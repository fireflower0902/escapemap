"""춘천 이스케이프존 공식 공개 시간표. 영업일의 24시 이후 표기를 보존한다."""
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlsplit, parse_qs
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.firestore_db import init_firestore, get_db, upsert_cafe, get_or_create_theme, upsert_cafe_date_schedules

CAFE_ID = '230738333'
BASE_URL = 'http://www.cc-escapezone.co.kr'
CAFE_META = {'name': '이스케이프존', 'branch_name': '강대점',
             'address': '강원특별자치도 춘천시 서부대성로 231-1 4층', 'area': 'gangwon',
             'website_url': BASE_URL + '/kr/webpage.php?webpage=0301', 'engine': 'ccescapezone', 'is_active': True}


def parse_page(html, day):
    if not re.search(r'"setDate"\s*,\s*"' + re.escape(day) + r'"', html):
        raise ValueError('요청 날짜와 공식 시간표 날짜 불일치')
    soup = BeautifulSoup(html, 'html.parser')
    themes = []
    for first_slot in soup.select('.spurs_btn1'):
        # Each theme has a distinct slot-list parent; process each list once.
        parent = first_slot.parent
        if first_slot != parent.select_one('.spurs_btn1'):
            continue
        heading = parent.find_previous('div', style=re.compile('font-size:24px'))
        if not heading or not heading.get_text(strip=True):
            raise ValueError('시간표 테마명 누락')
        slots = []
        for node in parent.select('.spurs_btn1'):
            value = node.get_text(strip=True)
            if not re.fullmatch(r'(?:[01]\d|2\d):[0-5]\d', value):
                raise ValueError('공식 시간 표기 변경')
            action = node.get('onclick', '')
            if action:
                match = re.fullmatch(r"location.href='([^']+)'", action)
                if not match:
                    raise ValueError('예약 링크 형식 변경')
                link = urljoin(BASE_URL, match[1])
                query = parse_qs(urlsplit(link).query)
                if urlsplit(link).netloc != urlsplit(BASE_URL).netloc or query.get('date') != [day] or query.get('reserve_time') != [value]:
                    raise ValueError('예약 링크 날짜/시간 불일치')
                status = 'available'
            elif 'line-through' in node.get('style', ''):
                link, status = None, 'full'
            else:
                raise ValueError('예약 상태를 확인할 수 없음')
            slots.append({'time': value, 'status': status, 'booking_url': link})
        themes.append({'name': heading.get_text(strip=True), 'slots': slots})
    if not themes:
        raise ValueError('공식 시간표가 비어 있음')
    return themes


def main(run_schedule=True, days=6):
    init_firestore(settings.firebase_credentials_path)
    db = get_db()
    upsert_cafe(db, CAFE_ID, CAFE_META)
    now = datetime.now(ZoneInfo('Asia/Seoul'))
    with requests.Session() as session:
        for offset in range(days + 1):
            day = (now.date() + timedelta(days=offset)).isoformat()
            response = session.get(CAFE_META['website_url'], params={'date': day}, timeout=20)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            parsed = parse_page(response.text, day)
            themes = {}
            for theme in parsed:
                tid = get_or_create_theme(db, CAFE_ID, theme['name'], {'is_active': True})
                themes[tid] = {'slots': theme['slots']}
            if run_schedule:
                upsert_cafe_date_schedules(db, day, CAFE_ID, themes, now)
            print(day, len(themes), 'themes', sum(len(t['slots']) for t in themes.values()), 'slots')
            if offset < days:
                time.sleep(0.5)


if __name__ == '__main__':
    main()
