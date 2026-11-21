"""코드이스케이프 가로수길 공식 공개 날짜별 시간표. 예약 생성은 호출하지 않는다."""
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.firestore_db import init_firestore, get_db, upsert_cafe, get_or_create_theme, upsert_cafe_date_schedules

CAFE_ID = '522639283'
SITE_URL = 'http://www.code-escape-garosu.com'
RESERVE_URL = SITE_URL + '/web/home.php'
CAFE_META = {'name': '코드이스케이프', 'branch_name': '가로수길점',
             'address': '서울 강남구 가로수길 14 다모빌딩 5층', 'area': 'gangnam',
             'website_url': SITE_URL, 'engine': 'codegarosu', 'is_active': True}


def parse_page(html, day):
    soup = BeautifulSoup(html, 'html.parser')
    form = soup.find('form', attrs={'name': 'register'})
    if not form:
        raise ValueError('공식 검색 양식 없음')
    values = {e.get('name'): e.get('value') for e in form.select('input[name]')}
    if values.get('rev_days') != day or values.get('zizum_num') != '1':
        raise ValueError('조회 날짜/지점 불일치')
    if '가로수길' not in soup.get_text():
        raise ValueError('공식 지점명 불일치')
    themes = {e.get('value'): e.get_text(' ', strip=True) for e in form.select('select[name=theme_num] option[value]') if e.get('value')}
    if not themes or len(set(themes.values())) != len(themes):
        raise ValueError('테마 목록 없음/중복')
    names = {v: k for k, v in themes.items()}
    data, seen = {}, set()
    for tr in soup.select('table.list tr'):
        cells = tr.find_all('td', recursive=False)
        if not cells:
            continue
        if len(cells) != 4:
            raise ValueError('시간표 열 변경')
        clock, name = [e.get_text(' ', strip=True) for e in cells[:2]]
        if not re.fullmatch(r'(?:[01]\d|2\d):[0-5]\d', clock) or name not in names:
            raise ValueError('알 수 없는 시간/테마')
        key = (name, clock)
        if key in seen:
            raise ValueError('시간표 중복')
        seen.add(key)
        image = cells[3].find('img')
        icon = (image.get('src', '').rsplit('/', 1)[-1] if image else '')
        anchor = cells[3].find('a')
        available = icon == 'rev_y.png' and anchor and re.fullmatch(r"javascript:fun_rev_next\('\d+',''\)", anchor.get('href', ''))
        if available:
            status = 'available'
        elif icon == 'rev_n.png' and not anchor:
            status = 'full'
        else:
            raise ValueError('알 수 없는 예약 상태')
        link = RESERVE_URL + '?' + urlencode({'mid': 2, 'go': 'rev_make', 'rev_days': day, 'person': 3, 'zizum_num': 1})
        data.setdefault(names[name], []).append({'time': clock, 'status': status, 'booking_url': link if available else None})
    return themes, data


def main(run_schedule=True, days=6):
    init_firestore(settings.firebase_credentials_path)
    db = get_db()
    now = datetime.now(ZoneInfo('Asia/Seoul'))
    upsert_cafe(db, CAFE_ID, CAFE_META)
    ids = {}
    with requests.Session() as session:
        for offset in range(days + 1):
            day = (now.date() + timedelta(days=offset)).isoformat()
            response = session.get(RESERVE_URL, params={'mid': 2, 'go': 'rev_make', 'rev_days': day, 'person': 3, 'zizum_num': 1}, timeout=20)
            response.raise_for_status()
            response.encoding = 'utf-8'
            themes, data = parse_page(response.text, day)
            for key, name in themes.items():
                if key not in ids:
                    ids[key] = get_or_create_theme(db, CAFE_ID, name, {'is_active': True})
            if data and run_schedule:
                upsert_cafe_date_schedules(db, day, CAFE_ID, {ids[key]: {'slots': slots} for key, slots in data.items()}, now)
            print(day, len(data), 'themes', sum(map(len, data.values())), 'slots')
            time.sleep(0.5)


if __name__ == '__main__':
    main()
