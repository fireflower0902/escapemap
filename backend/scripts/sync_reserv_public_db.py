"""개편된 Reserv 공식 공개 시간표. 예약 생성/조회/취소 API는 호출하지 않는다."""
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote, urlencode
from zoneinfo import ZoneInfo

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.crawl_time import business_slot_datetime
from app.firestore_db import init_firestore, get_db, upsert_cafe, get_or_create_theme, upsert_cafe_date_schedules

BRANCHES = [{'cafe_id': '767938268',
  'cafe_name': '플레이더월드',
  'branch_name': '평택점',
  'address': '경기 평택시 평택2로10번길 34',
  'area': 'gyeonggi',
  'base_url': 'https://reservation.playthe.world',
  'shop_key': 'eerYSTbbLAQnqZv3'},
 {'cafe_id': '76631654',
  'cafe_name': '플레이더월드',
  'branch_name': '동성로점',
  'address': '대구 중구 동성로5길 43',
  'area': 'daegu',
  'base_url': 'https://reservation.playthe.world',
  'shop_key': 'bF9P9ARTDcgrbcDR'},
 {'cafe_id': '1637776603',
  'cafe_name': '플레이더월드',
  'branch_name': '부평점',
  'address': '인천 부평구 부평문화로80번길 31',
  'area': 'incheon',
  'base_url': 'https://reservation.playthe.world',
  'shop_key': 'fsGEtW3EXJiFXVCZ'},
 {'cafe_id': '1000900386',
  'cafe_name': '이스케이프샵',
  'branch_name': '',
  'address': '서울 강남구 논현로175길 93',
  'area': 'gangnam',
  'base_url': 'https://escapeshop.co.kr',
  'shop_key': 'Jmas3Q5kHnfxQhFZ'},
 {'cafe_id': '2016521022',
  'cafe_name': '이스케이프샵',
  'branch_name': '건대점',
  'address': '서울 광진구 능동로 129-1',
  'area': 'konkuk',
  'base_url': 'https://escapeshop.co.kr',
  'shop_key': 'tS5DajzuHqnhrnjH'},
 {'cafe_id': '27329834',
  'cafe_name': '룸익스케이프',
  'branch_name': '신촌 블랙점',
  'address': '서울 서대문구 연세로4길 6 3층',
  'area': 'sinchon',
  'base_url': 'https://ex-cape.com',
  'shop_key': 'Z5dmpFTTqzaSqaa4'},
 {'cafe_id': '1542251042',
  'cafe_name': '룸익스케이프',
  'branch_name': '신촌 화이트점',
  'address': '서울 서대문구 명물길 66 2층',
  'area': 'sinchon',
  'base_url': 'https://ex-cape.com',
  'shop_key': 'p8j31JZAgRCJWnUc'},
 {'cafe_id': '912842418',
  'cafe_name': '룸익스케이프',
  'branch_name': '신촌 올리브점',
  'address': '서울 서대문구 연세로9길 25 지하 1층',
  'area': 'sinchon',
  'base_url': 'https://ex-cape.com',
  'shop_key': 'vG4SZyg8jem2YYuo'},
 {'cafe_id': '690123759',
  'cafe_name': '룸익스케이프',
  'branch_name': '인디고블루점',
  'address': '서울 서대문구 연세로5가길 21',
  'area': 'sinchon',
  'base_url': 'https://ex-cape.com',
  'shop_key': 'mpu5Jvr5DzANeHRL'},
 {'cafe_id': '2012633570',
  'cafe_name': '오늘의한페이지 방탈출카페',
  'branch_name': '',
  'address': '서울 강남구 봉은사로6길 26',
  'area': 'gangnam',
  'base_url': 'https://page-today.co.kr',
  'shop_key': 'rjwaaAh3mVPbCdHA'},
 {'cafe_id': '1393764461',
  'cafe_name': '시간의문',
  'branch_name': '광주점',
  'address': '광주 동구 중앙로160번길 15-3, 3층',
  'area': 'gwangju',
  'base_url': 'https://gateoftime.kr',
  'shop_key': 'YybEYe16XjtuRV7S'},
 {'cafe_id': '929019886',
  'cafe_name': '시간의문',
  'branch_name': '대구동성로점',
  'address': '대구 중구 중앙대로 394-8, 2층',
  'area': 'daegu',
  'base_url': 'https://gateoftime.kr',
  'shop_key': 'HiJhoQFf8ThapVG3'},
 {'cafe_id': '138006966',
  'cafe_name': '더메이즈',
  'branch_name': '건대점',
  'address': '서울 광진구 아차산로26길 13 지하1층',
  'area': 'konkuk',
  'base_url': 'https://themazegd.co.kr',
  'shop_key': 'Am5Dz67F3dgg16F4'}]


