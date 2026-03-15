"""
방탈출 넘버원(수원) 테마 + 스케줄 DB 동기화 스크립트.

사이트: http://www.no1escape.com
플랫폼: Gnuboard 기반 자체 AJAX API

지점:
  수원점  cafe_id=27324626  area=gyeonggi  (경기 수원시 팔달구 향교로 47)

API:
  GET http://www.no1escape.com/sub/theme_list.ajax.html.php?date={YYYY-MM-DD}
  응답: {"msg": "OK", "html": "..."}
  HTML:
    <div class="rv_prison">
      <h2>{N}. {theme_name}</h2>
      <li class="booking" data-id="{id}" data-date="{date}" data-time="{HH:MM}">HH:MM<br>ON</li>  ← 예약가능
      <li class="rv_no">HH:MM<br>OFF</li>  ← 예약불가
    </div>

예약 URL: http://www.no1escape.com/sub/Reservation1.php (슬롯별 직접 링크 없음)

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_no1escape_db.py
  uv run python scripts/sync_no1escape_db.py --no-schedule
  uv run python scripts/sync_no1escape_db.py --days 14
"""

import json
import re
import ssl
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta
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

SITE_URL    = "http://www.no1escape.com"
API_URL     = f"{SITE_URL}/sub/theme_list.ajax.html.php"
RESERVE_URL = f"{SITE_URL}/sub/Reservation1.php"
REQUEST_DELAY = 0.8

CAFE_ID     = "27324626"
BRANCH_NAME = "수원점"
ADDRESS     = "경기 수원시 팔달구 향교로 47"
AREA        = "gyeonggi"

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*",
    "Referer": f"{SITE_URL}/sub/Reservation1.php",
    "Accept-Language": "ko-KR,ko;q=0.9",
}


def fetch_slots(target_date: date) -> str:
    """날짜별 테마/슬롯 HTML 조회."""
    date_str = target_date.strftime("%Y-%m-%d")
    url = f"{API_URL}?date={date_str}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        if data.get("msg") == "OK":
            return data.get("html", "")
        return ""
    except Exception as e:
        print(f"  [WARN] GET {url} 실패: {e}")
        return ""


def parse_html(html: str) -> dict[str, list[dict]]:
    """
    반환: {theme_name: [{time, status, booking_url}]}
    """
    soup = BeautifulSoup(html, "html.parser")
    result: dict[str, list[dict]] = {}

    for prison in soup.find_all("div", class_="rv_prison"):
        h2 = prison.find("h2")
        if not h2:
            continue
        # "01. 레시피 (Recipe)" → "레시피 (Recipe)"
        raw_name = h2.get_text(strip=True)
        theme_name = re.sub(r"^\d+\.\s*", "", raw_name).strip()

        slots = []
        for li in prison.find_all("li"):
            cls = li.get("class", [])
            time_str = li.get("data-time", "").strip()
            if not time_str:
                continue

            if "booking" in cls:
                status = "available"
                booking_url = RESERVE_URL
            elif "rv_no" in cls:
                status = "full"
                booking_url = None
            else:
                continue

            slots.append({
                "time":        time_str,
                "status":      status,
                "booking_url": booking_url,
            })

        if slots:
            result[theme_name] = slots

    return result


# ── DB 동기화 ─────────────────────────────────────────────────────────────────

def sync_cafe_meta(db) -> None:
    upsert_cafe(db, CAFE_ID, {
        "name":        "방탈출NO1",
        "branch_name": BRANCH_NAME,
        "address":     ADDRESS,
        "area":        AREA,
        "website_url": SITE_URL,
        "engine":      "no1escape",
        "crawled":     True,
        "is_active":   True,
    })
    print(f"  [UPSERT] 카페: 방탈출NO1 {BRANCH_NAME} (id={CAFE_ID})")


def sync_schedules(db, days: int = 14) -> int:
    today = date.today()
    crawled_at = datetime.now()

    cafe_doc = db.collection("cafes").document(CAFE_ID).get()
    if not cafe_doc.exists:
        print(f"  [WARN] cafe {CAFE_ID} Firestore 미존재 — 건너뜀")
        return 0

    theme_cache: dict[str, str] = {}
    date_themes: dict[str, dict] = {}
    writes = 0

    for i in range(days + 1):
        target_date = today + timedelta(days=i)
        date_str = target_date.strftime("%Y-%m-%d")

        html = fetch_slots(target_date)
        time.sleep(REQUEST_DELAY)
        if not html:
            print(f"  {date_str}: 데이터 없음")
            continue

        themes_map = parse_html(html)
        avail = full = 0

        for theme_name, slots in themes_map.items():
            if theme_name not in theme_cache:
                doc_id = get_or_create_theme(db, CAFE_ID, theme_name, {
                    "poster_url": None,
                    "is_active":  True,
                })
                theme_cache[theme_name] = doc_id
                print(f"  [UPSERT] 테마: {theme_name}")
            theme_doc_id = theme_cache[theme_name]

            for slot in slots:
                try:
                    hh, mm = map(int, slot["time"].split(":"))
                except Exception:
                    continue
                slot_dt = datetime(
                    target_date.year, target_date.month, target_date.day, hh, mm
                )
                if slot_dt <= datetime.now():
                    continue

                date_themes.setdefault(date_str, {}).setdefault(
                    theme_doc_id, {"slots": []}
                )["slots"].append({
                    "time":        f"{hh:02d}:{mm:02d}",
                    "status":      slot["status"],
                    "booking_url": slot["booking_url"],
                })
                if slot["status"] == "available":
                    avail += 1
                else:
                    full += 1

        print(f"  {date_str}: 가능 {avail} / 마감 {full}")

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

    print(f"  스케줄 동기화 완료: {writes}개 날짜 문서 작성")
    return writes


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main(run_schedule: bool = True, days: int = 14):
    print("=" * 60)
    print("방탈출NO1(no1escape.com) → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)
    db = get_db()

    print("\n[ 1단계 ] 카페 메타 동기화")
    sync_cafe_meta(db)

    if run_schedule:
        print(f"\n[ 2단계 ] 스케줄 동기화 (오늘~{days}일 후)")
        sync_schedules(db, days=days)

    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="방탈출NO1 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
