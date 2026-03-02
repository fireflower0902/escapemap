"""
스튜디오이에스씨 (Studio ESC) 테마 + 스케줄 DB 동기화 스크립트.

사이트: https://studioesc.co.kr/
플랫폼: sinbiweb PHP CMS

API:
  1) 세션 획득: GET https://studioesc.co.kr/ → 302 → /layout/res/home.php?go=main
  2) 날짜별 예약 현황: GET https://studioesc.co.kr/layout/res/home.php?go=rev.make&rev_days=YYYY-MM-DD
     HTML 응답: div.theme_box 단위로 테마별 슬롯 정보
     - span.possible  → 예약 가능 (a[href] = 예약 링크)
     - span.impossible → 예약 마감
     - 해당 날짜에 theme_box가 없으면 예약 미오픈 → 건너뜀

테마 (2026-03-02 기준):
  - 검은마법사 (The Dark Enchanter)
  - 하얀마법사 (The Pure Enchanter)

cafe_id: 1908100709

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_studioesc_db.py
  uv run python scripts/sync_studioesc_db.py --no-schedule
  uv run python scripts/sync_studioesc_db.py --days 14
"""

import asyncio
import ssl
import sys
import time
import urllib.request
import urllib.parse
from datetime import date, datetime, time as dtime, timedelta
from http.cookiejar import CookieJar
from pathlib import Path

# SSL 검증 비활성화 (macOS Python 기본 인증서 문제 우회)
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from bs4 import BeautifulSoup
from sqlalchemy import select

from app.database import AsyncSessionLocal, engine, Base
from app.models.cafe import Cafe
from app.models.theme import Theme
from app.models.schedule import Schedule

CAFE_ID = "1908100709"
BASE_URL = "https://studioesc.co.kr/layout/res/home.php"
RESERVE_URL = BASE_URL + "?go=rev.make"
SITE_ROOT = "https://studioesc.co.kr/"
REQUEST_DELAY = 1.0


# ── HTTP 유틸 ───────────────────────────────────────────────────────────────────

def _make_opener() -> urllib.request.OpenerDirector:
    """쿠키 핸들러 + SSL 우회가 포함된 opener 생성."""
    cj = CookieJar()
    https_handler = urllib.request.HTTPSHandler(context=_SSL_CTX)
    return urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cj),
        https_handler,
    )


def _get_session(opener: urllib.request.OpenerDirector) -> bool:
    """루트 페이지 GET → PHPSESSID 세션 쿠키 획득."""
    req = urllib.request.Request(
        SITE_ROOT,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9",
        },
    )
    try:
        with opener.open(req, timeout=15) as r:
            r.read()
        print(f"  세션 획득 완료 (status={r.status})")
        return True
    except Exception as e:
        print(f"  [ERROR] 세션 획득 실패: {e}")
        return False


def _fetch_reserve_page(opener: urllib.request.OpenerDirector, target_date: date) -> str:
    """날짜별 예약 페이지 HTML 반환."""
    date_str = target_date.strftime("%Y-%m-%d")
    url = f"{RESERVE_URL}&rev_days={date_str}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9",
            "Referer": SITE_ROOT,
        },
    )
    try:
        with opener.open(req, timeout=15) as r:
            return r.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"  [WARN] 페이지 로드 실패 {date_str}: {e}")
        return ""


# ── HTML 파싱 ──────────────────────────────────────────────────────────────────

def _parse_reserve_page(html: str, target_date: date) -> list[dict]:
    """
    예약 페이지 HTML에서 테마별 슬롯 파싱.

    반환: [
      {
        "theme_name": str,
        "poster_url": str | None,
        "slots": [{"time": dtime, "status": str, "booking_url": str | None}]
      }, ...
    ]
    """
    soup = BeautifulSoup(html, "html.parser")
    boxes = soup.select(".theme_box")
    if not boxes:
        return []

    date_str = target_date.strftime("%Y-%m-%d")
    results = []

    for box in boxes:
        h3 = box.select_one("h3.h3_theme")
        if not h3:
            continue
        theme_name = h3.text.strip()

        # 포스터 이미지 (../../file/theme/N_a.jpg → 절대 경로로 변환)
        img_tag = box.select_one(".theme_pic img")
        poster_url = None
        if img_tag and img_tag.get("src"):
            raw_src = img_tag["src"].split("?")[0]  # 쿼리스트링 제거
            if raw_src.startswith("../../"):
                poster_url = "https://studioesc.co.kr/" + raw_src[6:]
            elif raw_src.startswith("http"):
                poster_url = raw_src

        slots = []
        for li in box.select("ul.reserve_Time li"):
            time_span = li.select_one("span.time")
            if not time_span:
                continue
            time_str = time_span.text.strip()  # "HH:MM" or "HH:MM "
            try:
                hh, mm = map(int, time_str.split(":"))
                time_obj = dtime(hh, mm)
            except Exception:
                continue

            possible = li.select_one("span.possible")
            impossible = li.select_one("span.impossible")
            a_tag = li.select_one("a")

            if possible:
                status = "available"
                href = a_tag.get("href", "") if a_tag else ""
                if href:
                    # 상대 경로 → 절대 경로
                    booking_url = (
                        "https://studioesc.co.kr/layout/res/" + href
                        if not href.startswith("http")
                        else href
                    )
                else:
                    booking_url = RESERVE_URL + f"&rev_days={date_str}"
            elif impossible:
                status = "full"
                booking_url = None
            else:
                # 알 수 없는 상태 → 건너뜀
                continue

            slots.append({
                "time": time_obj,
                "status": status,
                "booking_url": booking_url,
            })

        if slots:
            results.append({
                "theme_name": theme_name,
                "poster_url": poster_url,
                "slots": slots,
            })

    return results


