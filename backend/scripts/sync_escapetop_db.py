"""
이스케이프탑 + 에베레스트이스케이프 테마 + 스케줄 DB 동기화 스크립트.

사이트: 각 지점별 독립 사이트 (kwangjutop.com, busantop.net 등)
예약 시스템: 네이버 예약 (booking.naver.com) GraphQL API

이스케이프탑 지점:
  광주점  businessId=19971   cafe_id=1856406910  area=gwangju
  부산점  businessId=19907   cafe_id=665041653   area=busan
  창원점  businessId=70013   cafe_id=1097124167  area=gyeongnam
  울산점  businessId=25732   cafe_id=284779798   area=ulsan
  수원점  businessId=85882   cafe_id=836762242   area=gyeonggi
  대전점  businessId=44773   cafe_id=1973717836  area=daejeon

기타 네이버예약 지점:
  에베레스트이스케이프            businessId=900300   bizTypeId=6  cafe_id=164116124  area=gyeonggi
  브레이크아웃이스케이프 해운대본점  businessId=27519    cafe_id=170158027  area=busan
  브레이크아웃이스케이프 홍대점     businessId=110544   cafe_id=451924760  area=hongdae
  나비잠 방탈출 1호점             businessId=1564927  cafe_id=713424921  area=gyeonggi
  나비잠방탈출 2호점              businessId=1583178  cafe_id=704757588  area=gyeonggi
  리얼월드 커넥트현대 청주점       businessId=1438216  cafe_id=1488706210 area=chungbuk
  오늘탈출 고양점                 businessId=284482   cafe_id=300855776  area=gyeonggi
  시그널헌터 광교중앙점            businessId=1556188  cafe_id=215947527  area=gyeonggi
  타임이스케이프 창원점            businessId=1325475  cafe_id=27607543   area=gyeongnam
  브레인이스케이프 광주점          businessId=427883   cafe_id=1459848720 area=gwangju
  방탈출추리존 대전              businessId=509345   cafe_id=2138163704 area=daejeon
  러시아워방탈출 3호점 광주        businessId=1370021  cafe_id=2102768222 area=gwangju
  러시아워방탈출 로드맨션 광주      businessId=540364   cafe_id=942247508  area=gwangju
  카타르시스이스케이프 서면 부산     businessId=737799   cafe_id=1358303820 area=busan
  판타지아방탈출카페 광주           businessId=795803   cafe_id=100018735  area=gwangju
API:
  POST https://booking.naver.com/graphql
  - bizItems 쿼리: 지점별 테마 목록 반환
  - schedule 쿼리: bizItemId + 날짜 범위 → daily summary 또는 hourly 슬롯

스케줄 응답:
  hourly: [{
    unitStartTime: "YYYY-MM-DD HH:MM:SS",  (KST)
    unitBookingCount: int,  (예약된 수)
    unitStock: int,         (총 슬롯 수)
  }]
  → unitBookingCount < unitStock → available

예약 URL: https://booking.naver.com/booking/12/bizes/{businessId}/items/{bizItemId}

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_escapetop_db.py
  uv run python scripts/sync_escapetop_db.py --no-schedule
  uv run python scripts/sync_escapetop_db.py --days 14
"""

import json
import re
import ssl
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings
from app.firestore_db import (
    init_firestore, get_db, upsert_cafe,
    get_or_create_theme, upsert_cafe_date_schedules,
    load_cafe_hashes, save_cafe_hashes,
)

NAVER_BOOKING_URL = "https://booking.naver.com"
GRAPHQL_URL = NAVER_BOOKING_URL + "/graphql"
BUSINESS_TYPE_ID = 12
REQUEST_DELAY = 0.5

