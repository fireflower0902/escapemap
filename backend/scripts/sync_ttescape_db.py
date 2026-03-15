"""
티켓투이스케이프(ttescape.co.kr) 테마 + 스케줄 DB 동기화 스크립트.

사이트: https://www.ttescape.co.kr
플랫폼: iMweb + 자체 REST API

지점:
  홍대점  cafe_id=327610610  area=hongdae  (서울 마포구 와우산로29가길 83)

API:
  GET https://api.ttescape.co.kr/api/availability/list?mode=date&date={YYYY-MM-DD}
  응답: {"slots": [{
    "시간": "HHMM",           ← 4자리 숫자 (콜론 없음)
    "입장가능": true/false,
    "테마": "테마명"
  }, ...]}
  (구 응답 형식: 배열 직접 반환도 처리)

예약 URL: https://www.ttescape.co.kr (슬롯별 직접 링크 없음)

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_ttescape_db.py
  uv run python scripts/sync_ttescape_db.py --no-schedule
  uv run python scripts/sync_ttescape_db.py --days 14
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

SITE_URL = "https://www.ttescape.co.kr"
API_URL = "https://api.ttescape.co.kr/api/availability/list"
REQUEST_DELAY = 0.8

BRANCHES = [
    {
        "cafe_id":     "327610610",
        "branch_name": "홍대점",
        "area":        "hongdae",
        "address":     "서울 마포구 와우산로29가길 83",
    },
]

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": SITE_URL,
}


def fetch_slots(target_date: date) -> list[dict]:
    """
    날짜별 슬롯 조회.
    반환: [{"시간": "HHMM", "입장가능": bool, "테마": str}]
    """
    date_str = target_date.strftime("%Y-%m-%d")
    url = f"{API_URL}?mode=date&date={date_str}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        # API 응답 형식: {"slots": [...]} 또는 [...]
        if isinstance(data, dict):
            return data.get("slots", [])
        if isinstance(data, list):
            return data
        return []
    except Exception as e:
        print(f"  [WARN] GET {url} 실패: {e}")
        return []


# ── DB 동기화 ─────────────────────────────────────────────────────────────────

def sync_cafe_meta(db, branch: dict) -> None:
    upsert_cafe(db, branch["cafe_id"], {
        "name":        "티켓투이스케이프",
        "branch_name": branch["branch_name"],
        "address":     branch["address"],
        "area":        branch["area"],
        "website_url": SITE_URL,
        "engine":      "ttescape",
        "crawled":     True,
        "is_active":   True,
    })
    print(f"  [UPSERT] 카페: 티켓투이스케이프 {branch['branch_name']} (id={branch['cafe_id']})")


def sync_branch(branch: dict, days: int = 14) -> int:
    db = get_db()
    cafe_id = branch["cafe_id"]
    today = date.today()
    target_dates = [today + timedelta(days=i) for i in range(days + 1)]
    crawled_at = datetime.now()
    total_writes = 0

    cafe_doc = db.collection("cafes").document(cafe_id).get()
    if not cafe_doc.exists:
        print(f"  [WARN] cafe {cafe_id} Firestore 미존재 — 건너뜀")
        return 0

    theme_cache: dict[str, str] = {}
    date_themes: dict[str, dict] = {}

    for target_date in target_dates:
        date_str = target_date.strftime("%Y-%m-%d")
        slots = fetch_slots(target_date)
        time.sleep(REQUEST_DELAY)

        if not slots:
            print(f"  {date_str}: 데이터 없음")
            continue

        avail_cnt = full_cnt = 0

        for slot in slots:
            raw_time = str(slot.get("시간", "")).zfill(4)  # "HHMM"
            theme_name = slot.get("테마", "").strip()
            can_enter = slot.get("입장가능", False)

            if not theme_name or len(raw_time) < 4:
                continue

            try:
                hh = int(raw_time[:2])
                mm = int(raw_time[2:4])
            except Exception:
                continue

            slot_dt = datetime(
                target_date.year, target_date.month, target_date.day, hh, mm,
            )
            if slot_dt <= datetime.now():
                continue

            if theme_name not in theme_cache:
                doc_id = get_or_create_theme(db, cafe_id, theme_name, {
                    "poster_url": None,
                    "is_active":  True,
                })
                theme_cache[theme_name] = doc_id
                print(f"  [UPSERT] 테마: {theme_name}")
            theme_doc_id = theme_cache[theme_name]

            status = "available" if can_enter else "full"
            date_themes.setdefault(date_str, {}).setdefault(
                theme_doc_id, {"slots": []}
            )["slots"].append({
                "time":        f"{hh:02d}:{mm:02d}",
                "status":      status,
                "booking_url": SITE_URL if can_enter else None,
            })

            if can_enter:
                avail_cnt += 1
            else:
                full_cnt += 1

        print(f"  {date_str}: 가능 {avail_cnt} / 마감 {full_cnt}")

    known_hashes = load_cafe_hashes(db, cafe_id)
    new_hashes: dict[str, str] = {}
    for date_str, themes_map in date_themes.items():
        h = upsert_cafe_date_schedules(
            db, date_str, cafe_id, themes_map, crawled_at,
            known_hash=known_hashes.get(date_str),
        )
        if h:
            new_hashes[date_str] = h
            total_writes += 1

    if new_hashes:
        today_str = today.isoformat()
        save_cafe_hashes(db, cafe_id, {
            k: v for k, v in {**known_hashes, **new_hashes}.items()
            if k >= today_str
        })

    print(f"  스케줄 동기화 완료: {total_writes}개 날짜 문서 작성")
    return total_writes


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main(run_schedule: bool = True, days: int = 14):
    print("=" * 60)
    print("티켓투이스케이프(ttescape.co.kr) → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)
    db = get_db()

    print("\n[ 1단계 ] 카페 메타 동기화")
    for branch in BRANCHES:
        sync_cafe_meta(db, branch)

    if run_schedule:
        for branch in BRANCHES:
            print(f"\n[ 2단계 ] {branch['branch_name']} 스케줄 동기화 (오늘~{days}일 후)")
            sync_branch(branch, days=days)

    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="티켓투이스케이프 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
