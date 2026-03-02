"""
프랭크의골동품가게 테마 + 스케줄 DB 동기화 스크립트.

사이트: https://thefrank.co.kr/
플랫폼: 신비웹(sinbiweb) PHP CMS 자체 예약 시스템

API:
  POST https://thefrank.co.kr/core/res/rev.make.ajax.php
  Content-Type: application/x-www-form-urlencoded

  act=theme&zizum_num=1&theme_num=&rev_days=YYYY-MM-DD
    → 전체 테마 목록 (HTML)
    → a[href] 속성에서 theme_num 추출
    → span 텍스트에서 테마명 추출

  act=theme_img&theme_num={N}
    → 테마 포스터 이미지 URL (HTML img 태그)

  act=time&rev_days=YYYY-MM-DD&theme_num={N}
    → 날짜별 시간대 슬롯 (HTML)
    → a.none → 예약완료(full)
    → a[href] (class 없음) → 예약가능(available)
    → span 텍스트 "10시 30분" 형식에서 시간 파싱

테마 목록 (2026-03-02 기준):
  theme_num=5: My Private Heaven
  theme_num=6: Brooklyn My Love
  theme_num=7: Plan to save my dear

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_frankantique_db.py
  uv run python scripts/sync_frankantique_db.py --no-schedule
  uv run python scripts/sync_frankantique_db.py --days 3
"""

import asyncio
import re
import ssl
import sys
import time
import urllib.request
import urllib.parse
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path

# SSL 인증서 체인 불완전으로 인한 오류 우회
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

CAFE_ID = "874592991"  # 프랭크의골동품가게 카카오 place_id
AJAX_URL = "https://thefrank.co.kr/core/res/rev.make.ajax.php"
BOOKING_URL = "https://thefrank.co.kr/layout/res/home.php?go=rev.make"
REFERER = "https://thefrank.co.kr/layout/res/home.php?go=rev.make"
ZIZUM_NUM = "1"   # 단일 지점
BASE_IMAGE_URL = "https://thefrank.co.kr"
REQUEST_DELAY = 0.8