BRANCHES = [
    {
        "cafe_id":          "1856406910",
        "business_id":      "19971",
        "business_type_id": 12,
        "branch_name":      "광주점",
        "name":             "이스케이프탑",
        "address":          "광주 동구 충장로3가 38-14",
        "area":             "gwangju",
        "site_url":         "http://kwangjutop.com",
    },
    {
        "cafe_id":          "665041653",
        "business_id":      "19907",
        "business_type_id": 12,
        "branch_name":      "부산점",
        "name":             "이스케이프탑",
        "address":          "부산 부산진구 부전동 520-14",
        "area":             "busan",
        "site_url":         "http://busantop.net",
    },
    {
        "cafe_id":          "1097124167",
        "business_id":      "70013",
        "business_type_id": 12,
        "branch_name":      "창원점",
        "name":             "이스케이프탑",
        "address":          "경남 창원시 성산구 상남동 13-4",
        "area":             "gyeongnam",
        "site_url":         "http://changwontop.net",
    },
    {
        "cafe_id":          "284779798",
        "business_id":      "25732",
        "business_type_id": 12,
        "branch_name":      "울산점",
        "name":             "이스케이프탑",
        "address":          "울산 남구 삼산동 1522-2",
        "area":             "ulsan",
        "site_url":         "http://www.ulsantop.net",
    },
    {
        "cafe_id":          "836762242",
        "business_id":      "85882",
        "business_type_id": 12,
        "branch_name":      "수원점",
        "name":             "이스케이프탑",
        "address":          "경기 수원시 팔달구 인계동 1032-8",
        "area":             "gyeonggi",
        "site_url":         "http://suwontop.net",
    },
    {
        "cafe_id":          "1973717836",
        "business_id":      "44773",
        "business_type_id": 12,
        "branch_name":      "대전점",
        "name":             "이스케이프탑",
        "address":          "대전 중구 은행동 166-2",
        "area":             "daejeon",
        "site_url":         "http://daejeontop.net",
    },
    # 에베레스트이스케이프 (경기 고양시 일산)
    {
        "cafe_id":          "164116124",
        "business_id":      "900300",
        "business_type_id": 6,
        "branch_name":      "",
        "name":             "에베레스트이스케이프",
        "address":          "경기 고양시 일산동구 백석동 1283-1",
        "area":             "gyeonggi",
        "site_url":         "http://everestescape.com",
    },
    # 괴담저장소 한강대 담력훈련 (서울 마포구)
    {
        "cafe_id":          "617331855",
        "business_id":      "1204854",
        "business_type_id": 12,
        "branch_name":      "한강대점",
        "name":             "괴담저장소",
        "address":          "서울 마포구 동교동 198-1",
        "area":             "hongdae",
        "site_url":         "https://mysteryzip.com",
        "normalize_theme":  True,  # "[월] 테마명" → "테마명" 정규화
    },
    # 괴담저장소 제일기숙학원 (별도 businessId)
    {
        "cafe_id":          "617331855",  # 같은 카카오 장소
        "business_id":      "1335513",
        "business_type_id": 12,
        "branch_name":      "한강대점",
        "name":             "괴담저장소",
        "address":          "서울 마포구 동교동 198-1",
        "area":             "hongdae",
        "site_url":         "https://mysteryzip.com",
        "normalize_theme":  True,
    },
    # 시크릿도어 방탈출카페 군포산본점 (bit.ly/3z5y45w → booking.naver.com/booking/12/bizes/731521)
    {
        "cafe_id":          "163640808",
        "business_id":      "731521",
        "business_type_id": 12,
        "branch_name":      "군포산본점",
        "name":             "시크릿도어",
        "address":          "경기 군포시 산본동 1136-2",
        "area":             "gyeonggi",
        "site_url":         "https://booking.naver.com/booking/12/bizes/731521",
    },
    # 브레이크아웃이스케이프 해운대본점 (busan.breakoutescapegame.com)
    {
        "cafe_id":          "170158027",
        "business_id":      "27519",
        "business_type_id": 12,
        "branch_name":      "해운대본점",
        "name":             "브레이크아웃이스케이프",
        "address":          "부산 해운대구 중동 1394-286",
        "area":             "busan",
        "site_url":         "https://busan.breakoutescapegame.com",
    },
    # 브레이크아웃이스케이프 홍대점 (hongdae.breakoutescapegame.com)
    {
        "cafe_id":          "451924760",
        "business_id":      "110544",
        "business_type_id": 12,
        "branch_name":      "홍대점",
        "name":             "브레이크아웃이스케이프",
        "address":          "서울 마포구 서교동 338-48",
        "area":             "hongdae",
        "site_url":         "https://hongdae.breakoutescapegame.com",
    },
    # 나비잠 방탈출 1호점 (nabijam.com - 네이버 예약)
    {
        "cafe_id":          "713424921",
        "business_id":      "1564927",
        "business_type_id": 12,
        "branch_name":      "1호점",
        "name":             "나비잠",
        "address":          "경기 안양시 동안구 호계동 1044-1",
        "area":             "gyeonggi",
        "site_url":         "https://nabijam.com",
    },
    # 나비잠방탈출 2호점 (nabijam.com - 네이버 예약)
    {
        "cafe_id":          "704757588",
        "business_id":      "1583178",
        "business_type_id": 12,
        "branch_name":      "2호점",
        "name":             "나비잠",
        "address":          "경기 안양시 동안구 호계동 1049",
        "area":             "gyeonggi",
        "site_url":         "https://nabijam.com",
    },
    # 리얼월드 커넥트현대 청주점 (cheongju.realworld.to - 네이버 예약)
    {
        "cafe_id":          "1488706210",
        "business_id":      "1438216",
        "business_type_id": 12,
        "branch_name":      "커넥트현대 청주점",
        "name":             "리얼월드",
        "address":          "충북 청주시",
        "area":             "chungbuk",
        "site_url":         "https://cheongju.realworld.to",
    },
    # 오늘탈출 고양점 (todayescape.com - 네이버 예약, 4시간 방탈출)
    {
        "cafe_id":          "300855776",
        "business_id":      "284482",
        "business_type_id": 12,
        "branch_name":      "고양점",
        "name":             "오늘탈출",
        "address":          "경기 고양시",
        "area":             "gyeonggi",
        "site_url":         "https://www.todayescape.com",
    },
    # 시그널헌터 광교중앙점 (signalhunter.co.kr - 네이버 예약)
    {
        "cafe_id":          "215947527",
        "business_id":      "1556188",
        "business_type_id": 12,
        "branch_name":      "광교중앙점",
        "name":             "시그널헌터",
        "address":          "경기 수원시 영통구 이의동 1347-2",
        "area":             "gyeonggi",
        "site_url":         "https://www.signalhunter.co.kr",
    },
    # 타임이스케이프 창원점 (timeescape.co.kr - 네이버 예약)
    {
        "cafe_id":          "27607543",
        "business_id":      "1325475",
        "business_type_id": 12,
        "branch_name":      "창원점",
        "name":             "타임이스케이프",
        "address":          "경남 창원시 성산구 상남동 17-4",
        "area":             "gyeongnam",
        "site_url":         "http://www.timeescape.co.kr",
    },
    # 브레인이스케이프 광주점 (brain-escape.co.kr - 네이버 예약)
    {
        "cafe_id":          "1459848720",
        "business_id":      "427883",
        "business_type_id": 12,
        "branch_name":      "광주점",
        "name":             "브레인이스케이프",
        "address":          "광주 동구 황금동 20",
        "area":             "gwangju",
        "site_url":         "http://www.brain-escape.co.kr",
    },
    # 방탈출추리존 대전 (네이버 예약)
    {
        "cafe_id":          "2138163704",
        "business_id":      "509345",
        "business_type_id": 12,
        "branch_name":      "",
        "name":             "방탈출추리존",
        "address":          "대전 중구 은행동 168-5",
        "area":             "daejeon",
        "site_url":         "https://booking.naver.com/booking/12/bizes/509345",
    },
    # 러시아워방탈출카페 3호점 광주 (네이버 예약)
    {
        "cafe_id":          "2102768222",
        "business_id":      "1370021",
        "business_type_id": 12,
        "branch_name":      "3호점",
        "name":             "러시아워방탈출",
        "address":          "광주 동구 황금동 23-4",
        "area":             "gwangju",
        "site_url":         "https://booking.naver.com/booking/12/bizes/1370021",
    },
    # 러시아워방탈출카페 로드맨션 광주 (네이버 예약)
    {
        "cafe_id":          "942247508",
        "business_id":      "540364",
        "business_type_id": 12,
        "branch_name":      "로드맨션",
        "name":             "러시아워방탈출",
        "address":          "광주 북구 용봉동 159-13",
        "area":             "gwangju",
        "site_url":         "https://booking.naver.com/booking/12/bizes/540364",
    },
    # 카타르시스이스케이프 서면점 부산 (네이버 예약)
    {
        "cafe_id":          "1358303820",
        "business_id":      "737799",
        "business_type_id": 12,
        "branch_name":      "서면점",
        "name":             "카타르시스이스케이프",
        "address":          "부산 부산진구 부전동 187-10",
        "area":             "busan",
        "site_url":         "https://booking.naver.com/booking/12/bizes/737799",
    },
    # 판타지아방탈출카페 광주 (네이버 예약)
    {
        "cafe_id":          "100018735",
        "business_id":      "795803",
        "business_type_id": 12,
        "branch_name":      "",
        "name":             "판타지아방탈출카페",
        "address":          "광주 북구 용봉동 153-9",
        "area":             "gwangju",
        "site_url":         "https://booking.naver.com/booking/12/bizes/795803",
    },
    # 하이드앤시크 홍대점 / 위드방탈출카페 (withescaper.com)
    {
        "cafe_id":          "554838835",
        "business_id":      "594531",
        "business_type_id": 12,
        "branch_name":      "홍대점",
        "name":             "하이드앤시크",
        "address":          "서울 마포구 동교동 203-57",
        "area":             "hongdae",
        "site_url":         "http://withescaper.com",
        "normalize_theme":  True,  # "[N월 예약]" 제거
    },
    # 에피소드방탈출 강남점 (epsd.co.kr - 네이버 예약)
    {
        "cafe_id":          "1277196871",
        "business_id":      "704325",
        "business_type_id": 12,
        "branch_name":      "강남점",
        "name":             "에피소드방탈출",
        "address":          "서울 강남구 강남대로98길 8",
        "area":             "gangnam",
        "site_url":         "https://www.epsd.co.kr",
    },
    # 인스테이지 방탈출 춘천 (네이버 예약)
    {
        "cafe_id":          "1415278100",
        "business_id":      "891433",
        "business_type_id": 12,
        "branch_name":      "",
        "name":             "인스테이지방탈출",
        "address":          "강원 춘천시 서부대성로 196 3층",
        "area":             "gangwon",
        "site_url":         "https://booking.naver.com/booking/12/bizes/891433",
    },
    # 더패닉방탈출카페 포항 (네이버 예약, bizTypeId=10)
    {
        "cafe_id":          "1266197087",
        "business_id":      "52738",
        "business_type_id": 10,
        "branch_name":      "",
        "name":             "더패닉방탈출카페",
        "address":          "경북 포항시 북구 대흥동 605-2",
        "area":             "gyeongbuk",
        "site_url":         "https://booking.naver.com/booking/10/bizes/52738",
    },
]

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Content-Type": "application/json",
    "Origin": NAVER_BOOKING_URL,
    "Referer": NAVER_BOOKING_URL + "/",
    "Accept": "application/json",
}

