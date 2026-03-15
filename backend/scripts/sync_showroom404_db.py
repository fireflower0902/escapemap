"""
쇼룸404 (showroom404.com) 테마 + 스케줄 DB 동기화 스크립트.

사이트: https://showroom404.com
지점: 홍대점 (서울 마포구 서교동 407-27 5층, 카카오 place_id=887263854)
플랫폼: WordPress + booking_system 플러그인 (filter_rooms AJAX)

API:
  POST https://showroom404.com/wp-admin/admin-ajax.php
  Body: action=filter_rooms&location_id=15&theme_id={ID}&currentDate=YYYY-MM-DD
  응답: HTML 조각
    - .theme-time-list > li > a[class="submit"] → 예약가능 (data-time="HH:MM")
    - .theme-time-list > li > a[class="disable"] → 예약불가

테마 목록 (location_id=15):
  - 648: 한라아파트 4동 404호
  - 653: PIG
  - 8281: 꼬치 진다
  - 8284: 블랙홀

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_showroom404_db.py
  uv run python scripts/sync_showroom404_db.py --no-schedule
  uv run python scripts/sync_showroom404_db.py --days 14
"""

import re
import sys
import time
import urllib.request
import urllib.parse
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from bs4 import BeautifulSoup

from app.config import settings
from app.firestore_db import (
    init_firestore, get_db, upsert_cafe,
    get_or_create_theme, upsert_cafe_date_schedules,
    load_cafe_hashes, save_cafe_hashes,
)

CAFE_ID = "887263854"
AJAX_URL = "https://showroom404.com/wp-admin/admin-ajax.php"
BOOKING_URL = "https://showroom404.com/booking/"
LOCATION_ID = 15
REQUEST_DELAY = 1.0

THEMES = [
    {"theme_id": 648,  "name": "한라아파트 4동 404호"},
    {"theme_id": 653,  "name": "PIG"},
    {"theme_id": 8281, "name": "꼬치 진다"},
    {"theme_id": 8284, "name": "블랙홀"},
]

CAFE_META = {
    "name":        "쇼룸404",
    "branch_name": "홍대점",
    "address":     "서울 마포구 서교동 407-27 5층",
    "area":        "hongdae",
    "phone":       None,
    "website_url": "https://showroom404.com/",
    "engine":      "showroom404",
    "crawled":     True,
    "lat":         None,
    "lng":         None,
    "is_active":   True,
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": BOOKING_URL,
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept": "text/html,*/*",
    "X-Requested-With": "XMLHttpRequest",
}


# ── HTTP 유틸 ────────────────────────────────────────────────────────────────────

def _fetch_slots(theme_id: int, target_date: date) -> list[dict]:
    """
    filter_rooms AJAX API로 날짜별 슬롯 조회.
    반환: [{"time": dtime, "status": "available"|"full"}]
    """
    date_str = target_date.strftime("%Y-%m-%d")
    body = urllib.parse.urlencode({
        "action": "filter_rooms",
        "location_id": str(LOCATION_ID),
        "theme_id": str(theme_id),
        "currentDate": date_str,
    }).encode()

    req = urllib.request.Request(AJAX_URL, data=body, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"  [WARN] 슬롯 조회 실패 theme_id={theme_id} date={date_str}: {e}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    slots = []

    for a_tag in soup.select(".theme-time-list li a"):
        css_class = a_tag.get("class", [])
        if isinstance(css_class, str):
            css_class = [css_class]

        time_str = a_tag.get("data-time", "").strip()
        if not time_str or ":" not in time_str:
            continue

        try:
            hh, mm = map(int, time_str.split(":"))
            time_obj = dtime(hh, mm)
        except Exception:
            continue

        if "submit" in css_class:
            status = "available"
        else:
            status = "full"

        slots.append({"time": time_obj, "status": status})

    return slots


# ── DB 동기화 ────────────────────────────────────────────────────────────────────

def sync_cafe_meta() -> None:
    db = get_db()
    upsert_cafe(db, CAFE_ID, CAFE_META)
    print(f"  [UPSERT] 카페: {CAFE_META['name']} {CAFE_META['branch_name']} (id={CAFE_ID})")


def sync_themes_db() -> dict[int, str]:
    """테마를 Firestore에 upsert. 반환: {theme_id → theme_doc_id}"""
    db = get_db()
    cafe_doc = db.collection("cafes").document(CAFE_ID).get()
    if not cafe_doc.exists:
        print(f"  [ERROR] cafe {CAFE_ID} Firestore 미존재")
        return {}

    tid_to_doc: dict[int, str] = {}
    for t in THEMES:
        doc_id = get_or_create_theme(db, CAFE_ID, t["name"], {
            "difficulty":   None,
            "duration_min": None,
            "poster_url":   None,
            "is_active":    True,
        })
        tid_to_doc[t["theme_id"]] = doc_id
        print(f"  [UPSERT] 테마: {t['name']} (theme_id={t['theme_id']}, doc={doc_id})")

    return tid_to_doc


def sync_schedules(tid_to_doc: dict[int, str], days: int = 14) -> None:
    """스케줄을 Firestore에 upsert (오늘~days일 후)."""
    db = get_db()
    today = date.today()
    target_dates = [today + timedelta(days=i) for i in range(days + 1)]
    crawled_at = datetime.now()
    writes = 0

    date_themes: dict[str, dict] = {}

    for theme_info in THEMES:
        theme_id = theme_info["theme_id"]
        theme_doc_id = tid_to_doc.get(theme_id)
        if theme_doc_id is None:
            continue

        for target_date in target_dates:
            slots = _fetch_slots(theme_id, target_date)
            time.sleep(REQUEST_DELAY)

            date_str = target_date.strftime("%Y-%m-%d")
            avail_cnt = 0
            full_cnt = 0

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
                date_themes.setdefault(date_str, {}).setdefault(theme_doc_id, {"slots": []})["slots"].append({
                    "time":        f"{time_obj.hour:02d}:{time_obj.minute:02d}",
                    "status":      status,
                    "booking_url": booking_url,
                })

                if status == "available":
                    avail_cnt += 1
                else:
                    full_cnt += 1

            print(f"  theme_id={theme_id} {date_str}: 가능 {avail_cnt} / 마감 {full_cnt}")

    known_hashes = load_cafe_hashes(db, CAFE_ID)
    new_hashes: dict[str, str] = {}
    for date_str, themes in date_themes.items():
        h = upsert_cafe_date_schedules(
            db, date_str, CAFE_ID, themes, crawled_at,
            known_hash=known_hashes.get(date_str),
        )
        if h:
            new_hashes[date_str] = h
            writes += 1

    if new_hashes:
        today_str = today.isoformat()
        save_cafe_hashes(db, CAFE_ID, {
            k: v for k, v in {**known_hashes, **new_hashes}.items()
            if k >= today_str
        })

    print(f"\n  스케줄 동기화 완료: {writes}개 날짜 문서 작성")


# ── 메인 ─────────────────────────────────────────────────────────────────────────

def main(run_schedule: bool = True, days: int = 14):
    print("=" * 60)
    print("쇼룸404 (showroom404.com) → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)

    print("\n[ 1단계 ] 카페 메타 동기화")
    sync_cafe_meta()

    print("\n[ 2단계 ] 테마 동기화")
    tid_to_doc = sync_themes_db()
    if not tid_to_doc:
        print("테마 동기화 실패, 종료.")
        return

    if run_schedule:
        print(f"\n[ 3단계 ] 스케줄 동기화 (오늘~{days}일 후)")
        sync_schedules(tid_to_doc, days=days)

    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="쇼룸404 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
