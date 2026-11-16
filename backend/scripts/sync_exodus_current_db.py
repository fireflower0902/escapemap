"""엑소더스 강남1호점 개편 후 공식 공개 slots API. 예약 생성은 호출하지 않는다."""
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.firestore_db import init_firestore, get_db, upsert_cafe, get_or_create_theme, upsert_cafe_date_schedules

CAFE_ID = '103606910'
BASE_URL = 'https://booking.exodusescape.co.kr'
CAFE_META = {'name': '엑소더스', 'branch_name': '강남1호점', 'address': '서울 강남구 역삼동 619-23 지하 1층',
             'area': 'gangnam', 'website_url': BASE_URL, 'engine': 'exodus_current', 'is_active': True}


def parse_payload(payload, today, days):
    if payload.get('branch') != 'gangnam' or payload.get('branch_info', {}).get('name') != '엑소더스 강남1호점':
        raise ValueError('공식 예약 지점 불일치')
    if not isinstance(payload.get('themes'), dict) or not isinstance(payload.get('days'), dict):
        raise ValueError('공식 시간표 응답 변경')
    schedules = {}
    seen = set()
    statuses = {'available': 'available', 'booked': 'full', 'closed': 'closed'}
    for key, slots in payload['days'].items():
        day = date.fromisoformat(key)
        if not today <= day <= today + timedelta(days=days):
            continue
        if not isinstance(slots, list):
            raise ValueError('공식 날짜별 시간표 변경')
        for slot in slots:
            theme = payload['themes'].get(slot.get('theme_id'), {})
            if not theme.get('name') or theme['name'] != slot.get('theme'):
                raise ValueError('테마 ID/이름 불일치')
            value = slot.get('time', '')
            if not re.fullmatch(r'(?:[01]\d|2\d):[0-5]\d', value) or slot.get('status') not in statuses or type(slot.get('past')) is not bool:
                raise ValueError('공식 예약 시간/상태 변경')
            unique = (key, theme['name'], value)
            if unique in seen:
                raise ValueError('시간표 중복')
            seen.add(unique)
            status = 'closed' if slot['past'] else statuses[slot['status']]
            schedules.setdefault(key, {}).setdefault(slot['theme_id'], []).append({
                'time': value, 'status': status, 'booking_url': BASE_URL + '/' if status == 'available' else None})
    if not any(schedules.values()):
        raise ValueError('공식 시간표가 비어 있음')
    return payload['themes'], schedules


def main(run_schedule=True, days=6):
    init_firestore(settings.firebase_credentials_path)
    db = get_db()
    now = datetime.now(ZoneInfo('Asia/Seoul'))
    response = requests.get(BASE_URL + '/api/slots', params={'days': days}, timeout=25)
    response.raise_for_status()
    themes, schedules = parse_payload(response.json(), now.date(), days)
    upsert_cafe(db, CAFE_ID, CAFE_META)
    ids = {key: get_or_create_theme(db, CAFE_ID, theme['name'], {'is_active': True, 'duration_min': theme.get('duration')})
           for key, theme in themes.items()}
    for day, data in schedules.items():
        if run_schedule:
            upsert_cafe_date_schedules(db, day, CAFE_ID, {ids[key]: {'slots': slots} for key, slots in data.items()}, now)
        print(day, len(data), 'themes', sum(map(len, data.values())), 'slots')


if __name__ == '__main__':
    main()
