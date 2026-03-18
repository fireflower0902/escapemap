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

from app.config import settings
from app.firestore_db import (
    init_firestore, get_db, upsert_cafe, get_or_create_theme,
    upsert_cafe_date_schedules, load_cafe_hashes, save_cafe_hashes,
    address_to_area,
)

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
    try:
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"  [WARN] GET {path} 실패: {e}")
        return {}


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

def sync_themes() -> dict[str, dict[int, str]]:
    """
    도어이스케이프 테마를 Firestore에 upsert.
    반환: {shop_keycode → {api_theme_id → theme_doc_id}}
    """
    db = get_db()
    shop_to_themes: dict[str, dict[int, str]] = {}
    added = updated = 0

    for shop_keycode, cafe_id in SHOP_MAP.items():
        detail = fetch_shop_detail(shop_keycode)
        time.sleep(REQUEST_DELAY)

        # 카페 meta upsert (신규 cafe 포함)
        shop_info = detail.get("shop", {})
        if shop_info:
            address = shop_info.get("address") or ""
            upsert_cafe(db, cafe_id, {
                "name":        "도어이스케이프",
                "branch_name": shop_info.get("name") or "",
                "address":     address,
                "area":        address_to_area(address),
                "phone":       shop_info.get("contact") or "",
                "website_url": "https://doorescape.co.kr",
                "engine":      "playtheworld",
                "crawled":     True,
                "is_active":   True,
            })

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

            theme_doc_id = get_or_create_theme(db, cafe_id, name, {
                "difficulty": difficulty,
                "duration_min": duration,
                "description": clean_summary or None,
                "poster_url": image_url,
                "is_active": True,
            })
            shop_to_themes[shop_keycode][api_id] = theme_doc_id
            print(f"  [UPSERT] {name} (cafe={cafe_id}) — {duration}분")

    print(f"\n  테마 동기화 완료: {sum(len(v) for v in shop_to_themes.values())}개")
    return shop_to_themes


def sync_schedules(
    shop_to_themes: dict[str, dict[int, str]],
    days: int = 6,
):
    """도어이스케이프 스케줄을 Firestore에 upsert (오늘~days일 후)."""
    db = get_db()
    today = date.today()
    target_dates = {
        (today + timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(days + 1)
    }
    crawled_at = datetime.now()
    writes = 0

    for shop_keycode, theme_id_map in shop_to_themes.items():
        cafe_id = SHOP_MAP.get(shop_keycode, "")
        if not theme_id_map:
            continue

        detail = fetch_shop_detail(shop_keycode)
        time.sleep(REQUEST_DELAY)

        booking_base = f"https://doorescape.co.kr/reservation.html?keycode={shop_keycode}"

        # {date_str: {theme_doc_id: {"slots": [...]}}}
        date_themes: dict[str, dict] = {}

        for t in detail.get("themes", []):
            api_id = t["id"]
            theme_doc_id = theme_id_map.get(api_id)
            if not theme_doc_id:
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

                date_themes.setdefault(day_str, {}).setdefault(theme_doc_id, {"slots": []})["slots"].append({
                    "time": f"{hh:02d}:{mm:02d}",
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

        print(f"  {shop_keycode} 완료")

    print(f"\n  스케줄 동기화 완료: {writes}개 날짜 문서 작성")


def main(run_schedule: bool = True, days: int = 6):
    print("=" * 60)
    print("doorescape.co.kr → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)

    print("\n[ 1단계 ] 테마 동기화")
    shop_to_themes = sync_themes()
    total_themes = sum(len(v) for v in shop_to_themes.values())
    print(f"  테마 ID 매핑: {total_themes}개")

    if run_schedule:
        print(f"\n[ 2단계 ] 스케줄 동기화 (오늘~{days}일 후)")
        sync_schedules(shop_to_themes, days=days)

    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 생략")
    parser.add_argument("--days", type=int, default=6, help="스케줄 조회 일수")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
