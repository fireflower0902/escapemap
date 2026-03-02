"""
doorescape.co.kr 테마 + 스케줄을 DB에 동기화하는 스크립트.

API: macro.playthe.world (공용 예약 플랫폼)
  [전체 지점]  GET /v2/shops.json?keycode={BRAND_KEYCODE}
  [지점 상세]  GET /v2/shops/{shop_keycode}
    → 응답: { data: { shop: {...}, themes: [{id, title, image_url, summary, slots: [...]}] } }
    → 슬롯: { id, day_string (YYYY-MM-DD), integer_to_time (HH:MM), can_book (bool) }

인증: JWT (HS256) — keycode를 secret으로 사용
  headers: Bearer-Token, X-Request-Option (JWT), X-Secure-Random, Site-Referer 등

실행:
  cd escape-aggregator/backend
  python scripts/sync_doorescape_db.py
  python scripts/sync_doorescape_db.py --no-schedule
  python scripts/sync_doorescape_db.py --days 3
"""

import asyncio
import base64
import hashlib
import hmac
import json
import random
import re
import ssl
import string
import sys
import time
import urllib.request
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select

from app.database import AsyncSessionLocal, engine, Base
from app.models.cafe import Cafe
from app.models.theme import Theme
from app.models.schedule import Schedule

BRAND_KEYCODE = "MmtAku42Sc4f1V2N"
BASE_URL = "https://macro.playthe.world"
REQUEST_DELAY = 0.5

# shop keycode → 카카오 place_id (cafe.id)
SHOP_MAP = {
    "aAo1RDEnfyPkbeix": "691418241",   # 강남 가든점
    "NeZqzMtPCBsSvbAq": "765336936",   # 신논현 레드점
    "yGozPSZSJXwrzbin": "2058736611",  # 신논현 블루점
    "o83TaXbnod8DtEX5": "153136502",   # 홍대점
    "h1i4d4YyEfBctnpQ": "190103388",   # 이수역점
    "DGpkkgMQYaNLYXTZ": "27609271",    # 안산점
    "fGDxtefVDEyWczai": "1836271694",  # 대전유성 NC백화점
    "FgBZDHfrR8p5UDmF": "1460830485",  # 부평점
}

# SSL 검증 컨텍스트 (macro.playthe.world 인증서 체인 문제 우회)
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


# ── JWT 인증 ───────────────────────────────────────────────────────────────────

def _b64url(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode()
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _create_jwt(keycode: str, secure_random: str) -> str:
    header = json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":"))
    payload = json.dumps(
        {"X-Auth-Token": secure_random, "expired_at": int(time.time()) + 3600},
        separators=(",", ":"),
    )
    msg = f"{_b64url(header)}.{_b64url(payload)}"
    sig = hmac.new(keycode.encode(), msg.encode(), hashlib.sha256).digest()
    return f"{msg}.{_b64url(sig)}"


def _make_auth_headers() -> dict[str, str]:
    chars = string.ascii_letters + string.digits
    secure = "".join(random.choices(chars, k=16))
    jwt = _create_jwt(BRAND_KEYCODE, secure)
    return {
        "Bearer-Token": BRAND_KEYCODE,
        "Name": "door-escape",
        "Site-Referer": "https://doorescape.co.kr",
        "X-Request-Origin": "https://doorescape.co.kr",
        "X-Request-Option": jwt,
        "X-Secure-Random": secure,
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    }


def _api_get(path: str) -> dict:
    url = BASE_URL + path
    req = urllib.request.Request(url, headers=_make_auth_headers())
    with urllib.request.urlopen(req, context=_SSL_CTX, timeout=15) as r:
        return json.loads(r.read().decode())


# ── 크롤링 함수 ────────────────────────────────────────────────────────────────

def fetch_shop_detail(shop_keycode: str) -> dict:
    """지점 상세 (테마 + 슬롯 전체) 반환."""
    data = _api_get(f"/v2/shops/{shop_keycode}")
    return data.get("data", {})


def parse_duration(summary: str) -> int | None:
    """summary에서 소요 시간 추출. 예: '[ 70분 ]' → 70"""
    if not summary:
        return None
    m = re.search(r"\[\s*(\d+)\s*분\s*\]", summary)
    if m:
        return int(m.group(1))
    return None


def parse_difficulty(summary: str) -> int | None:
    """summary에서 난이도 추출 (별 5개 이미지로 표현되므로 숫자로 변환 어려움)."""
    if not summary:
        return None
    m = re.search(r"난이도\s*[:\s]+(\d+)", summary)
    if m:
        val = int(m.group(1))
        return max(1, min(5, val))
    return None


# ── DB 동기화 함수 ─────────────────────────────────────────────────────────────