# 이름에 이 문자열이 포함된 아이템은 중복(이벤트전용 등) 처리 → 스킵
_SKIP_KEYWORDS = ["오전이벤트", "이벤트전용", "이벤트 전용", "오전할인", "이벤트"]


def _normalize_theme_name(name: str) -> str:
    """
    월별 bizItem 접두/접미 제거.
    - "[N월] 테마명" → "테마명"
    - "테마명 [N월 예약]" → "테마명"
    - "테마명 [N월]" → "테마명"
    """
    # 앞쪽 "[N월] " 패턴 제거
    name = re.sub(r"^\[\d+월\]\s*", "", name)
    # 뒤쪽 " [N월...]" 패턴 제거
    name = re.sub(r"\s*\[\d+월[^\]]*\]\s*$", "", name)
    return name.strip()


def _graphql(query: str, variables: dict) -> dict:
    payload = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(GRAPHQL_URL, data=payload, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"  [WARN] GraphQL 요청 실패: {e}")
        return {}


def _fetch_biz_items(business_id: str) -> list[dict]:
    """지점의 모든 테마(bizItem) 목록 반환."""
    q = """
    query bizItems($bizItemsParams: BizItemsParams) {
      bizItems(input: $bizItemsParams) {
        businessId bizItemId name
      }
    }
    """
    data = _graphql(q, {"bizItemsParams": {"businessId": business_id}})
    return data.get("data", {}).get("bizItems", [])


