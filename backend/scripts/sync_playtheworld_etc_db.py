"""
macro.playthe.world 플랫폼을 사용하는 추가 방탈출 브랜드 동기화 스크립트.

대상 브랜드:
  1. 플레이더월드 강남점    keycode=kQHQReY6D1jPJKs4  Name=playtheworld
  2. 개꿀이스케이프         keycode=Xk8AiGgdQDjyBgZy  Name=playtheworld
  3. 이스케이프샾 신사점    keycode=nwGhWo2rSj4xGDAK  Name=escapeshop

API: macro.playthe.world (doorescape.co.kr와 동일 플랫폼)
  GET /v2/shops.json?keycode={BRAND_KEYCODE}   → 지점 목록
  GET /v2/shops/{shop_keycode}                 → 테마 + 슬롯 전체

인증: JWT (HS256, secret=keycode)
  headers: Bearer-Token, Name, Site-Referer, X-Request-Origin, X-Request-Option, X-Secure-Random

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_playtheworld_etc_db.py
  uv run python scripts/sync_playtheworld_etc_db.py --no-schedule
  uv run python scripts/sync_playtheworld_etc_db.py --days 3
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
from app.firestore_db import init_firestore, get_db, get_or_create_theme, upsert_schedule

REQUEST_DELAY = 0.5
BASE_URL = "https://macro.playthe.world"

# SSL 검증 컨텍스트 (macro.playthe.world 인증서 체인 문제 우회)
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# ── 브랜드 정의 ────────────────────────────────────────────────────────────────
# 각 브랜드: (keycode, name_header, site_referer, shop_keycode → cafe_id)
BRANDS = [
    {
        "keycode": "kQHQReY6D1jPJKs4",
        "name": "playtheworld",
        "referer": "https://reservation.playthe.world",
        "booking_base": "https://reservation.playthe.world/reservation.html",
        "shop_map": {
            "m86eCeH4SoNCqVVX": "841734382",   # 플레이더월드 강남점
        },
    },
    {
        "keycode": "Xk8AiGgdQDjyBgZy",
        "name": "playtheworld",
        "referer": "https://reservation.playthe.world",
        "booking_base": "https://doghoneyescape.com/reservation.html",
        "shop_map": {
            "XEcM52tKWqDCUFCG": "212176813",   # 개꿀이스케이프
        },
    },
    {
        "keycode": "nwGhWo2rSj4xGDAK",
        "name": "escapeshop",
        "referer": "https://escapeshop.co.kr",
        "booking_base": "https://escapeshop.co.kr/reservation.html",
        "shop_map": {
            "Jmas3Q5kHnfxQhFZ": "1000900386",  # 이스케이프샾 신사점
        },
    },
]


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


def _make_auth_headers(keycode: str, name: str, referer: str) -> dict[str, str]:
    chars = string.ascii_letters + string.digits
    secure = "".join(random.choices(chars, k=16))
    jwt = _create_jwt(keycode, secure)
    return {
        "Bearer-Token": secure,
        "Name": name,
        "Site-Referer": referer,
        "X-Request-Origin": referer,
        "X-Request-Option": jwt,
        "X-Secure-Random": secure,
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    }


def _api_get(path: str, keycode: str, name: str, referer: str) -> dict:
    url = BASE_URL + path
    req = urllib.request.Request(url, headers=_make_auth_headers(keycode, name, referer))
    with urllib.request.urlopen(req, context=_SSL_CTX, timeout=15) as r:
        return json.loads(r.read().decode())


# ── 파싱 유틸 ──────────────────────────────────────────────────────────────────

def parse_duration(summary: str) -> int | None:
    """summary HTML에서 소요 시간 추출. 예: '[ 70분 ]' → 70"""
    if not summary:
        return None
    m = re.search(r"\[\s*(\d+)\s*분\s*\]", summary)
    if m:
        return int(m.group(1))
    return None


def parse_difficulty(summary: str) -> int | None:
    if not summary:
        return None
    m = re.search(r"난이도\s*[:\s]+(\d+)", summary)
    if m:
        val = int(m.group(1))
        return max(1, min(5, val))
    return None


# ── DB 동기화 ──────────────────────────────────────────────────────────────────

def sync_brand_themes(brand: dict) -> dict[str, dict[int, str]]:
    """브랜드 내 지점들의 테마를 Firestore에 upsert.
    반환: {shop_keycode → {api_theme_id → theme_doc_id}}
    """
    db = get_db()
    keycode = brand["keycode"]
    name = brand["name"]
    referer = brand["referer"]
    shop_map = brand["shop_map"]

    shop_to_themes: dict[str, dict[int, str]] = {}

    for shop_keycode, cafe_id in shop_map.items():
        cafe_doc = db.collection("cafes").document(cafe_id).get()
        if not cafe_doc.exists:
            print(f"  [WARN] cafe {cafe_id} Firestore 미존재 — 건너뜀")
            continue

        detail = _api_get(f"/v2/shops/{shop_keycode}", keycode, name, referer)
        data = detail.get("data", {})
        time.sleep(REQUEST_DELAY)

        themes = data.get("themes", [])
        shop_to_themes[shop_keycode] = {}

        for t in themes:
            api_id = t["id"]
            t_name = t["title"]
            summary = t.get("summary") or ""
            clean_summary = re.sub(r"<[^>]+>", "", summary).strip()
            duration = parse_duration(clean_summary)
            difficulty = parse_difficulty(clean_summary)
            image_url = t.get("image_url") or None

            theme_doc_id = get_or_create_theme(db, cafe_id, t_name, {
                "difficulty": difficulty,
                "duration_min": duration,
                "description": clean_summary or None,
                "poster_url": image_url,
                "is_active": True,
            })
            shop_to_themes[shop_keycode][api_id] = theme_doc_id
            print(f"  [UPSERT] {t_name} (cafe={cafe_id}) — {duration}분")

    added = sum(len(v) for v in shop_to_themes.values())
    print(f"  테마: {added}개 upsert")
    return shop_to_themes


def sync_brand_schedules(
    brand: dict,
    shop_to_themes: dict[str, dict[int, str]],
    days: int = 6,
):
    db = get_db()
    keycode = brand["keycode"]
    name = brand["name"]
    referer = brand["referer"]
    booking_base = brand["booking_base"]
    shop_map = brand["shop_map"]

    today = date.today()
    target_dates = {
        (today + timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(days + 1)
    }
    crawled_at = datetime.now()
    added = 0

    for shop_keycode, theme_id_map in shop_to_themes.items():
        cafe_id = shop_map.get(shop_keycode, "")
        if not theme_id_map:
            continue

        detail = _api_get(f"/v2/shops/{shop_keycode}", keycode, name, referer)
        data = detail.get("data", {})
        time.sleep(REQUEST_DELAY)

        for t in data.get("themes", []):
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
                time_obj = dtime(hh, mm)
                d = date.fromisoformat(day_str)

                slot_dt = datetime(d.year, d.month, d.day, hh, mm)
                if slot_dt <= datetime.now():
                    continue

                if can_book:
                    status = "available"
                    booking_url = booking_base
                else:
                    status = "full"
                    booking_url = None

                upsert_schedule(
                    db,
                    date_str=day_str,
                    theme_doc_id=theme_doc_id,
                    cafe_id=cafe_id,
                    time_slot=f"{time_obj.hour:02d}:{time_obj.minute:02d}",
                    data={
                        "status": status,
                        "available_slots": None,
                        "booking_url": booking_url,
                        "crawled_at": crawled_at,
                    },
                )
                added += 1

        print(f"  {shop_keycode} 스케줄 완료")

    print(f"  스케줄: {added}개 레코드 추가")


def main(run_schedule: bool = True, days: int = 6):
    print("=" * 60)
    print("macro.playthe.world 추가 브랜드 → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)

    for brand in BRANDS:
        brand_name = brand["name"]
        print(f"\n{'─' * 50}")
        print(f"[ 브랜드: keycode={brand['keycode'][:8]}..., name={brand_name} ]")

        print("\n[ 테마 동기화 ]")
        shop_to_themes = sync_brand_themes(brand)
        total = sum(len(v) for v in shop_to_themes.values())
        print(f"  테마 ID 매핑: {total}개")

        if run_schedule and total > 0:
            print(f"\n[ 스케줄 동기화 (오늘~{days}일 후) ]")
            sync_brand_schedules(brand, shop_to_themes, days=days)

    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-schedule", action="store_true")
    parser.add_argument("--days", type=int, default=6)
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