async def sync_themes() -> dict[str, dict[int, int]]:
    """
    도어이스케이프 테마를 theme 테이블에 upsert.
    반환: {shop_keycode → {api_theme_id → db theme.id}}
    """
    shop_to_themes: dict[str, dict[int, int]] = {}
    added = updated = 0

    async with AsyncSessionLocal() as session:
        for shop_keycode, cafe_id in SHOP_MAP.items():
            cafe = await session.get(Cafe, cafe_id)
            if not cafe:
                print(f"  [WARN] cafe {cafe_id} DB 미존재 — 건너뜀")
                continue

            detail = fetch_shop_detail(shop_keycode)
            time.sleep(REQUEST_DELAY)

            themes = detail.get("themes", [])
            shop_to_themes[shop_keycode] = {}

            for t in themes:
                api_id = t["id"]
                name = t["title"]
                summary = t.get("summary") or ""
                # HTML 태그 제거
                clean_summary = re.sub(r"<[^>]+>", "", summary).strip()
                duration = parse_duration(clean_summary)
                difficulty = parse_difficulty(clean_summary)
                image_url = t.get("image_url") or None

                result = await session.execute(
                    select(Theme).where(
                        Theme.cafe_id == cafe_id,
                        Theme.name == name,
                    )
                )
                existing = result.scalar_one_or_none()

                if existing:
                    existing.duration_min = duration
                    existing.difficulty = difficulty
                    existing.description = clean_summary or None
                    existing.poster_url = image_url or existing.poster_url
                    existing.is_active = True
                    shop_to_themes[shop_keycode][api_id] = existing.id
                    updated += 1
                else:
                    theme = Theme(
                        cafe_id=cafe_id,
                        name=name,
                        description=clean_summary or None,
                        difficulty=difficulty,
                        duration_min=duration,
                        poster_url=image_url,
                        is_active=True,
                    )
                    session.add(theme)
                    await session.flush()
                    shop_to_themes[shop_keycode][api_id] = theme.id
                    added += 1

                print(f"  {'[NEW]' if not existing else '[UPD]'} {name} ({cafe.name}) — {duration}분")

        await session.commit()

    print(f"\n  테마 동기화 완료: {added}개 추가 / {updated}개 갱신")
    return shop_to_themes


async def sync_schedules(
    shop_to_themes: dict[str, dict[int, int]],
    days: int = 6,
):
    """도어이스케이프 스케줄을 schedule 테이블에 upsert (오늘~days일 후)."""
    today = date.today()
    target_dates = {
        (today + timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(days + 1)
    }
    crawled_at = datetime.now()
    added = 0

    async with AsyncSessionLocal() as session:
        for shop_keycode, theme_id_map in shop_to_themes.items():
            if not theme_id_map:
                continue

            detail = fetch_shop_detail(shop_keycode)
            time.sleep(REQUEST_DELAY)

            booking_base = f"https://doorescape.co.kr/reservation.html?keycode={shop_keycode}"

            for t in detail.get("themes", []):
                api_id = t["id"]
                db_theme_id = theme_id_map.get(api_id)
                if not db_theme_id:
                    continue

                for slot in t.get("slots", []):
                    day_str = slot.get("day_string", "")
                    if day_str not in target_dates:
                        continue

                    time_str = slot.get("integer_to_time", "")
                    if not time_str or ":" not in time_str:
                        continue

                    can_book = slot.get("can_book", False)
                    hh, mm = map(int, time_str.split(":"))
                    time_obj = dtime(hh, mm)
                    d = date.fromisoformat(day_str)

                    # 미래 슬롯만 저장
                    slot_dt = datetime(d.year, d.month, d.day, hh, mm)
                    if slot_dt <= datetime.now():
                        continue

                    if can_book:
                        status = "available"
                        booking_url = booking_base
                    else:
                        status = "full"
                        booking_url = None

                    result = await session.execute(
                        select(Schedule).where(
                            Schedule.theme_id == db_theme_id,
                            Schedule.date == d,
                            Schedule.time_slot == time_obj,
                        ).order_by(Schedule.crawled_at.desc()).limit(1)
                    )
                    existing = result.scalar_one_or_none()

                    if existing:
                        if existing.status != status:
                            session.add(Schedule(
                                theme_id=db_theme_id,
                                date=d,
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
                            date=d,
                            time_slot=time_obj,
                            status=status,
                            available_slots=None,
                            total_slots=None,
                            booking_url=booking_url,
                            crawled_at=crawled_at,
                        ))
                        added += 1

            print(f"  {shop_keycode} 완료")

        await session.commit()

    print(f"\n  스케줄 동기화 완료: {added}개 레코드 추가")


async def main(run_schedule: bool = True, days: int = 6):
    print("=" * 60)
    print("doorescape.co.kr → DB 동기화")
    print("=" * 60)

    from app.models import cafe, theme, schedule, user, alert  # noqa
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("\n[ 1단계 ] 테마 동기화")
    shop_to_themes = await sync_themes()
    total_themes = sum(len(v) for v in shop_to_themes.values())
    print(f"  테마 ID 매핑: {total_themes}개")

    if run_schedule:
        print(f"\n[ 2단계 ] 스케줄 동기화 (오늘~{days}일 후)")
        await sync_schedules(shop_to_themes, days=days)

    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 생략")
    parser.add_argument("--days", type=int, default=6, help="스케줄 조회 일수")
    args = parser.parse_args()
    asyncio.run(main(run_schedule=not args.no_schedule, days=args.days))