def _fetch_hourly_slots(business_id: str, biz_item_id: str, target_date: date, business_type_id: int = 12) -> list[dict]:
    """특정 날짜의 시간별 슬롯 반환."""
    date_str = target_date.strftime("%Y-%m-%dT00:00:00")
    q = """
    query schedule($scheduleParams: ScheduleParams) {
      schedule(input: $scheduleParams) {
        bizItemSchedule {
          hourly {
            unitStartTime
            unitBookingCount
            unitStock
          }
        }
      }
    }
    """
    data = _graphql(q, {
        "scheduleParams": {
            "businessId": business_id,
            "bizItemId": biz_item_id,
            "businessTypeId": business_type_id,
            "startDateTime": date_str,
            "endDateTime": date_str,
        }
    })
    return (
        data.get("data", {})
        .get("schedule", {})
        .get("bizItemSchedule", {})
        .get("hourly", []) or []
    )


# ── DB 동기화 ──────────────────────────────────────────────────────────────────

def sync_one_branch(branch: dict, days: int) -> int:
    db = get_db()
    cafe_id = branch["cafe_id"]
    business_id = branch["business_id"]
    branch_name = branch["branch_name"]
    do_normalize = branch.get("normalize_theme", False)

    # 카페 meta upsert
    upsert_cafe(db, cafe_id, {
        "name":        branch["name"],
        "branch_name": branch_name,
        "address":     branch["address"],
        "area":        branch["area"],
        "website_url": branch["site_url"],
        "engine":      "naver_booking",
        "crawled":     True,
        "is_active":   True,
    })
    print(f"  [UPSERT] 카페: {branch['name']} {branch_name} (id={cafe_id})")

    # 테마 목록 가져오기
    biz_items = _fetch_biz_items(business_id)
    time.sleep(REQUEST_DELAY)

    # 이벤트전용 아이템 필터링
    regular_items = [
        item for item in biz_items
        if not any(kw in item.get("name", "") for kw in _SKIP_KEYWORDS)
    ]
    print(f"  테마: {len(regular_items)}개 (전체 {len(biz_items)}개 중 이벤트전용 제외)")

    if not regular_items:
        print(f"  [{branch_name}] 테마 없음, 건너뜀.")
        return 0

    # 테마 upsert & theme_doc_id 맵
    biz_item_to_doc: dict[str, str] = {}
    for item in regular_items:
        biz_item_id = item["bizItemId"]
        raw_name = item["name"].strip()
        theme_name = _normalize_theme_name(raw_name) if do_normalize else raw_name
        doc_id = get_or_create_theme(db, cafe_id, theme_name, {
            "poster_url": None,
            "is_active":  True,
        })
        biz_item_to_doc[biz_item_id] = doc_id
        print(f"  [UPSERT] 테마: {theme_name}")

    # 스케줄 수집
    today = date.today()
    crawled_at = datetime.now()
    date_themes: dict[str, dict] = {}
    booking_base = f"{NAVER_BOOKING_URL}/booking/12/bizes/{business_id}"

    for i in range(days + 1):
        target_date = today + timedelta(days=i)
        date_str = target_date.strftime("%Y-%m-%d")
        avail = full = 0

        for item in regular_items:
            biz_item_id = item["bizItemId"]
            doc_id = biz_item_to_doc[biz_item_id]
            booking_url = f"{booking_base}/items/{biz_item_id}"

            slots = _fetch_hourly_slots(business_id, biz_item_id, target_date, branch.get("business_type_id", 12))
            time.sleep(REQUEST_DELAY)

            for slot in slots:
                # unitStartTime: "YYYY-MM-DD HH:MM:SS" (KST)
                unit_time = slot.get("unitStartTime", "")
                if not unit_time or len(unit_time) < 16:
                    continue
                try:
                    time_part = unit_time[11:16]  # "HH:MM"
                    hh, mm = int(time_part[:2]), int(time_part[3:5])
                except Exception:
                    continue

                slot_dt = datetime(
                    target_date.year, target_date.month, target_date.day, hh, mm
                )
                if slot_dt <= datetime.now():
                    continue

                count = slot.get("unitBookingCount", 0)
                stock = slot.get("unitStock", 1)
                is_available = count < stock
                status = "available" if is_available else "full"

                date_themes.setdefault(date_str, {}).setdefault(
                    doc_id, {"slots": []}
                )["slots"].append({
                    "time":        f"{hh:02d}:{mm:02d}",
                    "status":      status,
                    "booking_url": booking_url if is_available else None,
                })
                if is_available:
                    avail += 1
                else:
                    full += 1

        print(f"  {date_str}: 가능 {avail} / 마감 {full}")

    # Firestore upsert
    known_hashes = load_cafe_hashes(db, cafe_id)
    new_hashes: dict[str, str] = {}
    writes = 0

    for date_str, themes in sorted(date_themes.items()):
        h = upsert_cafe_date_schedules(
            db, date_str, cafe_id, themes, crawled_at,
            known_hash=known_hashes.get(date_str),
        )
        if h:
            new_hashes[date_str] = h
            writes += 1

    if new_hashes:
        today_str = today.isoformat()
        save_cafe_hashes(db, cafe_id, {
            k: v for k, v in {**known_hashes, **new_hashes}.items()
            if k >= today_str
        })

    print(f"  스케줄 동기화: {writes}개 날짜 작성")
    return writes


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main(run_schedule: bool = True, days: int = 14) -> None:
    print("=" * 60)
    print("이스케이프탑 → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)

    for branch in BRANCHES:
        print(f"\n[ {branch['branch_name']} ] 동기화")
        try:
            sync_one_branch(branch, days=days if run_schedule else 0)
        except Exception as e:
            print(f"  [ERROR] {branch['branch_name']} 실패: {e}")

    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="이스케이프탑 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
