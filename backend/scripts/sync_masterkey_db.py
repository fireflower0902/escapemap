"""
마스터키(플레이포인트랩) 전 지점 테마 + 스케줄 DB 동기화 스크립트.

사이트: http://www.master-key.co.kr/
플랫폼: 자체 개발 PHP 예약 시스템

API:
  POST http://www.master-key.co.kr/booking/booking_list_new
  Body: date=YYYY-MM-DD&store={bid}&room=
  응답: HTML (div.box2-inner 단위로 테마별 슬롯 제공)
  - p.col.true  → 예약가능
  - p.col.false → 예약완료
  - a 태그 텍스트(span 제거) → "HH:MM" 형식 시간
  - img[src] → /upload/room/{room_id}_img1.gif (room_id는 테마 고유 식별자)
  - div.hashtags → "#감성 #70분" 형식 (소요 시간 추출 가능)

지점 매핑 (bid → DB cafe_id):
  35 → 1466171651  플레이포인트랩 강남점
  41 → 1987907479  노바홍대점
  11 → 1462418270  플레이포인트랩 홍대점
  26 → 671151862   건대점
  20 → 751793807   홍대상수점
  32 → 97734177    마스터키프라임 신촌퍼플릭
  40 → 1559912469  해운대 블루오션스테이션
  43 → 1397923384  서면탄탄스트리트점
  44 → 886826713   플레이포인트랩 서면점
   1 → 27495854    궁동직영점 (대전)
   2 → 27523824    은행직영점 (대전)
  24 → 164781377   프라임청주점
  27 → 1850589033  평택점
  30 → 1834906043  동탄프라임
  23 → 870806933   화정점
   8 → 1292714537  전주고사점    (전주시 완산구 전주객사5길 30-2)
  12 → 1727885052  익산점        (익산시 동서로19길 74-1)
  14 → 2039293420  동성로2호점   (대구 중구 동성로5길 43)
  21 → 967129600   플레이포인트랩 잠실점

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_masterkey_db.py
  uv run python scripts/sync_masterkey_db.py --no-schedule
  uv run python scripts/sync_masterkey_db.py --days 3
  uv run python scripts/sync_masterkey_db.py --bid 35   # 특정 지점만
"""

import re
import sys
import time
import urllib.request
import urllib.parse
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from bs4 import BeautifulSoup

from app.config import settings
from app.firestore_db import init_firestore, get_db, upsert_cafe, get_or_create_theme, upsert_cafe_date_schedules, load_cafe_hashes, save_cafe_hashes

API_URL = "http://www.master-key.co.kr/booking/booking_list_new"
BOOKING_URL_TEMPLATE = "http://www.master-key.co.kr/booking/bk_detail?bid={bid}"
POSTER_URL_TEMPLATE = "http://www.master-key.co.kr/upload/room/{room_id}_img1.gif"
REQUEST_DELAY = 1.0

# bid(마스터키 지점 ID) → DB cafe_id 매핑
# DB에 없는 지점(bid=31 노원, 18 천안프리미엄, 13 안양)은 제외
SHOP_MAP: dict[int, str] = {
    35: "1466171651",  # 플레이포인트랩 강남점
    41: "1987907479",  # 노바홍대점
    11: "1462418270",  # 플레이포인트랩 홍대점
    26: "671151862",   # 건대점
    20: "751793807",   # 홍대상수점
    32: "97734177",    # 마스터키프라임 신촌퍼플릭
    40: "1559912469",  # 해운대 블루오션스테이션
    43: "1397923384",  # 서면탄탄스트리트점
    44: "886826713",   # 플레이포인트랩 서면점
    1:  "27495854",    # 궁동직영점 (대전)
    2:  "27523824",    # 은행직영점 (대전)
    24: "164781377",   # 프라임청주점
    27: "1850589033",  # 평택점
    30: "1834906043",  # 동탄프라임
    23: "870806933",   # 화정점
    21: "967129600",   # 플레이포인트랩 잠실점
    8:  "1292714537",  # 전주고사점
    12: "1727885052",  # 익산점
    14: "2039293420",  # 동성로2호점 (대구 중구 동성로5길 43)
    7:  "2030700012",  # 플레이포인트랩 두정점 (충남 천안시 서북구)
}

