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

SITE_URL = "http://movieescape.co.kr"
RESERVE_URL = SITE_URL + "/sub/03_1.html"
REQUEST_DELAY = 0.8

CAFE_ID = "1956789824"
CAFE_META = {
    "name":        "무비이스케이프",
    "branch_name": "동탄점",
    "address":     "경기 화성시 동탄구 반송동 88-8",
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


# ── DB 동기화 ─────────────────────────────────────────────────────────────────

def main(run_schedule: bool = True, days: int = 14):
    print("=" * 60)
    print("무비이스케이프 동탄점(movieescape.co.kr) → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)
    db = get_db()

    print("\n[ 1단계 ] 카페 메타 동기화")
    upsert_cafe(db, CAFE_ID, CAFE_META)
    print(f"  [UPSERT] 카페: 무비이스케이프 동탄점 (id={CAFE_ID})")

    # 테마 upsert
    print("\n[ 2단계 ] 테마 동기화")
    theme_doc_map: dict[str, str] = {}
    for code, name in THEMES.items():
        doc_id = get_or_create_theme(db, CAFE_ID, name, {
            "poster_url": None,
            "is_active":  True,
        })
        theme_doc_map[code] = doc_id
        print(f"  [UPSERT] 테마: {name} (code={code})")

    if not run_schedule:
        print("\n동기화 완료 (스케줄 건너뜀)")
        return

    # 스케줄 upsert
    print(f"\n[ 3단계 ] 스케줄 동기화 (오늘~{days}일 후)")
    today = date.today()
    crawled_at = datetime.now()
    known_hashes = load_cafe_hashes(db, CAFE_ID)
    new_hashes: dict[str, str] = {}
    date_themes: dict[str, dict] = {}

    for i in range(days + 1):
        target_date = today + timedelta(days=i)
        date_str = target_date.strftime("%Y-%m-%d")
        avail = full = 0

        for code, doc_id in theme_doc_map.items():
            html = _fetch(code, target_date)
            time.sleep(REQUEST_DELAY)
            slots = _parse_slots(html, target_date)

            for slot in slots:
                try:
                    hh, mm = int(slot["time"][:2]), int(slot["time"][3:5])
                except Exception:
                    continue
                slot_dt = datetime(
                    target_date.year, target_date.month, target_date.day, hh, mm
                )
                if slot_dt <= datetime.now():
                    continue

                date_themes.setdefault(date_str, {}).setdefault(
                    doc_id, {"slots": []}
                )["slots"].append({
                    "time":        f"{hh:02d}:{mm:02d}",
                    "status":      slot["status"],
                    "booking_url": slot.get("booking_url"),
                })
                if slot["status"] == "available":
                    avail += 1
                else:
                    full += 1

        print(f"  {date_str}: 가능 {avail} / 마감 {full}")

    writes = 0
    for date_str, themes_map in date_themes.items():
        h = upsert_cafe_date_schedules(
            db, date_str, CAFE_ID, themes_map, crawled_at,
            known_hash=known_hashes.get(date_str),
        )
        if h:
            new_hashes[date_str] = h
            writes += 1

    if new_hashes:
        today_str = today.isoformat()
        save_cafe_hashes(db, CAFE_ID, {
            k: v for k, v in {**known_hashes, **new_hashes}.items()
            if k >= today_str
        })

    print(f"\n  스케줄 동기화: {writes}개 날짜 작성")
    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="무비이스케이프 동탄점 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
