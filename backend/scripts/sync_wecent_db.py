"""레다 공식 메뉴가 연결한 위센트 이머시브 공개 availability GET 수집기."""
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.firestore_db import init_firestore, get_db, upsert_cafe, get_or_create_theme, upsert_cafe_date_schedules

CAFE_ID = '28201117'
SITE_URL = 'https://wecent.kr'
BOOKING_URL = SITE_URL + '/reservation'
CAFE_META = {'name': '위센트 이머시브', 'branch_name': '홍대점', 'former_name': '레다스퀘어',
             'address': '서울 마포구 독막로9길 23 3층', 'area': 'hongdae',
             'website_url': SITE_URL, 'engine': 'wecent', 'is_active': True}


def parse_themes(html):
    soup = BeautifulSoup(html, 'html.parser')
    if 'Wecent Immersive' not in soup.get_text():
        raise ValueError('공식 위센트 예약 화면 불일치')
    themes = {}
    for button in soup.select('button[data-theme-id]'):
        key = button['data-theme-id']
        title = button.select_one('.theme-copy strong')
        subtitle = button.select_one('.theme-copy p')
        if not key.isdigit() or key in themes or button.get('data-branch-id') != '1' or not title:
            raise ValueError('테마 목록/홍대 지점 불일치')
        short_name = title.get_text(' ', strip=True)
        duration = re.search(r'(\d+)분', button.get_text(' ', strip=True))
        themes[key] = {'short_name': short_name, 'name': short_name + (' ' + subtitle.get_text(' ', strip=True) if subtitle else ''),
                       'duration_min': int(duration.group(1)) if duration else None}
    if not themes:
        raise ValueError('공식 테마 목록 비어 있음')
    return themes


def parse_availability(data, day, theme_id, theme):
    if data.get('date') != day or data.get('branch', {}).get('id') != 1 or data.get('branch', {}).get('name') != '홍대점':
        raise ValueError('응답 날짜/지점 불일치')
    if str(data.get('theme', {}).get('id')) != theme_id or data.get('theme', {}).get('name') != theme['short_name']:
        raise ValueError('응답 테마 불일치')
    if type(data.get('is_bookable_date')) is not bool or not isinstance(data.get('slots'), list):
        raise ValueError('공식 시간표 형식 변경')
    slots, seen = [], set()
    for row in data['slots']:
        if not isinstance(row, dict):
            raise ValueError('시간표 행 형식 변경')
        clock, available, closed, reason = (row.get(k) for k in ['time', 'available', 'is_closed', 'reason'])
        if not isinstance(clock, str) or not re.fullmatch(r'(?:[01]\d|2\d):[0-5]\d', clock) or clock in seen:
            raise ValueError('시간표 시간 오류/중복')
        seen.add(clock)
        if type(available) is not bool or type(closed) is not bool:
            raise ValueError('예약 상태 boolean 누락')
        if available:
            if closed or reason is not None or not data['is_bookable_date']:
                raise ValueError('예약 가능/마감 상태 충돌')
            status = 'available'
        elif reason == 'reserved' and not closed:
            status = 'full'
        elif reason in {'closed', 'past', 'out_of_range'}:
            if reason == 'closed' and not closed:
                raise ValueError('휴무 상태 충돌')
            status = 'closed'
        else:
            raise ValueError('알 수 없는 예약 상태')
        slots.append({'time': clock, 'status': status, 'booking_url': BOOKING_URL if status == 'available' else None})
    return slots if data['is_bookable_date'] else []


def main(run_schedule=True, days=6):
    init_firestore(settings.firebase_credentials_path)
    db = get_db()
    now = datetime.now(ZoneInfo('Asia/Seoul'))
    with requests.Session() as session:
        page = session.get(BOOKING_URL, timeout=20)
        page.raise_for_status()
        themes = parse_themes(page.text)
        upsert_cafe(db, CAFE_ID, CAFE_META)
        ids = {key: get_or_create_theme(db, CAFE_ID, theme['name'], {'is_active': True, 'duration_min': theme.get('duration_min')}) for key, theme in themes.items()}
        for offset in range(days + 1):
            day = (now.date() + timedelta(days=offset)).isoformat()
            schedules = {}
            for key, theme in themes.items():
                response = session.get(SITE_URL + '/reservation/availability/' + key, params={'date': day}, headers={'Accept': 'application/json'}, timeout=20)
                response.raise_for_status()
                slots = parse_availability(response.json(), day, key, theme)
                if slots:
                    schedules[ids[key]] = {'slots': slots}
                time.sleep(0.5)
            if schedules and run_schedule:
                upsert_cafe_date_schedules(db, day, CAFE_ID, schedules, now)
            print(day, sum(len(row['slots']) for row in schedules.values()), 'slots')


if __name__ == '__main__':
    main()