# 새로 추가된 지점의 카페 메타 (Firestore에 카페 문서가 없는 경우 자동 생성)
CAFE_META: dict[int, dict] = {
    20: {
        "name":        "마스터키",
        "branch_name": "홍대상수점",
        "address":     "서울 마포구 상수동 317-4 상수동오피스텔 지하1층",
        "area":        "hongdae",
        "phone":       None,
        "website_url": "http://www.master-key.co.kr/booking/bk_detail?bid=20",
        "engine":      "masterkey",
        "crawled":     True,
        "lat":         None,
        "lng":         None,
        "is_active":   True,
    },
    32: {
        "name":        "마스터키프라임",
        "branch_name": "신촌퍼플릭",
        "address":     "서울 서대문구 창천동 52-130 지하1층",
        "area":        "sinchon",
        "phone":       None,
        "website_url": "http://www.master-key.co.kr/booking/bk_detail?bid=32",
        "engine":      "masterkey",
        "crawled":     True,
        "lat":         None,
        "lng":         None,
        "is_active":   True,
    },
    44: {
        "name":        "플레이포인트랩",
        "branch_name": "서면점",
        "address":     "부산 부산진구 서면로68번길 18",
        "area":        "busan",
        "phone":       None,
        "website_url": "http://www.master-key.co.kr/booking/bk_detail?bid=44",
        "engine":      "masterkey",
        "crawled":     True,
        "lat":         None,
        "lng":         None,
        "is_active":   True,
    },
    8: {
        "name":        "마스터키",
        "branch_name": "전주고사점",
        "address":     "전북특별자치도 전주시 완산구 전주객사5길 30-2",
        "area":        "etc",
        "phone":       None,
        "website_url": "http://www.master-key.co.kr/booking/bk_detail?bid=8",
        "engine":      "masterkey",
        "crawled":     True,
        "lat":         None,
        "lng":         None,
        "is_active":   True,
    },
    12: {
        "name":        "마스터키",
        "branch_name": "익산점",
        "address":     "전북특별자치도 익산시 동서로19길 74-1",
        "area":        "etc",
        "phone":       None,
        "website_url": "http://www.master-key.co.kr/booking/bk_detail?bid=12",
        "engine":      "masterkey",
        "crawled":     True,
        "lat":         None,
        "lng":         None,
        "is_active":   True,
    },
    14: {
        "name":        "마스터키",
        "branch_name": "동성로2호점",
        "address":     "대구 중구 동성로5길 43",
        "area":        "daegu",
        "phone":       None,
        "website_url": "http://www.master-key.co.kr/booking/bk_detail?bid=14",
        "engine":      "masterkey",
        "crawled":     True,
        "lat":         None,
        "lng":         None,
        "is_active":   True,
    },
    7: {
        "name":        "플레이포인트랩",
        "branch_name": "두정점",
        "address":     "충남 천안시 서북구 두정동",
        "area":        "etc",
        "phone":       None,
        "website_url": "http://www.master-key.co.kr/booking/bk_detail?bid=7",
        "engine":      "masterkey",
        "crawled":     True,
        "lat":         None,
        "lng":         None,
        "is_active":   True,
    },
}


