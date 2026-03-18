"""
더타임이스케이프(thetimeescape.co.kr) 테마 + 스케줄 DB 동기화 스크립트.

사이트: http://www.thetimeescape.co.kr
플랫폼: Gnuboard 5 + 자체 예약 모듈 (basic_room2 CMS)

지점:
  양산점  place_id=1233678979  area=etc  (경남 양산시 물금읍 청운로 185 오즈시티 307호)

API:
  POST http://www.thetimeescape.co.kr/theme/basic_room2/_content/makeThemeTime.php
  Body: rDate={YYYY-MM-DD}&rTheme={테마명_URL인코딩}
        rTheme='' 이면 전체 테마 반환
  응답: HTML
    <li class="rev" onClick="roomSubmit('{HH:MM}', '{테마명}')">
      <div class=time>HH:MM</div>
    </li>
    <li class="magam"><div class=time>HH:MM</div></li>

테마 (6개): 사기도박, 시크릿, 레이나의 시약, 누명, 보스의 놀이방, 귀신 헬리콥터

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_thetimeescape_db.py
  uv run python scripts/sync_thetimeescape_db.py --no-schedule
  uv run python scripts/sync_thetimeescape_db.py --days 14
"""

import re
import ssl
import sys
import time
import urllib.parse
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

SITE_URL = "http://www.thetimeescape.co.kr"
API_URL = SITE_URL + "/theme/basic_room2/_content/makeThemeTime.php"
BOOK_URL = SITE_URL + "/?sd=3&sc=3_2"
REQUEST_DELAY = 0.8

CAFE_ID = "1233678979"
CAFE_META = {
    "name":        "더타임이스케이프",
    "branch_name": "",
    "address":     "경남 양산시 물금읍 가촌리 1269-17",
    "area":        "etc",
    "website_url": SITE_URL,
    "engine":      "thetimeescape",
    "crawled":     True,
    "is_active":   True,
}

THEMES: list[str] = [
    "사기도박",
    "시크릿",
    "레이나의 시약",
    "누명",
    "보스의 놀이방",
    "귀신 헬리콥터",
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
    "Accept": "text/html,application/xhtml+xml,*/*",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Content-Type": "application/x-www-form-urlencoded",
    "Referer": SITE_URL + "/?sd=3&sc=3_1",
}


def _fetch(theme_name: str, target_date: date) -> str:
    """특정 테마 + 날짜의 슬롯 HTML 반환."""
    date_str = target_date.strftime("%Y-%m-%d")
    body = urllib.parse.urlencode({
        "rDate":  date_str,
        "rTheme": theme_name,
    }).encode()
    req = urllib.request.Request(API_URL, data=body, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [WARN] POST {API_URL} ({theme_name}/{date_str}) 실패: {e}")
        return ""


def _parse_slots(html: str, theme_name: str, target_date: date) -> list[dict]:
    """HTML에서 슬롯 목록 파싱. 반환: [{time, status, booking_url}]"""
    soup = BeautifulSoup(html, "html.parser")
    slots = []

    for li in soup.find_all("li"):
        classes = li.get("class", [])
        class_str = " ".join(classes)

        div_time = li.find("div")
        if not div_time:
            continue
        time_str = div_time.get_text(strip=True)
        if not re.match(r"^\d{2}:\d{2}$", time_str):
            continue

        if "rev" in class_str:
            slots.append({
                "time":        time_str,
                "status":      "available",
                "booking_url": BOOK_URL,
            })
        elif "magam" in class_str:
            slots.append({
                "time":        time_str,
                "status":      "full",
                "booking_url": None,
            })
        # ings(진행중)은 available 상태가 아니므로 무시

    return slots


# ── DB 동기화 ─────────────────────────────────────────────────────────────────

def main(run_schedule: bool = True, days: int = 14):
    print("=" * 60)
    print("더타임이스케이프(thetimeescape.co.kr) → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)
    db = get_db()

    print("\n[ 1단계 ] 카페 메타 동기화")
    upsert_cafe(db, CAFE_ID, CAFE_META)
    print(f"  [UPSERT] 카페: 더타임이스케이프 (id={CAFE_ID})")

    # 테마 upsert
    print("\n[ 2단계 ] 테마 동기화")
    theme_doc_map: dict[str, str] = {}  # theme_name → doc_id
    for name in THEMES:
        doc_id = get_or_create_theme(db, CAFE_ID, name, {
            "poster_url": None,
            "is_active":  True,
        })
        theme_doc_map[name] = doc_id
        print(f"  [UPSERT] 테마: {name}")

    if not run_schedule:
        print("\n동기화 완료 (스케줄 건너뜀)")
        return

    # 스케줄 upsert
    print(f"\n[ 3단계 ] 스케줄 동기화 (오늘~{days}일 후)")
    today = date.today()
    crawled_at = datetime.now()
    known_hashes = load_cafe_hashes(db, CAFE_ID)
    new_hashes: dict[str, str] = {}
    date_themes: dict[str, dict] = {}

    for i in range(days + 1):
        target_date = today + timedelta(days=i)
        date_str = target_date.strftime("%Y-%m-%d")
        avail = full = 0

        for theme_name, doc_id in theme_doc_map.items():
            html = _fetch(theme_name, target_date)
            time.sleep(REQUEST_DELAY)
            slots = _parse_slots(html, theme_name, target_date)

            for slot in slots:
                try:
                    hh, mm = int(slot["time"][:2]), int(slot["time"][3:5])
                except Exception:
                    continue
                slot_dt = datetime(
                    target_date.year, target_date.month, target_date.day, hh, mm
                )
                if slot_dt <= datetime.now():
                    continue

                date_themes.setdefault(date_str, {}).setdefault(
                    doc_id, {"slots": []}
                )["slots"].append({
                    "time":        f"{hh:02d}:{mm:02d}",
                    "status":      slot["status"],
                    "booking_url": slot.get("booking_url"),
                })
                if slot["status"] == "available":
                    avail += 1
                else:
                    full += 1

        print(f"  {date_str}: 가능 {avail} / 마감 {full}")

    writes = 0
    for date_str, themes_map in date_themes.items():
        h = upsert_cafe_date_schedules(
            db, date_str, CAFE_ID, themes_map, crawled_at,
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

    print(f"\n  스케줄 동기화: {writes}개 날짜 작성")
    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="더타임이스케이프 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