def parse_detail(payload, branch, today, days, observed_at):
    if payload.get('result') != 'success' or not isinstance(payload.get('data'), dict):
        raise ValueError('공식 시간표 응답 형식 변경')
    data = payload['data']
    shop = data.get('shop', {})
    if shop.get('keycode') != branch['shop_key']:
        raise ValueError('요청 지점과 응답 지점 불일치')
    if shop.get('naver_only'):
        raise ValueError('네이버 전용 지점은 네이버 예약 수집기로 확인해야 합니다.')
    if not isinstance(data.get('themes'), list):
        raise ValueError('테마 목록 누락')
    parsed, seen = [], set()
    for theme in data['themes']:
        if theme.get('is_deleted'):
            continue
        name = str(theme.get('title') or '').strip()
        if not name or not isinstance(theme.get('slots'), list):
            raise ValueError('공식 테마명/시간표 누락')
        by_date = {}
        for slot in theme['slots']:
            day = date.fromisoformat(slot.get('day_date', ''))
            if not today <= day <= today + timedelta(days=days):
                continue  # The endpoint may return an entire month.
            value = slot.get('integer_to_time', '')
            if not re.fullmatch(r'(?:[01]\d|2\d):[0-5]\d', value):
                raise ValueError('공식 시간 표기 변경')
            if slot.get('theme_id') != theme.get('id') or type(slot.get('can_book')) is not bool:
                raise ValueError('시간표의 테마/예약 상태 불일치')
            key = (name, day, value)
            if key in seen:
                raise ValueError('동일 테마 예약 시간 중복')
            seen.add(key)
            status = 'available' if slot['can_book'] else 'full'
            hour, minute = map(int, value.split(':'))
            if business_slot_datetime(day, hour, minute).replace(tzinfo=ZoneInfo('Asia/Seoul')) <= observed_at:
                status = 'closed'
            if status == 'available' and (not isinstance(slot.get('left_stock'), int) or slot['left_stock'] <= 0):
                raise ValueError('예약 가능 상태와 잔여 수량 불일치')
            url = branch['base_url'] + '/reservation/?' + urlencode({'shop': branch['shop_key']})
            by_date.setdefault(day.isoformat(), []).append({'time': value, 'status': status, 'booking_url': url if status == 'available' else None})
        parsed.append({'name': name, 'poster_url': theme.get('image_url') or None,
                       'description': theme.get('description') or None, 'dates': by_date})
    if not parsed or not any(t['dates'] for t in parsed):
        raise ValueError('요청 기간의 공개 시간표가 비어 있음')
    return shop, parsed


def main(run_schedule=True, days=6):
    init_firestore(settings.firebase_credentials_path)
    db = get_db()
    for branch in BRANCHES:
        now = datetime.now(ZoneInfo('Asia/Seoul'))
        for attempt in range(2):
            try:
                response = requests.get(branch['base_url'] + '/api/booking/stores/' + quote(branch['shop_key'], safe=''),
                                        headers={'Accept': 'application/json', 'X-Playtheworld-Request': 'same-origin'}, timeout=25)
                break
            except (requests.Timeout, requests.ConnectionError):
                if attempt:
                    raise
                time.sleep(1)
        response.raise_for_status()
        shop, themes = parse_detail(response.json(), branch, now.date(), days, now)
        cid = branch['cafe_id']
        upsert_cafe(db, cid, {'name': branch['cafe_name'], 'branch_name': branch['branch_name'],
                             'address': shop.get('address') or branch['address'], 'area': branch['area'],
                             'website_url': branch['base_url'] + '/reservation/', 'engine': 'reserv_public', 'is_active': True})
        schedules = {}
        for theme in themes:
            tid = get_or_create_theme(db, cid, theme['name'], {'is_active': True, 'poster_url': theme['poster_url'], 'description': theme['description']})
            for day, slots in theme['dates'].items():
                schedules.setdefault(day, {})[tid] = {'slots': slots}
        for day, data in sorted(schedules.items()):
            if run_schedule:
                upsert_cafe_date_schedules(db, day, cid, data, now)
            print(cid, day, len(data), 'themes', sum(len(t['slots']) for t in data.values()), 'slots')


if __name__ == '__main__':
    main()
