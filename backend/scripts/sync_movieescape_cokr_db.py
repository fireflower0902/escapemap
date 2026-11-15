"""
무비이스케이프 동탄점(movieescape.co.kr) 테마 + 스케줄 DB 동기화 스크립트.

사이트: http://movieescape.co.kr
플랫폼: 자체 PHP (EUC-KR) - movieescape.kr(bucheonroute)와 다른 사이트

지점:
  동탄점  place_id=1956789824  area=gyeonggi  (경기 화성시 동탄구 반송동 88-8)

API:
  GET http://movieescape.co.kr/sub/03_1.html
      ?D_ROOM={A|B|C|D}&CHOIS_DATE={YYYY-MM-DD}
  응답: EUC-KR HTML
    예약가능: <a href="/sub/03_2.html?JIJEM_CODE=&CHOIS_DATE=...&ROOM_CODE=X&ROOM_TIME=HH:MM&ROOM_WEEK=...">
    예약불가: div.off or li.timeOff 형태

테마 (4개):
  A=몬스터 하우스, B=나홀로집에, C=춘향전, D=찰리와 초콜릿 공장

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_movieescape_cokr_db.py
  uv run python scripts/sync_movieescape_cokr_db.py --no-schedule
  uv run python scripts/sync_movieescape_cokr_db.py --days 14
"""

import re
import ssl
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import unquote

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from bs4 import BeautifulSoup

from app.config import settings
from app.firestore_db import (
    init_firestore, get_db, upsert_cafe,
    get_or_create_theme, upsert_cafe_date_schedules,
    load_cafe_hashes, save_cafe_hashes,
)

SITE_URL = "https://movieescape.co.kr"
RESERVE_URL = SITE_URL + "/sub/03_1.html"
REQUEST_DELAY = 0.8

CAFE_ID = "1956789824"
CAFE_META = {
    "name":        "무비이스케이프",
    "branch_name": "동탄점",
    "address":     "경기도 화성시 동탄중심상가2길 15 수성프라자 5층",
    "area":        "gyeonggi",
    "website_url": SITE_URL,
    "engine":      "movieescape_cokr",
    "crawled":     True,
    "is_active":   True,
}

THEMES: dict[str, str] = {
    "A": "몬스터 하우스",
    "B": "나홀로집에",
    "C": "춘향전",
    "D": "찰리와 초콜릿 공장",
}

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": SITE_URL + "/sub/03_1.html",
}


def _fetch(room_code: str, target_date: date) -> str:
    date_str = target_date.strftime("%Y-%m-%d")
    url = f"{RESERVE_URL}?D_ROOM={room_code}&CHOIS_DATE={date_str}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            raw = resp.read()
    except Exception as e:
        print(f"  [WARN] GET {url} 실패: {e}")
        return ""
    try:
        return raw.decode("euc-kr", errors="replace")
    except Exception:
        return raw.decode("utf-8", errors="replace")


def _parse_slots(html: str, target_date: date) -> list[dict]:
    """HTML에서 슬롯 목록 파싱. 반환: [{time, status, booking_url}]"""
    soup = BeautifulSoup(html, "html.parser")
    slots = []
    seen: set = set()

    # 예약가능: a href 포함 슬롯 (ROOM_TIME 파라미터)
    avail_pattern = re.compile(r"ROOM_TIME=([\d:]+)", re.IGNORECASE)
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        m = avail_pattern.search(href)
        if not m:
            continue
        time_str = m.group(1)
        if not re.match(r"^\d{2}:\d{2}$", time_str):
            continue
        if time_str in seen:
            continue
        seen.add(time_str)

        booking_url = SITE_URL + href if href.startswith("/") else href
        slots.append({
            "time":        time_str,
            "status":      "available",
            "booking_url": booking_url,
        })

    # 예약불가: div.off 또는 li.timeOff
    for el in soup.find_all(["div", "li"]):
        classes = el.get("class", [])
        if "off" in classes or "timeOff" in classes or "magam" in classes:
            # 시간 추출
            span = el.find("span", class_="time")
            if not span:
                span = el.find(class_=re.compile(r"time"))
            if not span:
                time_text = el.get_text(strip=True)
            else:
                time_text = span.get_text(strip=True)
            if re.match(r"^\d{2}:\d{2}$", time_text) and time_text not in seen:
                seen.add(time_text)
                slots.append({
                    "time":        time_text,
                    "status":      "full",
                    "booking_url": None,
                })

    return slots



# 개편된 공식 날짜별 예약표. 과거 /sub/03_1.html 요청은 사용하지 않습니다.
def _parse_current_page(html,day):
    from urllib.parse import urljoin
    soup=BeautifulSoup(html,'html.parser');calendar=soup.select_one('#me-date')
    if not calendar or calendar.get('value')!=day.isoformat():raise ValueError('공식 예약표 날짜 불일치')
    result={}
    for box in soup.select('.me-show-main'):
        title=box.select_one('h3');slots=[]
        if not title:continue
        for el in box.select('.me-slots .me-slot'):
            value=el.get('data-time') or (el.select_one('b').get_text(strip=True) if el.select_one('b') else '')
            if not re.fullmatch(r'(?:[012]\d):[0-5]\d',value):continue
            label=el.select_one('small');label=label.get_text(strip=True).replace(' ','') if label else ''
            if label=='예약가능' and el.name=='a' and el.get('href'):status='available'
            elif label in ('마감','예약마감','예약불가','예약완료'):status='full'
            else:raise ValueError('알 수 없는 공식 예약 상태')
            slots.append({'time':value,'status':status,'booking_url':urljoin(SITE_URL,el['href']) if status=='available' else None})
        result[title.get_text(' ',strip=True)]=slots
    return result

def main(run_schedule=True,days=14):
    import requests
    init_firestore(settings.firebase_credentials_path);db=get_db();today=date.today()
    for offset in range(days+1 if run_schedule else 1):
        day=today+timedelta(days=offset);r=requests.get(SITE_URL+'/theme/'+day.isoformat()+'/',timeout=25);r.raise_for_status();parsed=_parse_current_page(r.text,day)
        if not parsed:raise ValueError('공식 테마 목록 파싱 실패')
        if offset==0:upsert_cafe(db,CAFE_ID,CAFE_META)
        data={}
        for name,slots in parsed.items():
            tid=get_or_create_theme(db,CAFE_ID,name,{'is_active':True})
            if slots:data[tid]={'slots':slots}
        if run_schedule and data:upsert_cafe_date_schedules(db,day.isoformat(),CAFE_ID,data,datetime.now())
        print(CAFE_ID,day,len(parsed),'themes',sum(len(t['slots']) for t in data.values()),'slots',flush=True);time.sleep(REQUEST_DELAY)
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--days',type=int,default=14);p.add_argument('--no-schedule',action='store_true');a=p.parse_args();main(not a.no_schedule,a.days)
