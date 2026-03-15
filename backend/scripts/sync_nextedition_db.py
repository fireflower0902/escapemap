"""
넥스트에디션(nextedition.co.kr) 테마 + 스케줄 DB 동기화 스크립트.

사이트: https://www.nextedition.co.kr
API: macro.playthe.world (도어이스케이프와 동일 플랫폼)

Brand Keycode: fanEiYJgoTWk79Vu
Headers: Name=nextedition, Site-Referer=https://next-edition.co.kr

지점 (shop keycode → 카카오 place_id):
  건대1호점 (acBZTNkAVSAF1epy, 광진구 자양동 17-5)        → 1973765277
  건대2호점 (KAuTx3m4n65nuMNB, 광진구 아차산로 192)        → 287949141
  건대 보네르관 (KBUDLjRFoSYfUXrD, 광진구 화양동 9-19)     → 1108129560
  신림점   (qN5HHMkKFyf8uyjj, 관악구 남부순환로 1598)      → 1224056973
  잠실점   (mC6ZzJXrCSRwvaGq, 송파구 올림픽로 118)         → 1460924995
  부천점   (XKCRH8C1Hi4HMZ1S, 부천시 원미구 심곡동 175-9 6층)  → 1678997732
  분당서현점 (timEGRUC2R7mzs7s, 성남시 분당구 황새울로342번길 19 B1) → 635335984

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_nextedition_db.py
  uv run python scripts/sync_nextedition_db.py --no-schedule
  uv run python scripts/sync_nextedition_db.py --days 6
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
    init_firestore, get_db, upsert_cafe,
    get_or_create_theme, upsert_cafe_date_schedules,
    load_cafe_hashes, save_cafe_hashes,
)

BRAND_KEYCODE = "fanEiYJgoTWk79Vu"
BASE_URL = "https://macro.playthe.world"
SITE_URL = "https://www.nextedition.co.kr"
REQUEST_DELAY = 0.5

# shop keycode → 카카오 place_id (cafe.id)
SHOP_MAP: dict[str, str] = {
    "acBZTNkAVSAF1epy": "1973765277",  # 건대1호점
    "KAuTx3m4n65nuMNB": "287949141",   # 건대2호점
    "KBUDLjRFoSYfUXrD": "1108129560",  # 건대 보네르관
    "qN5HHMkKFyf8uyjj": "1224056973",  # 신림점 (관악구 남부순환로 1598)
    "mC6ZzJXrCSRwvaGq": "1460924995",  # 잠실점 (송파구 올림픽로 118)
    "XKCRH8C1Hi4HMZ1S": "1678997732",  # 부천점 (경기 부천시 원미구 심곡동 175-9 6층)
    "timEGRUC2R7mzs7s": "635335984",   # 분당서현점 (경기 성남시 분당구 황새울로342번길 19 B1)
}

# area 코드 매핑
SHOP_AREA: dict[str, str] = {
    "acBZTNkAVSAF1epy": "konkuk",
    "KAuTx3m4n65nuMNB": "konkuk",
    "KBUDLjRFoSYfUXrD": "konkuk",
    "qN5HHMkKFyf8uyjj": "sinlim",
    "mC6ZzJXrCSRwvaGq": "jamsil",
    "XKCRH8C1Hi4HMZ1S": "gyeonggi",
    "timEGRUC2R7mzs7s": "gyeonggi",
}

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


# ── JWT 인증 (doorescape와 동일한 방식) ──────────────────────────────────────

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
        "Name": "nextedition",
        "Site-Referer": "https://next-edition.co.kr",
        "X-Request-Origin": "https://next-edition.co.kr",
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


def fetch_shop_detail(shop_keycode: str) -> dict:
    """지점 상세 (테마 + 슬롯 전체) 반환."""
    data = _api_get(f"/v2/shops/{shop_keycode}")
    return data.get("data", {})


def parse_duration(summary: str) -> int | None:
    """summary에서 소요 시간 추출."""
    if not summary:
        return None
    m = re.search(r"\[\s*(\d+)\s*분\s*\]|\b(\d+)\s*분\b", summary)
    if m:
        return int(m.group(1) or m.group(2))
    return None


def parse_difficulty(summary: str) -> int | None:
    """summary에서 난이도 추출."""
    if not summary:
        return None
    m = re.search(r"난이도\s*[:\s]+(\d+)", summary)
    if m:
        return max(1, min(5, int(m.group(1))))
    return None


# ── DB 동기화 ─────────────────────────────────────────────────────────────────

def sync_cafe_metas() -> None:
    """카페 메타를 Firestore에 upsert합니다."""
    db = get_db()
    for shop_keycode, cafe_id in SHOP_MAP.items():
        detail = fetch_shop_detail(shop_keycode)
        time.sleep(REQUEST_DELAY)
        shop = detail.get("shop", {})
        if not shop:
            print(f"  [WARN] {shop_keycode} 상세 조회 실패")
            continue

        name_full = shop.get("name", "")
        # "넥스트에디션 건대1호점" → "넥스트에디션", "건대1호점"
        if " " in name_full:
            parts = name_full.split(" ", 1)
            name = parts[0]
            branch_name = parts[1]
        else:
            name = name_full
            branch_name = None

        area = SHOP_AREA.get(shop_keycode, "etc")
        upsert_cafe(db, cafe_id, {
            "name":        name,
            "branch_name": branch_name,
            "address":     shop.get("address", ""),
            "area":        area,
            "phone":       shop.get("contact"),
            "website_url": f"{SITE_URL}/reservation.html?keycode={shop_keycode}",
            "engine":      "nextedition",
            "crawled":     True,
            "lat":         None,
            "lng":         None,
            "is_active":   True,
        })
        print(f"  [UPSERT] 카페: {name_full} (id={cafe_id})")


def sync_themes() -> dict[str, dict[int, str]]:
    """
    넥스트에디션 테마를 Firestore에 upsert.
    반환: {shop_keycode → {api_theme_id → theme_doc_id}}
    """
    db = get_db()
    shop_to_themes: dict[str, dict[int, str]] = {}

    for shop_keycode, cafe_id in SHOP_MAP.items():
        cafe_doc = db.collection("cafes").document(cafe_id).get()
        if not cafe_doc.exists:
            print(f"  [WARN] cafe {cafe_id} Firestore 미존재 — 건너뜀")
            continue

        detail = fetch_shop_detail(shop_keycode)
        time.sleep(REQUEST_DELAY)

        themes = detail.get("themes", [])
        shop_to_themes[shop_keycode] = {}

        for t in themes:
            api_id = t["id"]
            name = t["title"]
            summary = t.get("summary") or t.get("description") or ""
            clean_summary = re.sub(r"<[^>]+>", "", summary).strip()
            duration = parse_duration(clean_summary)
            difficulty = parse_difficulty(clean_summary)
            image_url = t.get("image_url") or None

            doc_id = get_or_create_theme(db, cafe_id, name, {
                "difficulty":   difficulty,
                "duration_min": duration,
                "poster_url":   image_url,
                "is_active":    True,
            })
            shop_to_themes[shop_keycode][api_id] = doc_id
            print(f"  [UPSERT] 테마: {name} (cafe={cafe_id}) — {duration}분")

    print(f"\n  테마 동기화: {sum(len(v) for v in shop_to_themes.values())}개")
    return shop_to_themes


def sync_schedules(
    shop_to_themes: dict[str, dict[int, str]],
    days: int = 6,
) -> None:
    """넥스트에디션 스케줄을 Firestore에 upsert (오늘~days일 후)."""
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

        booking_base = f"{SITE_URL}/reservation.html?keycode={shop_keycode}"

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
                try:
                    hh, mm = map(int, time_str.split(":"))
                except Exception:
                    continue

                d = date.fromisoformat(day_str)
                slot_dt = datetime(d.year, d.month, d.day, hh, mm)
                if slot_dt <= datetime.now():
                    continue

                status = "available" if can_book else "full"
                booking_url = booking_base if can_book else None

                date_themes.setdefault(day_str, {}).setdefault(theme_doc_id, {"slots": []})["slots"].append({
                    "time":        f"{hh:02d}:{mm:02d}",
                    "status":      status,
                    "booking_url": booking_url,
                })

        known_hashes = load_cafe_hashes(db, cafe_id)
        new_hashes: dict[str, str] = {}
        for date_str, themes in date_themes.items():
            h = upsert_cafe_date_schedules(
                db, date_str, cafe_id, themes, crawled_at,
                known_hash=known_hashes.get(date_str),
            )
            if h:
                new_hashes[date_str] = h
                writes += 1

        if new_hashes:
            today_str = date.today().isoformat()
            save_cafe_hashes(db, cafe_id, {
                k: v for k, v in {**known_hashes, **new_hashes}.items()
                if k >= today_str
            })

        avail = sum(
            1 for themes in date_themes.values()
            for t_data in themes.values()
            for s in t_data["slots"]
            if s["status"] == "available"
        )
        print(f"  {shop_keycode} 완료 (가능 슬롯 {avail}개)")

    print(f"\n  스케줄 동기화 완료: {writes}개 날짜 문서 작성")


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main(run_schedule: bool = True, days: int = 6):
    print("=" * 60)
    print("넥스트에디션(nextedition.co.kr) → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)

    print("\n[ 1단계 ] 카페 메타 동기화")
    sync_cafe_metas()

    print("\n[ 2단계 ] 테마 동기화")
    shop_to_themes = sync_themes()
    if not shop_to_themes:
        print("  테마 없음, 종료.")
        return

    if run_schedule:
        print(f"\n[ 3단계 ] 스케줄 동기화 (오늘~{days}일 후)")
        sync_schedules(shop_to_themes, days=days)

    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="넥스트에디션 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=6, help="오늘부터 며칠치 수집 (기본 6)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
