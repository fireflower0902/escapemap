"""
마피아카페 강남1호점 테마 + 스케줄 DB 동기화 스크립트.

사이트: https://www.mafiacafe.kr/
API: https://api.realmafia.kr (자체 REST API)

API 엔드포인트:
  GET https://api.realmafia.kr/web/locations
    → [{id, name, address, url, thumbnail}, ...]
  GET https://api.realmafia.kr/web/meetings/calendar
    params: {year, month, locationId}
    → {day_number: [{id, title, date(UTC), isNumberAvailable, currentNumber, maxNumber, thumbnail}, ...]}

Date 파싱:
  - date는 UTC ISO8601 → KST(+9h)로 변환
  - 예: "2026-03-03T06:30:00.000Z" → 2026-03-03 15:30 KST

DB 정보:
  - cafe_id: 1030963843 (강남1호점)
  - location_id: 2

예약 URL: https://www.mafiacafe.kr/program/reservation/{meeting_id}

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_mafiacafe_db.py
  uv run python scripts/sync_mafiacafe_db.py --no-schedule
  uv run python scripts/sync_mafiacafe_db.py --months 2
"""

import asyncio
import json
import ssl
import sys
import time
import urllib.request
import urllib.parse
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select

from app.database import AsyncSessionLocal, engine, Base
from app.models.cafe import Cafe
from app.models.theme import Theme
from app.models.schedule import Schedule

CAFE_ID = "1030963843"   # 강남1호점
LOCATION_ID = 2          # API 상의 location_id
API_BASE = "https://api.realmafia.kr"
SITE_URL = "https://www.mafiacafe.kr"
REQUEST_DELAY = 0.8
KST = timezone(timedelta(hours=9))


# ── HTTP 유틸 ───────────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Authorization": "",
    "Origin": SITE_URL,
    "Referer": SITE_URL + "/",
    "Accept": "application/json",
}


def _get(path: str, params: dict | None = None) -> dict:
    url = API_BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"  [WARN] GET {path} 실패: {e}")
        return {}


# ── API 호출 ────────────────────────────────────────────────────────────────────

def _fetch_calendar(year: int, month: int) -> dict[int, list[dict]]:
    """
    월별 캘린더 조회.
    반환: {day: [meeting, ...]}
    """
    data = _get("/web/meetings/calendar", {"year": year, "month": month, "locationId": LOCATION_ID})
    result: dict[int, list[dict]] = {}
    for day_str, meetings in data.get("data", {}).items():
        result[int(day_str)] = meetings
    return result


def _parse_meeting(meeting: dict) -> dict | None:
    """
    meeting dict → {title, poster_url, date, time, status, booking_url}
    """
    try:
        title = meeting["title"]
        dt_utc = datetime.fromisoformat(meeting["date"].replace("Z", "+00:00"))
        dt_kst = dt_utc.astimezone(KST)
        target_date = dt_kst.date()
        time_obj = dtime(dt_kst.hour, dt_kst.minute)

        is_avail = meeting.get("isNumberAvailable", False)
        status = "available" if is_avail else "full"

        meeting_id = meeting["id"]
        booking_url = f"{SITE_URL}/program/reservation/{meeting_id}" if is_avail else None

        # 포스터 URL
        thumb = meeting.get("thumbnail")
        poster_url = thumb.get("originalPath") if thumb else None

        return {
            "title": title,
            "poster_url": poster_url,
            "date": target_date,
            "time": time_obj,
            "status": status,
            "booking_url": booking_url,
        }
    except Exception as e:
        print(f"  [WARN] 미팅 파싱 실패: {e} — {meeting}")
        return None


# ── DB 동기화 ───────────────────────────────────────────────────────────────────

