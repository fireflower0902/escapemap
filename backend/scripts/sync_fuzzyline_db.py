"""하이드앤시크 새 공식 도메인의 공개 지점/테마/시간표 GET 수집기."""
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.firestore_db import init_firestore, get_db, upsert_cafe, get_or_create_theme, upsert_cafe_date_schedules

SITE_URL = 'https://play.fuzzyline.io'
BRANCHES = [
    {'cafe_id': '554838835', 'room_id': 1, 'branch_name': 'The Origin 연남',
     'address': '서울 마포구 월드컵북로6길 24-7 SANTOH빌딩 B1', 'area': 'hongdae'},
    {'cafe_id': '1944665207', 'room_id': 2, 'branch_name': 'Cyberpunk 안국',
     'address': '서울 종로구 인사동길 44 쌈지길 B2', 'area': 'myeongdong'},
]
KST = ZoneInfo('Asia/Seoul')


def public_data(session, path, params):
    response = session.get(SITE_URL + path, params=params, timeout=20)
    response.raise_for_status()
    payload = response.json()
    if payload.get('success') is not True or not isinstance(payload.get('data'), list):
        raise ValueError('공식 공개 목록 응답 변경')
    return payload['data']


def parse_slots(rows, day, room_id, theme_id, slug, now):
    if not isinstance(rows, list):
        raise ValueError('시간표 배열 누락')
    slots, seen = [], set()
    for row in rows:
        if not isinstance(row, dict) or row.get('roomId') != room_id or row.get('themeId') != theme_id:
            raise ValueError('응답 지점/테마 불일치')
        raw = row.get('startTime')
        if not isinstance(raw, str):
            raise ValueError('시작시간 누락')
        start = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        if start.tzinfo is None:
            raise ValueError('시간대 누락')
        local = start.astimezone(KST)
        if local.date().isoformat() != day or local.second or local.microsecond:
            raise ValueError('응답 날짜/분 단위 시간 불일치')
        clock = local.strftime('%H:%M')
        if clock in seen:
            raise ValueError('시간표 중복')
        seen.add(clock)
        remaining, capacity, status = row.get('remainingCapacity'), row.get('capacityMax'), row.get('status')
        if type(remaining) is not int or type(capacity) is not int or not 0 <= remaining <= capacity or capacity < 0:
            raise ValueError(f'잔여 인원 형식 오류: {day} {clock}, remaining={remaining!r}, capacity={capacity!r}')
        if status not in {'open', 'filling', 'full', 'closed', 'in_progress', 'pre_open'}:
            raise ValueError('알 수 없는 시간표 상태')
        # 공식 시간 선택 UI와 동일하게 잔여0, full/closed/in_progress/pre_open은 선택 불가.
        if local <= now or status in {'closed', 'in_progress', 'pre_open'}:
            normalized = 'closed'
        elif remaining <= 0 or status == 'full':
            normalized = 'full'
        else:
            normalized = 'available'
        link = SITE_URL + '/select?' + urlencode({'theme': slug})
        slots.append({'time': clock, 'status': normalized, 'booking_url': link if normalized == 'available' else None})
    return slots


def main(run_schedule=True, days=6):
    init_firestore(settings.firebase_credentials_path)
    db = get_db()
    now = datetime.now(KST)
    with requests.Session() as session:
        rooms = public_data(session, '/api/rooms/homepage', {'locale': 'ko'})
        themes = public_data(session, '/api/themes', {'locale': 'ko'})
        for branch in BRANCHES:
            room_id, cafe_id = branch['room_id'], branch['cafe_id']
            matches = [r for r in rooms if r.get('room_id') == room_id]
            if len(matches) != 1 or matches[0].get('name') != branch['branch_name'] or matches[0].get('branchInfo', {}).get('address') != branch['address']:
                raise ValueError('공식 지점명/주소 불일치')
            selected = [t for t in themes if t.get('RoomID') == room_id]
            if not selected:
                raise ValueError('공식 테마 없음')
            ids, slugs = {}, {}
            for theme in selected:
                tid, name, slug = theme.get('ThemeID'), theme.get('NameKo'), theme.get('Slug')
                if type(tid) is not int or tid in ids or not name or not isinstance(slug, str) or not re.fullmatch(r'[a-z0-9-]+', slug):
                    raise ValueError('테마 ID/이름/예약 경로 불일치')
                ids[tid] = get_or_create_theme(db, cafe_id, name, {'is_active': True, 'duration_min': theme.get('TimeLimit')})
                slugs[tid] = slug
            upsert_cafe(db, cafe_id, {'name': '하이드앤시크', 'branch_name': branch['branch_name'], 'address': branch['address'],
                                    'area': branch['area'], 'website_url': SITE_URL, 'engine': 'fuzzyline', 'is_active': True})
            for offset in range(days + 1):
                day = (now.date() + timedelta(days=offset)).isoformat()
                data = {}
                for tid, theme_doc in ids.items():
                    rows = public_data(session, '/api/slots', {'date': day, 'roomId': room_id, 'themeId': tid})
                    slots = parse_slots(rows, day, room_id, tid, slugs[tid], now)
                    if slots:
                        data[theme_doc] = {'slots': slots}
                    time.sleep(0.5)
                if data and run_schedule:
                    upsert_cafe_date_schedules(db, day, cafe_id, data, now)
                print(cafe_id, day, sum(len(t['slots']) for t in data.values()), 'slots')


if __name__ == '__main__':
    main()
