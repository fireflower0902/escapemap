"""
macro.playthe.world 플랫폼을 사용하는 추가 방탈출 브랜드 동기화 스크립트.

대상 브랜드:
  1. 플레이더월드 강남/평택/동성로/부평  keycode=kQHQReY6D1jPJKs4  Name=playtheworld
  2. 개꿀이스케이프         keycode=Xk8AiGgdQDjyBgZy  Name=playtheworld
  3. 이스케이프샾 신사점    keycode=nwGhWo2rSj4xGDAK  Name=escapeshop
  4. 이스케이프샾 건대점    keycode=nwGhWo2rSj4xGDAK  shop=tS5DajzuHqnhrnjH
  5. 룸익스케이프(ex-cape)  keycode=CKRwHMB3FGpytPrP  Name=room-excape  (신촌 4지점)
  6. 오늘의한페이지         keycode=jCEMud1hyJKnxYGu  Name=page-today   (강남)
  7. 룸즈에이 부평점        keycode=LmnDt6wGgVEUpPC5  Name=roomsa       (인천 부평구)
  8. 시간의문               keycode=GGvfWvikFsVUQS1b  Name=gateoftime   (광주/대구)

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
from app.firestore_db import (
    init_firestore, get_db, upsert_cafe, get_or_create_theme,
    upsert_cafe_date_schedules, load_cafe_hashes, save_cafe_hashes,
    address_to_area,
)

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
            "eerYSTbbLAQnqZv3": "767938268",    # 플레이더월드 평택점
            "bF9P9ARTDcgrbcDR": "76631654",     # 플레이더월드 동성로점 (대구)
            "fsGEtW3EXJiFXVCZ": "1637776603",   # 플레이더월드 부평점 (인천)
            "U9cZjMPWeVZbij6X": "1224388097",   # 플레이더월드 대전은행점
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
            "tS5DajzuHqnhrnjH": "2016521022",   # 이스케이프샾 건대점
        },
    },
    {
        "keycode": "CKRwHMB3FGpytPrP",
        "name": "room-excape",
        "referer": "https://ex-cape.com",
        "booking_base": "https://ex-cape.com/reservation.html",
        "shop_map": {
            "Z5dmpFTTqzaSqaa4": "27329834",     # 룸익스케이프 신촌 블랙점
            "p8j31JZAgRCJWnUc": "1542251042",   # 룸익스케이프 신촌 화이트점
            "vG4SZyg8jem2YYuo": "912842418",    # 룸익스케이프 신촌 올리브점
            "mpu5Jvr5DzANeHRL": "690123759",    # 룸익스케이프 신촌 인디고블루점
        },
    },
    {
        "keycode": "jCEMud1hyJKnxYGu",
        "name": "page-today",
        "referer": "https://page-today.co.kr",
        "booking_base": "https://page-today.co.kr/#reserve",
        "shop_map": {
            "rjwaaAh3mVPbCdHA": "2012633570",   # 오늘의한페이지 강남점
        },
    },
    {
        "keycode": "LmnDt6wGgVEUpPC5",
        "name": "roomsa",
        "referer": "https://roomsa.co.kr",
        "booking_base": "https://roomsa.co.kr/reservation.html",
        "shop_map": {
            "HUSqfLY6kenWuw5q": "802938757",    # 룸즈에이 부평점
            "N22seZPUEfSe1jKQ": "1544141348",   # 룸즈에이 광주수완 2호점
        },
    },
    {
        "keycode": "GGvfWvikFsVUQS1b",
        "name": "gateoftime",
        "referer": "https://gateoftime.kr",
        "booking_base": "https://gateoftime.kr/reservation.html",
        "keycode_in_path": True,  # /v2/shops/{shop}?keycode= 필수
        "shop_map": {
            "YybEYe16XjtuRV7S": "1393764461",   # 시간의문 광주점
            "HiJhoQFf8ThapVG3": "929019886",    # 시간의문 대구동성로점
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
    try:
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"  [WARN] GET {path} 실패: {e}")
        return {}


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

    needs_keycode = brand.get("keycode_in_path", False)
    for shop_keycode, cafe_id in shop_map.items():
        path = f"/v2/shops/{shop_keycode}"
        if needs_keycode:
            path += f"?keycode={keycode}"
        detail = _api_get(path, keycode, name, referer)
        data = detail.get("data", {})
        time.sleep(REQUEST_DELAY)

        # 카페 meta upsert (신규 cafe 포함)
        shop_info = data.get("shop", {})
        if shop_info:
            address = shop_info.get("address") or ""
            upsert_cafe(db, cafe_id, {
                "name":        name,
                "branch_name": shop_info.get("name") or "",
                "address":     address,
                "area":        address_to_area(address),
                "phone":       shop_info.get("contact") or "",
                "website_url": shop_info.get("brand_site_url") or brand.get("referer", ""),
                "engine":      "playtheworld",
                "crawled":     True,
                "is_active":   True,
            })

        cafe_doc = db.collection("cafes").document(cafe_id).get()
        if not cafe_doc.exists:
            print(f"  [WARN] cafe {cafe_id} Firestore 미존재 — 건너뜀")
            continue

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
    writes = 0

    for shop_keycode, theme_id_map in shop_to_themes.items():
        cafe_id = shop_map.get(shop_keycode, "")
        if not theme_id_map:
            continue

        detail = _api_get(f"/v2/shops/{shop_keycode}", keycode, name, referer)
        data = detail.get("data", {})
        time.sleep(REQUEST_DELAY)

        # {date_str: {theme_doc_id: {"slots": [...]}}}
        date_themes: dict[str, dict] = {}

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

        print(f"  {shop_keycode} 스케줄 완료")

    print(f"  스케줄: {writes}개 날짜 문서 작성")


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