def _fetch_raw(bid: int, target_date: date) -> list[dict]:
    """마스터키 API 호출 → 테마별 슬롯 raw 데이터 반환.

    반환: [
        {
            "room_id": "209",          # 이미지 경로에서 추출한 테마 고유 ID
            "name": "위로",            # 테마명
            "poster_url": "http://...", # 포스터 이미지 URL
            "duration_min": 70,        # 소요 시간 (None이면 정보 없음)
            "slots": [                 # 슬롯 목록
                {"time": dtime(11, 55), "status": "full"},
                {"time": dtime(14, 45), "status": "available"},
            ],
        },
        ...
    ]
    """
    date_str = target_date.strftime("%Y-%m-%d")
    body = urllib.parse.urlencode({
        "date": date_str,
        "store": str(bid),
        "room": "",
    }).encode()
    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": BOOKING_URL_TEMPLATE.format(bid=bid),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"  [WARN] API 오류 bid={bid} date={date_str}: {e}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    results = []

    for box in soup.find_all("div", class_="box2-inner"):
        # 테마명
        title_div = box.find("div", class_="title")
        if not title_div:
            continue
        name = title_div.get_text(strip=True)
        if not name:
            continue

        # room_id (이미지 경로 /upload/room/{room_id}_img1.gif에서 추출)
        img = box.find("img")
        room_id = None
        poster_url = None
        if img:
            m = re.search(r"/(\d+)_img", img.get("src", ""))
            if m:
                room_id = m.group(1)
                poster_url = POSTER_URL_TEMPLATE.format(room_id=room_id)

        # 소요 시간 (#70분 형식에서 추출)
        duration_min = None
        hashtags_div = box.find("div", class_="hashtags")
        if hashtags_div:
            m = re.search(r"(\d+)분", hashtags_div.get_text())
            if m:
                duration_min = int(m.group(1))

        # 슬롯 파싱
        slots = []
        for p in box.find_all("p", class_="col"):
            a_tag = p.find("a")
            span_tag = p.find("span")
            if not a_tag:
                continue

            full_text = a_tag.get_text(strip=True)
            span_text = span_tag.get_text(strip=True) if span_tag else ""
            time_str = full_text.replace(span_text, "").strip()  # "HH:MM"

            if not re.match(r"^\d{1,2}:\d{2}$", time_str):
                continue

            hh, mm = map(int, time_str.split(":"))
            classes = p.get("class", [])
            status = "available" if "true" in classes else "full"
            slots.append({"time": dtime(hh, mm), "status": status})

        results.append({
            "room_id": room_id,
            "name": name,
            "poster_url": poster_url,
            "duration_min": duration_min,
            "slots": slots,
        })

    return results


# ── DB 동기화 ──────────────────────────────────────────────────────────────────

def sync_themes(bids: list[int]) -> dict[tuple[int, str], str]:
    """마스터키 전 지점 테마를 Firestore에 upsert.

    오늘~6일 후 데이터를 스캔해 각 지점의 활성 테마를 모두 발견한 뒤 upsert.

    반환: {(bid, room_id) → theme_doc_id}
    """
    db = get_db()

    # 각 bid별 발견된 테마 수집: {bid: {room_id: {name, poster_url, duration_min}}}
    discovered: dict[int, dict[str, dict]] = {bid: {} for bid in bids}

    today = date.today()
    scan_dates = [today + timedelta(days=i) for i in range(7)]

    print("  테마 발견 스캔 중...")
    for bid in bids:
        for target_date in scan_dates:
            rows = _fetch_raw(bid, target_date)
            for r in rows:
                room_id = r["room_id"] or r["name"]  # room_id 없으면 이름으로 대체
                if room_id not in discovered[bid]:
                    discovered[bid][room_id] = {
                        "name": r["name"],
                        "poster_url": r["poster_url"],
                        "duration_min": r["duration_min"],
                    }
            time.sleep(REQUEST_DELAY)
        bid_count = len(discovered[bid])
        print(f"    bid={bid} → {bid_count}개 테마 발견")

    # Firestore upsert
    theme_map: dict[tuple[int, str], str] = {}

    for bid, themes_by_room in discovered.items():
        cafe_id = SHOP_MAP[bid]
        # 신규 지점은 카페 메타 먼저 upsert
        if bid in CAFE_META:
            upsert_cafe(db, cafe_id, CAFE_META[bid])
            print(f"  [UPSERT] 카페 메타 bid={bid} (id={cafe_id})")
        cafe_doc = db.collection("cafes").document(cafe_id).get()
        if not cafe_doc.exists:
            print(f"  [ERROR] cafe {cafe_id} Firestore 미존재 — bid={bid} 건너뜀")
            continue

        for room_id, info in themes_by_room.items():
            name = info["name"]
            poster_url = info["poster_url"]
            duration_min = info["duration_min"]

            theme_doc_id = get_or_create_theme(db, cafe_id, name, {
                "difficulty": None,
                "duration_min": duration_min,
                "poster_url": poster_url,
                "is_active": True,
            })
            theme_map[(bid, room_id)] = theme_doc_id
            print(f"  [UPSERT] {name} (cafe={cafe_id}) room_id={room_id}")

    print(f"\n  테마 동기화 완료: {len(theme_map)}개")
    return theme_map


