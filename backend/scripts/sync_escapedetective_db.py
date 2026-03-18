"""
방탈출탐정(escapecafe.co.kr) 테마 + 스케줄 DB 동기화 스크립트.

지점:
  수원점  cafe_id=779900297  https://www.escapecafe.co.kr/

예약 시스템: 자체 PHP CMS (leezeno 계열 추정)

API:
  GET https://www.escapecafe.co.kr/reservation/?theme_code={CODE}&yyyymmdd={YYYY-MM-DD}
  파라미터:
    theme_code = 테마 코드 (4자리 숫자)
    yyyymmdd   = 예약 날짜

HTML 구조:
  <div class="item">
    HH:MM
    <a href="./reseve_reg.php?theme_code=...&yyyymmdd=...&hhmm=HH:MM">예약가능</a>  ← 가능
    <!-- 예약완료인 경우 <a> 없이 텍스트만 -->
  </div>

테마 코드:
  1573110382  스토커
  1573112486  여고괴담
  1573626297  사라진 피카소
  1573626409  [3세대] 크라임씬 (화이트의 죽음)

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_escapedetective_db.py
  uv run python scripts/sync_escapedetective_db.py --no-schedule
  uv run python scripts/sync_escapedetective_db.py --days 14
"""

import re
import sys
import time
import urllib.request
import urllib.parse
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

CAFE_ID  = "779900297"
NAME     = "방탈출탐정"
ADDRESS  = "경기 수원시"
AREA     = "gyeonggi"
SITE_URL = "https://www.escapecafe.co.kr"
RESERVE_URL = SITE_URL + "/reservation/"

REQUEST_DELAY = 0.8

THEMES = [
    {"code": "1573110382", "name": "스토커"},
    {"code": "1573112486", "name": "여고괴담"},
    {"code": "1573626297", "name": "사라진 피카소"},
    {"code": "1573626409", "name": "[3세대] 크라임씬 (화이트의 죽음)"},
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": SITE_URL,
}


def _fetch(theme_code: str, target_date: date) -> bytes:
    url = RESERVE_URL + "?" + urllib.parse.urlencode({
        "theme_code": theme_code,
        "yyyymmdd": target_date.strftime("%Y-%m-%d"),
    })
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read()
    except Exception as e:
        print(f"  [WARN] GET {url} 실패: {e}")
        return b""


def _parse_slots(html: str, theme_code: str, target_date: date) -> list[dict]:
    """<div class="item">에서 슬롯 추출."""
    slots = []
    item_pattern = re.compile(
        r'class="item">\s*(\d{1,2}:\d{2})\s*(.*?)</div>',
        re.DOTALL
    )
    for m in item_pattern.finditer(html):
        time_str = m.group(1).strip()
        content  = m.group(2).strip()

        try:
            hh, mm = int(time_str.split(":")[0]), int(time_str.split(":")[1])
        except Exception:
            continue

        slot_dt = datetime(
            target_date.year, target_date.month, target_date.day, hh, mm
        )
        if slot_dt <= datetime.now():
            continue

        # 예약가능 링크가 있으면 available, 없으면 full
        is_available = 'href="./reseve_reg.php?' in content
        status = "available" if is_available else "full"

        booking_url = None
        if is_available:
            href_m = re.search(r'href="(./reseve_reg\.php\?[^"]+)"', content)
            if href_m:
                booking_url = SITE_URL + "/reservation/" + href_m.group(1)[2:]

        slots.append({
            "time":        f"{hh:02d}:{mm:02d}",
            "status":      status,
            "booking_url": booking_url,
        })

    return slots


# ── DB 동기화 ──────────────────────────────────────────────────────────────────

def sync(days: int) -> None:
    db = get_db()

    upsert_cafe(db, CAFE_ID, {
        "name":        NAME,
        "branch_name": "수원점",
        "address":     ADDRESS,
        "area":        AREA,
        "website_url": SITE_URL,
        "engine":      "escapedetective",
        "crawled":     True,
        "is_active":   True,
    })
    print(f"  [UPSERT] 카페: {NAME} (id={CAFE_ID})")

    # 테마 upsert
    code_to_doc: dict[str, str] = {}
    for t in THEMES:
        doc_id = get_or_create_theme(db, CAFE_ID, t["name"], {
            "poster_url": None,
            "is_active":  True,
        })
        code_to_doc[t["code"]] = doc_id
        print(f"  [UPSERT] 테마: {t['name']} ({t['code']})")

    today      = date.today()
    crawled_at = datetime.now()
    date_themes: dict[str, dict] = {}

    for day_offset in range(days + 1):
        target_date = today + timedelta(days=day_offset)
        date_str    = target_date.strftime("%Y-%m-%d")
        avail = full = 0

        for t in THEMES:
            raw = _fetch(t["code"], target_date)
            time.sleep(REQUEST_DELAY)
            if not raw:
                continue
            html   = raw.decode("utf-8", errors="replace")
            slots  = _parse_slots(html, t["code"], target_date)
            doc_id = code_to_doc[t["code"]]

            for slot in slots:
                date_themes.setdefault(date_str, {}).setdefault(
                    doc_id, {"slots": []}
                )["slots"].append({
                    "time":        slot["time"],
                    "status":      slot["status"],
                    "booking_url": slot["booking_url"],
                })
                if slot["status"] == "available":
                    avail += 1
                else:
                    full += 1

        print(f"  {date_str}: 가능 {avail} / 마감 {full}")

    # Firestore upsert
    known_hashes = load_cafe_hashes(db, CAFE_ID)
    new_hashes: dict[str, str] = {}
    writes = 0

    for date_str, themes in sorted(date_themes.items()):
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

    print(f"  스케줄 동기화: {writes}개 날짜 작성")


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main(run_schedule: bool = True, days: int = 14) -> None:
    print("=" * 60)
    print("방탈출탐정(escapecafe.co.kr) → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)

    if run_schedule:
        sync(days=days)
    else:
        db = get_db()
        upsert_cafe(db, CAFE_ID, {
            "name":        NAME,
            "branch_name": "수원점",
            "address":     ADDRESS,
            "area":        AREA,
            "website_url": SITE_URL,
            "engine":      "escapedetective",
            "crawled":     True,
            "is_active":   True,
        })
        print("  [SKIP] 스케줄 동기화 건너뜀")

    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="방탈출탐정 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
