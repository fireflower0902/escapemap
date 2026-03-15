"""
꿈소풍(dreampicnicescape.com) 테마 + 스케줄 DB 동기화 스크립트.

사이트: https://dreampicnicescape.com
플랫폼: 자체 Laravel REST API

지점:
  부천점   cafe_id=59939450   경기 부천시 원미구 부일로459번길 33 4층
  안산1호점 cafe_id=1767938917 경기 안산시 단원구 고잔2길 41 6층

API:
  GET /api/public/branches           → 지점 목록
  GET /api/public/themes             → 테마 목록 (모든 지점)
  GET /api/themes?date=YYYY-MM-DD    → 날짜별 테마 + 예약현황

API 구조:
  {branch_name: {themes: [{id, name, image_url, difficulty, time(min),
    times:[HH:MM,...], reservedSlots:{"{themeId}-{time}": ...}, blockedTimes:[...]}]}}

  슬롯 가용성:
    available: times에 있고 reservedSlots/{themeId}-{time} 없고 blockedTimes 미포함
    full:      reservedSlots에 있거나 blockedTimes에 포함

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_dreampicnic_db.py
  uv run python scripts/sync_dreampicnic_db.py --no-schedule
  uv run python scripts/sync_dreampicnic_db.py --days 14
"""

import json
import ssl
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings
from app.firestore_db import (
    init_firestore, get_db, upsert_cafe,
    get_or_create_theme, upsert_cafe_date_schedules,
    load_cafe_hashes, save_cafe_hashes,
)

SITE_URL = "https://dreampicnicescape.com"
REQUEST_DELAY = 0.5

# 지점명 → cafe_id 매핑
BRANCH_MAP: dict[str, dict] = {
    "부천점": {
        "cafe_id":     "59939450",
        "address":     "경기 부천시 원미구 부일로459번길 33 4층",
        "area":        "gyeonggi",
    },
    "안산1호점": {
        "cafe_id":     "1767938917",
        "address":     "경기 안산시 단원구 고잔2길 41 6층",
        "area":        "gyeonggi",
    },
}

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": SITE_URL + "/reservation",
}


def _api_get(path: str) -> dict | list:
    url = SITE_URL + path
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"  [WARN] GET {path} 실패: {e}")
        return {}


# ── DB 동기화 ─────────────────────────────────────────────────────────────────

def sync_cafe_metas() -> None:
    db = get_db()
    for branch_name, meta in BRANCH_MAP.items():
        upsert_cafe(db, meta["cafe_id"], {
            "name":        "꿈소풍",
            "branch_name": branch_name,
            "address":     meta["address"],
            "area":        meta["area"],
            "website_url": SITE_URL,
            "engine":      "dreampicnic",
            "crawled":     True,
            "is_active":   True,
        })
        print(f"  [UPSERT] 카페: 꿈소풍 {branch_name} (id={meta['cafe_id']})")


def sync_themes() -> dict[str, dict[int, str]]:
    """테마 Firestore upsert.
    반환: {branch_name → {theme_api_id → theme_doc_id}}
    """
    db = get_db()
    branch_to_themes: dict[str, dict[int, str]] = {}

    raw = _api_get("/api/public/themes")
    time.sleep(REQUEST_DELAY)
    if not raw:
        print("  [WARN] 테마 API 빈 응답")
        return {}

    for branch_name, themes in raw.items():
        meta = BRANCH_MAP.get(branch_name)
        if not meta:
            continue
        cafe_id = meta["cafe_id"]
        cafe_doc = db.collection("cafes").document(cafe_id).get()
        if not cafe_doc.exists:
            print(f"  [WARN] cafe {cafe_id} Firestore 미존재 — 건너뜀")
            continue

        branch_to_themes[branch_name] = {}
        for t in themes:
            api_id = t["id"]
            name = t["name"]
            image_url = (SITE_URL + "/" + t["image_url"]) if t.get("image_url") else None
            difficulty_raw = t.get("difficulty")
            try:
                difficulty = round(float(difficulty_raw)) if difficulty_raw else None
            except Exception:
                difficulty = None
            duration = t.get("time")  # minutes

            doc_id = get_or_create_theme(db, cafe_id, name, {
                "difficulty":   difficulty,
                "duration_min": duration,
                "poster_url":   image_url,
                "is_active":    True,
            })
            branch_to_themes[branch_name][api_id] = doc_id
            print(f"  [UPSERT] 테마: {name} (branch={branch_name}, duration={duration}분)")

    return branch_to_themes