# ── DB 동기화 ───────────────────────────────────────────────────────────────────

async def sync_themes(themes_info: list[dict]) -> dict[str, int]:
    """
    테마를 DB에 upsert.
    반환: {테마명 → db theme.id}
    """
    name_to_id: dict[str, int] = {}
    added = updated = 0

    async with AsyncSessionLocal() as session:
        cafe = await session.get(Cafe, CAFE_ID)
        if not cafe:
            print(f"  [ERROR] cafe {CAFE_ID} DB 미존재 — 스크립트를 중단합니다.")
            return {}

        for info in themes_info:
            theme_name = info["theme_name"]
            poster_url = info.get("poster_url")

            result = await session.execute(
                select(Theme).where(
                    Theme.cafe_id == CAFE_ID,
                    Theme.name == theme_name,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                if poster_url:
                    existing.poster_url = poster_url
                existing.is_active = True
                name_to_id[theme_name] = existing.id
                updated += 1
                print(f"  [UPD] {theme_name} (id={existing.id})")
            else:
                theme = Theme(
                    cafe_id=CAFE_ID,
                    name=theme_name,
                    description=None,
                    difficulty=None,
                    duration_min=None,
                    poster_url=poster_url,
                    is_active=True,
                )
                session.add(theme)
                await session.flush()
                name_to_id[theme_name] = theme.id
                added += 1
                print(f"  [NEW] {theme_name} (id={theme.id})")

        await session.commit()

    print(f"\n  테마 동기화 완료: {added}개 추가 / {updated}개 갱신")
    return name_to_id


async def sync_schedules(
    opener: urllib.request.OpenerDirector,
    name_to_id: dict[str, int],
    days: int = 14,
):
    """스케줄을 schedule 테이블에 upsert (오늘~days일 후)."""
    today = date.today()
    target_dates = [today + timedelta(days=i) for i in range(days + 1)]
    crawled_at = datetime.now()
    added = 0

    async with AsyncSessionLocal() as session:
        for target_date in target_dates:
            html = _fetch_reserve_page(opener, target_date)
            time.sleep(REQUEST_DELAY)

            parsed = _parse_reserve_page(html, target_date)
            date_str = target_date.strftime("%Y-%m-%d")

            if not parsed:
                print(f"  {date_str}: 예약 미오픈 — 건너뜀")
                continue

            avail = full = 0
            for theme_data in parsed:
                theme_name = theme_data["theme_name"]
                db_theme_id = name_to_id.get(theme_name)
                if db_theme_id is None:
                    print(f"  [WARN] DB에 없는 테마: {theme_name!r}")
                    continue

                for slot in theme_data["slots"]:
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

                    if status == "available":
                        avail += 1
                    else:
                        full += 1

            print(f"  {date_str}: 가능 {avail}개 / 마감 {full}개")

        await session.commit()

    print(f"\n  스케줄 동기화 완료: {added}개 레코드 추가")


# ── 메인 ────────────────────────────────────────────────────────────────────────

async def main(run_schedule: bool = True, days: int = 14):
    print("=" * 60)
    print("스튜디오이에스씨 (Studio ESC) → DB 동기화")
    print("=" * 60)

    from app.models import cafe, theme, schedule, user, alert  # noqa
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    opener = _make_opener()

    print("\n[ 0단계 ] 세션 획득")
    if not _get_session(opener):
        print("세션 획득 실패, 종료.")
        return
    time.sleep(REQUEST_DELAY)

    # 테마 목록을 오늘 날짜 페이지에서 추출
    print("\n[ 1단계 ] 테마 목록 추출 (오늘 날짜 기준)")
    today = date.today()
    html_today = _fetch_reserve_page(opener, today)
    time.sleep(REQUEST_DELAY)
    parsed_today = _parse_reserve_page(html_today, today)

    if not parsed_today:
        # 오늘 미오픈이면 가장 가까운 오픈 날짜에서 추출
        print("  오늘 미오픈 → 다음 날짜 시도")
        for i in range(1, 8):
            next_date = today + timedelta(days=i)
            html = _fetch_reserve_page(opener, next_date)
            time.sleep(REQUEST_DELAY)
            parsed_today = _parse_reserve_page(html, next_date)
            if parsed_today:
                print(f"  {next_date} 기준 테마 {len(parsed_today)}개 발견")
                break

    if not parsed_today:
        print("  테마 정보를 찾을 수 없음, 종료.")
        return

    for t in parsed_today:
        print(f"  테마: {t['theme_name']!r} | poster={t['poster_url']}")

    print("\n[ 2단계 ] 테마 DB 동기화")
    name_to_id = await sync_themes(parsed_today)
    if not name_to_id:
        print("테마 동기화 실패, 종료.")
        return

    if run_schedule:
        print(f"\n[ 3단계 ] 스케줄 동기화 (오늘~{days}일 후)")
        await sync_schedules(opener, name_to_id, days=days)

    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="스튜디오이에스씨 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    asyncio.run(main(run_schedule=not args.no_schedule, days=args.days))