def sync_schedules(bids: list[int], theme_map: dict[tuple[int, str], str], days: int = 6):
    """마스터키 스케줄을 Firestore에 upsert (오늘~days일 후)."""
    db = get_db()
    today = date.today()
    target_dates = [today + timedelta(days=i) for i in range(days + 1)]
    crawled_at = datetime.now()
    writes = 0

    for bid in bids:
        cafe_id = SHOP_MAP[bid]
        booking_url_base = BOOKING_URL_TEMPLATE.format(bid=bid)
        try:
            # {date_str: {theme_doc_id: {"slots": [...]}}}
            date_themes: dict[str, dict] = {}

            for target_date in target_dates:
                rows = _fetch_raw(bid, target_date)
                time.sleep(REQUEST_DELAY)

                date_str = target_date.strftime("%Y-%m-%d")
                for r in rows:
                    room_id = r["room_id"] or r["name"]
                    theme_doc_id = theme_map.get((bid, room_id))
                    if theme_doc_id is None:
                        print(f"  [WARN] theme_map 미존재 bid={bid} room_id={room_id} — 건너뜀")
                        continue

                    for slot in r["slots"]:
                        time_obj = slot["time"]
                        status = slot["status"]

                        slot_dt = datetime(
                            target_date.year, target_date.month, target_date.day,
                            time_obj.hour, time_obj.minute,
                        )
                        if slot_dt <= datetime.now():
                            continue

                        booking_url = booking_url_base if status == "available" else None

                        date_themes.setdefault(date_str, {}).setdefault(theme_doc_id, {"slots": []})["slots"].append({
                            "time": f"{time_obj.hour:02d}:{time_obj.minute:02d}",
                            "status": status,
                            "booking_url": booking_url,
                        })

            known_hashes = load_cafe_hashes(db, cafe_id)
            new_hashes: dict[str, str] = {}
            for date_str, themes in date_themes.items():
                h = upsert_cafe_date_schedules(db, date_str, cafe_id, themes, crawled_at,
                                               known_hash=known_hashes.get(date_str))
                if h:
                    new_hashes[date_str] = h
                    writes += 1
            if new_hashes:
                today_str = date.today().isoformat()
                save_cafe_hashes(db, cafe_id, {k: v for k, v in {**known_hashes, **new_hashes}.items() if k >= today_str})

            print(f"  bid={bid} 완료")
        except Exception as e:
            print(f"  [ERROR] bid={bid} (cafe_id={cafe_id}) 스케줄 동기화 실패: {e}")

    print(f"\n  스케줄 동기화 완료: {writes}개 날짜 문서 작성")


def main(bids: list[int], run_schedule: bool = True, days: int = 6):
    print("=" * 60)
    print("마스터키(플레이포인트랩) → DB 동기화")
    print(f"대상 bid: {bids}")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)

    print("\n[ 1단계 ] 테마 동기화 (오늘~6일 스캔)")
    theme_map = sync_themes(bids)
    print(f"  (bid, room_id) 매핑 수: {len(theme_map)}")

    if run_schedule and theme_map:
        print(f"\n[ 2단계 ] 스케줄 동기화 (오늘~{days}일 후)")
        sync_schedules(bids, theme_map, days=days)

    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="마스터키(플레이포인트랩) DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="테마만 동기화, 스케줄 생략")
    parser.add_argument("--days", type=int, default=6, help="오늘 포함 몇 일치 스케줄 수집 (기본 6)")
    parser.add_argument("--bid", type=int, default=None, help="특정 지점 bid만 동기화")
    args = parser.parse_args()

    if args.bid is not None:
        if args.bid not in SHOP_MAP:
            print(f"[ERROR] bid={args.bid}는 SHOP_MAP에 없습니다.")
            print(f"등록된 bid: {list(SHOP_MAP.keys())}")
            sys.exit(1)
        target_bids = [args.bid]
    else:
        target_bids = list(SHOP_MAP.keys())

    main(bids=target_bids, run_schedule=not args.no_schedule, days=args.days)