async def sync_theme(title: str, poster_url: str | None) -> int | None:
    """테마 upsert. 반환: db theme.id"""
    async with AsyncSessionLocal() as session:
        cafe = await session.get(Cafe, CAFE_ID)
        if not cafe:
            print(f"  [ERROR] cafe {CAFE_ID} DB 미존재")
            return None

        result = await session.execute(
            select(Theme).where(Theme.cafe_id == CAFE_ID, Theme.name == title)
        )
        existing = result.scalar_one_or_none()

        if existing:
            if poster_url:
                existing.poster_url = poster_url
            existing.is_active = True
            await session.commit()
            print(f"  [UPD] {title} (id={existing.id})")
            return existing.id
        else:
            theme = Theme(
                cafe_id=CAFE_ID,
                name=title,
                description=None,
                difficulty=None,
                duration_min=150,  # "2시간 30분"
                poster_url=poster_url,
                is_active=True,
            )
            session.add(theme)
            await session.flush()
            tid = theme.id
            await session.commit()
            print(f"  [NEW] {title} (id={tid})")
            return tid


async def sync_schedules(slots: list[dict], theme_id_map: dict[str, int]):
    """슬롯 목록을 schedule 테이블에 upsert."""
    crawled_at = datetime.now()
    added = 0

    async with AsyncSessionLocal() as session:
        for slot in slots:
            title = slot["title"]
            db_theme_id = theme_id_map.get(title)
            if db_theme_id is None:
                continue

            target_date = slot["date"]
            time_obj = slot["time"]
            status = slot["status"]
            booking_url = slot["booking_url"]

            # 과거 시간 건너뜀
            slot_dt = datetime(
                target_date.year, target_date.month, target_date.day,
                time_obj.hour, time_obj.minute,
            )
            if slot_dt <= datetime.now():
                continue

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

        await session.commit()

    print(f"  스케줄 동기화 완료: {added}개 레코드 추가")
    return added


# ── 메인 ────────────────────────────────────────────────────────────────────────

async def main(run_schedule: bool = True, months: int = 2):
    print("=" * 60)
    print("마피아카페 강남1호점 → DB 동기화")
    print("=" * 60)

    from app.models import cafe, theme, schedule, user, alert  # noqa
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 이번 달 ~ months달치 캘린더 수집
    all_slots: list[dict] = []
    theme_id_map: dict[str, int] = {}

    today = date.today()
    months_to_fetch = []
    for i in range(months):
        y = today.year
        m = today.month + i
        if m > 12:
            m -= 12
            y += 1
        months_to_fetch.append((y, m))

    print("\n[ 1단계 ] 캘린더 조회")
    for year, month in months_to_fetch:
        print(f"  {year}년 {month}월...")
        cal = _fetch_calendar(year, month)
        time.sleep(REQUEST_DELAY)

        for day, meetings in cal.items():
            for meeting in meetings:
                slot = _parse_meeting(meeting)
                if slot:
                    all_slots.append(slot)

    print(f"  총 슬롯: {len(all_slots)}개")

    # 고유 테마 목록 추출 (포스터 URL 우선 사용)
    theme_info: dict[str, str | None] = {}
    for slot in all_slots:
        title = slot["title"]
        if title not in theme_info or (slot["poster_url"] and not theme_info[title]):
            theme_info[title] = slot["poster_url"]

    print(f"\n[ 2단계 ] 테마 동기화 ({len(theme_info)}개)")
    for title, poster_url in theme_info.items():
        print(f"  테마: {title!r} | poster={poster_url}")
        db_id = await sync_theme(title, poster_url)
        if db_id:
            theme_id_map[title] = db_id

    if not theme_id_map:
        print("  테마 없음, 종료.")
        return

    if run_schedule:
        print(f"\n[ 3단계 ] 스케줄 동기화")
        # 날짜별 요약
        by_date: dict[str, dict[str, int]] = {}
        for slot in all_slots:
            d = str(slot["date"])
            if d not in by_date:
                by_date[d] = {"available": 0, "full": 0}
            by_date[d][slot["status"]] = by_date[d].get(slot["status"], 0) + 1
        for d in sorted(by_date):
            av = by_date[d]["available"]
            fl = by_date[d]["full"]
            print(f"  {d}: 가능 {av}개 / 마감 {fl}개")

        await sync_schedules(all_slots, theme_id_map)

    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="마피아카페 강남1호점 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--months", type=int, default=2, help="몇 개월치 수집 (기본 2)")
    args = parser.parse_args()
    asyncio.run(main(run_schedule=not args.no_schedule, months=args.months))
