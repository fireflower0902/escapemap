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
  26 → 671151862   건대점
  40 → 1559912469  해운대 블루오션스테이션
  43 → 1397923384  서면탄탄스트리트점
   1 → 27495854    궁동직영점 (대전)
   2 → 27523824    은행직영점 (대전)
  24 → 164781377   프라임청주점
  27 → 1850589033  평택점
  30 → 1834906043  동탄프라임
  23 → 870806933   화정점

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_masterkey_db.py
  uv run python scripts/sync_masterkey_db.py --no-schedule
  uv run python scripts/sync_masterkey_db.py --days 3
  uv run python scripts/sync_masterkey_db.py --bid 35   # 특정 지점만
"""

import asyncio
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
from sqlalchemy import select

from app.database import AsyncSessionLocal, engine, Base
from app.models.cafe import Cafe
from app.models.theme import Theme
from app.models.schedule import Schedule

API_URL = "http://www.master-key.co.kr/booking/booking_list_new"
BOOKING_URL_TEMPLATE = "http://www.master-key.co.kr/booking/bk_detail?bid={bid}"
POSTER_URL_TEMPLATE = "http://www.master-key.co.kr/upload/room/{room_id}_img1.gif"
REQUEST_DELAY = 1.0

# bid(마스터키 지점 ID) → DB cafe_id 매핑
# DB에 없는 지점(bid=31 노원, 21 잠실, 18 천안프리미엄, 13 안양, 7 천안두정, 44 서면오리진, 11 홍대)은 제외
SHOP_MAP: dict[int, str] = {
    35: "1466171651",  # 플레이포인트랩 강남점
    41: "1987907479",  # 노바홍대점
    26: "671151862",   # 건대점
    40: "1559912469",  # 해운대 블루오션스테이션
    43: "1397923384",  # 서면탄탄스트리트점
    1:  "27495854",    # 궁동직영점 (대전)
    2:  "27523824",    # 은행직영점 (대전)
    24: "164781377",   # 프라임청주점
    27: "1850589033",  # 평택점
    30: "1834906043",  # 동탄프라임
    23: "870806933",   # 화정점
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

async def sync_themes(bids: list[int]) -> dict[tuple[int, str], int]:
    """마스터키 전 지점 테마를 DB에 upsert.

    오늘~6일 후 데이터를 스캔해 각 지점의 활성 테마를 모두 발견한 뒤 upsert.

    반환: {(bid, room_id) → db theme.id}
    """
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

    # DB upsert
    theme_map: dict[tuple[int, str], int] = {}
    added = updated = 0

    async with AsyncSessionLocal() as session:
        for bid, themes_by_room in discovered.items():
            cafe_id = SHOP_MAP[bid]
            cafe = await session.get(Cafe, cafe_id)
            if not cafe:
                print(f"  [ERROR] cafe {cafe_id} DB 미존재 — bid={bid} 건너뜀")
                continue

            for room_id, info in themes_by_room.items():
                name = info["name"]
                poster_url = info["poster_url"]
                duration_min = info["duration_min"]

                result = await session.execute(
                    select(Theme).where(
                        Theme.cafe_id == cafe_id,
                        Theme.name == name,
                    )
                )
                existing = result.scalar_one_or_none()

                if existing:
                    existing.poster_url = poster_url or existing.poster_url
                    existing.duration_min = duration_min or existing.duration_min
                    existing.is_active = True
                    theme_map[(bid, room_id)] = existing.id
                    updated += 1
                else:
                    theme = Theme(
                        cafe_id=cafe_id,
                        name=name,
                        description=None,
                        difficulty=None,
                        duration_min=duration_min,
                        poster_url=poster_url,
                        is_active=True,
                    )
                    session.add(theme)
                    await session.flush()
                    theme_map[(bid, room_id)] = theme.id
                    added += 1

                print(f"  {'[NEW]' if not existing else '[UPD]'} {name} ({cafe.name}) room_id={room_id}")

        await session.commit()

    print(f"\n  테마 동기화 완료: {added}개 추가 / {updated}개 갱신")
    return theme_map


async def sync_schedules(bids: list[int], theme_map: dict[tuple[int, str], int], days: int = 6):
    """마스터키 스케줄을 schedule 테이블에 upsert (오늘~days일 후)."""
    today = date.today()
    target_dates = [today + timedelta(days=i) for i in range(days + 1)]
    crawled_at = datetime.now()
    added = 0

    async with AsyncSessionLocal() as session:
        for bid in bids:
            booking_url_base = BOOKING_URL_TEMPLATE.format(bid=bid)

            for target_date in target_dates:
                rows = _fetch_raw(bid, target_date)
                time.sleep(REQUEST_DELAY)

                for r in rows:
                    room_id = r["room_id"] or r["name"]
                    db_theme_id = theme_map.get((bid, room_id))
                    if db_theme_id is None:
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

                        result = await session.execute(
                            select(Schedule).where(
                                Schedule.theme_id == db_theme_id,
                                Schedule.date == target_date,
                                Schedule.time_slot == time_obj,
                            ).order_by(Schedule.crawled_at.desc()).limit(1)
                        )
                        existing = result.scalar_one_or_none()

                        if existing:
                            if existing.status != status:
                                session.add(Schedule(
                                    theme_id=db_theme_id,
                                    date=target_date,
                                    time_slot=time_obj,
                                    status=status,
                                    available_slots=None,
                                    total_slots=None,
                                    booking_url=booking_url,
                                    crawled_at=crawled_at,
                                ))
                                added += 1
                        else:
                            session.add(Schedule(
                                theme_id=db_theme_id,
                                date=target_date,
                                time_slot=time_obj,
                                status=status,
                                available_slots=None,
                                total_slots=None,
                                booking_url=booking_url,
                                crawled_at=crawled_at,
                            ))
                            added += 1

            print(f"  bid={bid} 완료")

        await session.commit()

    print(f"\n  스케줄 동기화 완료: {added}개 레코드 추가")


async def main(bids: list[int], run_schedule: bool = True, days: int = 6):
    print("=" * 60)
    print("마스터키(플레이포인트랩) → DB 동기화")
    print(f"대상 bid: {bids}")
    print("=" * 60)

    from app.models import cafe, theme, schedule, user, alert  # noqa
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("\n[ 1단계 ] 테마 동기화 (오늘~6일 스캔)")
    theme_map = await sync_themes(bids)
    print(f"  (bid, room_id) 매핑 수: {len(theme_map)}")

    if run_schedule and theme_map:
        print(f"\n[ 2단계 ] 스케줄 동기화 (오늘~{days}일 후)")
        await sync_schedules(bids, theme_map, days=days)

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

    asyncio.run(main(bids=target_bids, run_schedule=not args.no_schedule, days=args.days))