def _post(data: dict) -> str:
    """AJAX 엔드포인트에 POST 요청."""
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(
        AJAX_URL,
        data=body,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": REFERER,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as r:
            raw = r.read()
            # 사이트가 EUC-KR 혼용 가능성 있어 UTF-8 우선, 실패 시 euc-kr
            try:
                return raw.decode("utf-8")
            except UnicodeDecodeError:
                return raw.decode("euc-kr", errors="ignore")
    except Exception as e:
        print(f"  [WARN] POST 실패 data={data}: {e}")
        return ""


def _fetch_themes(target_date: date) -> list[dict]:
    """테마 목록 조회.

    반환: [{"theme_num": "5", "name": "My Private Heaven"}, ...]
    """
    html = _post({
        "act": "theme",
        "zizum_num": ZIZUM_NUM,
        "theme_num": "",
        "rev_days": target_date.strftime("%Y-%m-%d"),
    })
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    themes = []
    for a in soup.find_all("a"):
        href = a.get("href", "")
        m = re.search(r"fun_theme_select\('(\d+)'", href)
        if not m:
            continue
        theme_num = m.group(1)
        span = a.find("span")
        name = span.get_text(strip=True) if span else ""
        if theme_num and name:
            themes.append({"theme_num": theme_num, "name": name})
    return themes


def _fetch_poster(theme_num: str) -> str | None:
    """테마 포스터 이미지 URL 조회."""
    html = _post({"act": "theme_img", "theme_num": theme_num})
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    img = soup.find("img")
    if img and img.get("src"):
        src = img["src"]
        if src.startswith("http"):
            return src
        return BASE_IMAGE_URL + src
    return None


def _fetch_slots(theme_num: str, target_date: date) -> list[dict]:
    """날짜별 시간대 슬롯 조회.

    반환: [{"time": dtime(10, 30), "status": "available"}, ...]
    """
    html = _post({
        "act": "time",
        "rev_days": target_date.strftime("%Y-%m-%d"),
        "theme_num": theme_num,
    })
    if not html or "잘못된 접근" in html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    slots = []
    for a in soup.find_all("a"):
        span = a.find("span")
        if not span:
            continue
        # "10시 30분" 또는 "10시 00분" 형식 파싱
        time_text = span.get_text(strip=True)
        m = re.search(r"(\d+)시\s*(\d+)분", time_text)
        if not m:
            continue
        hh, mm = int(m.group(1)), int(m.group(2))

        # 예약 가능 여부: class="none" → full, href 있음 → available
        classes = a.get("class", [])
        href = a.get("href", "")
        if "none" in classes:
            status = "full"
        elif "fun_theme_time_select" in href:
            status = "available"
        else:
            status = "full"  # 예상치 못한 경우 full로 처리

        slots.append({"time": dtime(hh, mm), "status": status})
    return slots


# ── DB 동기화 ──────────────────────────────────────────────────────────────────

async def sync_themes() -> dict[str, int]:
    """프랭크의골동품가게 테마를 DB에 upsert.

    반환: {theme_num → db theme.id}
    """
    # 오늘 or 내일 날짜로 테마 목록 조회 (오늘이 지난 경우 대비)
    today = date.today()
    themes_raw = _fetch_themes(today)
    if not themes_raw:
        tomorrow = today + timedelta(days=1)
        themes_raw = _fetch_themes(tomorrow)
    time.sleep(REQUEST_DELAY)

    if not themes_raw:
        print("  [ERROR] 테마 목록 조회 실패")
        return {}

    # 포스터 이미지 수집
    theme_data = []
    for t in themes_raw:
        poster = _fetch_poster(t["theme_num"])
        time.sleep(REQUEST_DELAY)
        theme_data.append({**t, "poster_url": poster})
        print(f"  테마 발견: [{t['theme_num']}] {t['name']} poster={poster}")

    # DB upsert
    theme_map: dict[str, int] = {}
    added = updated = 0

    async with AsyncSessionLocal() as session:
        cafe = await session.get(Cafe, CAFE_ID)
        if not cafe:
            print(f"  [ERROR] cafe {CAFE_ID} DB 미존재")
            return {}

        for t in theme_data:
            theme_num = t["theme_num"]
            name = t["name"]
            poster_url = t["poster_url"]

            result = await session.execute(
                select(Theme).where(
                    Theme.cafe_id == CAFE_ID,
                    Theme.name == name,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.poster_url = poster_url or existing.poster_url
                existing.is_active = True
                theme_map[theme_num] = existing.id
                updated += 1
            else:
                theme = Theme(
                    cafe_id=CAFE_ID,
                    name=name,
                    description=None,
                    difficulty=None,
                    duration_min=None,
                    poster_url=poster_url,
                    is_active=True,
                )
                session.add(theme)
                await session.flush()
                theme_map[theme_num] = theme.id
                added += 1

            print(f"  {'[NEW]' if not existing else '[UPD]'} {name} (theme_num={theme_num})")

        await session.commit()

    print(f"\n  테마 동기화 완료: {added}개 추가 / {updated}개 갱신")
    return theme_map


async def sync_schedules(theme_map: dict[str, int], days: int = 6):
    """프랭크의골동품가게 스케줄을 schedule 테이블에 upsert (오늘~days일 후)."""
    today = date.today()
    target_dates = [today + timedelta(days=i) for i in range(days + 1)]
    crawled_at = datetime.now()
    added = 0

    async with AsyncSessionLocal() as session:
        for theme_num, db_theme_id in theme_map.items():
            for target_date in target_dates:
                slots = _fetch_slots(theme_num, target_date)
                time.sleep(REQUEST_DELAY)

                for slot in slots:
                    time_obj = slot["time"]
                    status = slot["status"]

                    slot_dt = datetime(
                        target_date.year, target_date.month, target_date.day,
                        time_obj.hour, time_obj.minute,
                    )
                    if slot_dt <= datetime.now():
                        continue

                    booking_url = BOOKING_URL if status == "available" else None

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

            print(f"  theme_num={theme_num} 완료")

        await session.commit()

    print(f"\n  스케줄 동기화 완료: {added}개 레코드 추가")


async def main(run_schedule: bool = True, days: int = 6):
    print("=" * 60)
    print("프랭크의골동품가게 → DB 동기화")
    print("=" * 60)

    from app.models import cafe, theme, schedule, user, alert  # noqa
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("\n[ 1단계 ] 테마 동기화")
    theme_map = await sync_themes()
    print(f"  theme_num 매핑: {theme_map}")

    if run_schedule and theme_map:
        print(f"\n[ 2단계 ] 스케줄 동기화 (오늘~{days}일 후)")
        await sync_schedules(theme_map, days=days)

    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="프랭크의골동품가게 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="테마만 동기화, 스케줄 생략")
    parser.add_argument("--days", type=int, default=6, help="오늘 포함 몇 일치 스케줄 수집 (기본 6)")
    args = parser.parse_args()
    asyncio.run(main(run_schedule=not args.no_schedule, days=args.days))
