"""어메이즈드 부평3호점 공식 Booked 공개 일정 (예약 생성 없이 날짜 조회만)."""
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

CAFE_ID = '2138418097'
BASE_URL = 'https://amazed.co.kr'
BOOKING_URL = 'https://amazed.co.kr/?page_id=4808#booking'
CAFE_META = {'name': '어메이즈드', 'branch_name': '3호점', 'address': '인천 부평구 시장로 36 명지빌딩 6층',
             'area': 'incheon', 'website_url': BOOKING_URL, 'engine': 'amazed_booked', 'is_active': True}
THEME_NAME = 'SHIFT : 고쿄의 하루'  # Official booking-page title artwork, calendar 19.


def parse_slots(html, day):
    soup = BeautifulSoup(html, 'html.parser')
    wrapper = soup.select_one('.booked-appt-list')
    if wrapper is None or wrapper.get('data-list-date') != day:
        raise ValueError('공식 일정 날짜 불일치')
    slots = []
    for node in wrapper.select('.timeslot'):
        button = node.select_one('button.new-appt')
        if not button or button.get('data-calendar-id') != '19' or button.get('data-date') != day:
            raise ValueError('공식 테마 일정 식별자 변경')
        interval = button.get('data-timeslot', '')
        match = re.fullmatch(r'([012]\d)([0-5]\d)-[012]\d[0-5]\d', interval)
        if not match:
            raise ValueError('공식 시간 표기 변경')
        value = match[1] + ':' + match[2]
        if button.has_attr('disabled') and '매진되었습니다' in button.get_text():
            status = 'full'
        elif not button.has_attr('disabled') and 'timeslot-unavailable' not in node.get('class', []) and '바로 예매하기' in button.get_text():
            status = 'available'
        else:
            raise ValueError('공식 예약 상태 불명확')
        slots.append({'time': value, 'status': status, 'booking_url': BOOKING_URL if status == 'available' else None})
    if not slots:
        raise ValueError('공식 시간표 비어 있음')
    return slots


def main(run_schedule=True, days=6):
    init_firestore(settings.firebase_credentials_path)
    db = get_db()
    now = datetime.now(ZoneInfo('Asia/Seoul'))
    with requests.Session() as session:
        page = session.get(BOOKING_URL, timeout=25)
        page.raise_for_status()
        soup = BeautifulSoup(page.content, 'html.parser')
        if not soup.select_one('.booked-list-view-nav[data-calendar-id="19"]') or '부평3호점' not in soup.get_text():
            raise ValueError('공식 지점 또는 테마 일정 변경')
        upsert_cafe(db, CAFE_ID, CAFE_META)
        tid = get_or_create_theme(db, CAFE_ID, THEME_NAME, {'duration_min': 100, 'is_active': True})
        for offset in range(days + 1):
            day = (now.date() + timedelta(days=offset)).isoformat()
            # Same read-only action used by the official date-next control.
            response = session.post(BASE_URL + '/wp-admin/admin-ajax.php',
                data={'action': 'booked_appointment_list_date', 'date': day, 'calendar_id': '19', 'force_default': 'false'}, timeout=25)
            response.raise_for_status()
            slots = parse_slots(response.content, day)
            if run_schedule:
                upsert_cafe_date_schedules(db, day, CAFE_ID, {tid: {'slots': slots}}, now)
            print(day, '1 theme', len(slots), 'slots')
            if offset < days:
                time.sleep(.5)


if __name__ == '__main__':
    main()