def sync_schedules(
    branch_to_themes: dict[str, dict[int, str]],
    days: int = 14,
) -> None:
    db = get_db()
    today = date.today()
    crawled_at = datetime.now()
    writes = 0

    for i in range(days + 1):
        target_date = today + timedelta(days=i)
        date_str = target_date.strftime("%Y-%m-%d")

        raw = _api_get(f"/api/themes?date={date_str}")
        time.sleep(REQUEST_DELAY)
        if not raw:
            continue

        for branch_name, bdata in raw.items():
            meta = BRANCH_MAP.get(branch_name)
            if not meta:
                continue
            cafe_id = meta["cafe_id"]
            theme_id_map = branch_to_themes.get(branch_name, {})

            known_hashes = load_cafe_hashes(db, cafe_id)
            date_themes: dict[str, dict] = {}
            avail = full = 0

            for t in bdata.get("themes", []):
                api_id = t["id"]
                theme_doc_id = theme_id_map.get(api_id)
                if not theme_doc_id:
                    continue

                reserved_slots: dict = t.get("reservedSlots", {})
                blocked_times: list = t.get("blockedTimes", [])
                times: list = t.get("times", [])

                for time_str in times:
                    try:
                        hh, mm = map(int, time_str.split(":"))
                    except Exception:
                        continue
                    slot_dt = datetime(
                        target_date.year, target_date.month, target_date.day, hh, mm
                    )
                    if slot_dt <= datetime.now():
                        continue

                    slot_key = f"{api_id}-{time_str}"
                    is_reserved = (slot_key in reserved_slots) or (time_str in blocked_times)
                    status = "full" if is_reserved else "available"
                    booking_url = (SITE_URL + "/reservation") if not is_reserved else None

                    date_themes.setdefault(date_str, {}).setdefault(
                        theme_doc_id, {"slots": []}
                    )["slots"].append({
                        "time":        f"{hh:02d}:{mm:02d}",
                        "status":      status,
                        "booking_url": booking_url,
                    })
                    if status == "available":
                        avail += 1
                    else:
                        full += 1

            print(f"  {branch_name} {date_str}: 가능 {avail} / 마감 {full}")

            new_hashes: dict[str, str] = {}
            for d_str, themes_map in date_themes.items():
                h = upsert_cafe_date_schedules(
                    db, d_str, cafe_id, themes_map, crawled_at,
                    known_hash=known_hashes.get(d_str),
                )
                if h:
                    new_hashes[d_str] = h
                    writes += 1

            if new_hashes:
                today_str = today.isoformat()
                save_cafe_hashes(db, cafe_id, {
                    k: v for k, v in {**known_hashes, **new_hashes}.items()
                    if k >= today_str
                })

    print(f"\n  스케줄 동기화 완료: {writes}개 날짜 문서 작성")


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main(run_schedule: bool = True, days: int = 14):
    print("=" * 60)
    print("꿈소풍(dreampicnicescape.com) → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)

    print("\n[ 1단계 ] 카페 메타 동기화")
    sync_cafe_metas()

    print("\n[ 2단계 ] 테마 동기화")
    branch_to_themes = sync_themes()
    if not branch_to_themes:
        print("  테마 없음, 종료.")
        return

    if run_schedule:
        print(f"\n[ 3단계 ] 스케줄 동기화 (오늘~{days}일 후)")
        sync_schedules(branch_to_themes, days=days)

    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="꿈소풍 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
