"""
코드케이(code-k.co.kr) 테마 + 스케줄 DB 동기화 스크립트.

사이트: http://www.code-k.co.kr
예약 시스템: http://codek5678.cafe24.com (Cafe24 JIJEM 계열 PHP)

지점:
  인천구월점  cafe_id=1475074228  area=incheon  (인천 남동구 구월동 1467-1)

API:
  GET http://codek5678.cafe24.com/sub/code_sub04_1.html?JIJEM_CODE=S1&CHOIS_DATE=YYYY-MM-DD
  응답: EUC-KR HTML
    <li class="thema1">테마명</li> → 테마별 섹션 구분
    <li class="timeOff">★ HH:MM</li> → 예약불가
    <a href="code_sub04_2.html?..."><li class="timeOn">☆ HH:MM</li></a> → 예약가능
  - JIJEM_CODE 파라미터는 서버에서 무시됨 (S1/S2/S3 동일 데이터 반환)
  - 예약 URL: code_sub04_2.html?chois_date=DATE&room_time=HH:MM&jijem_code=S1&room_code=codek_sN&room_name=...

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_codek_db.py
  uv run python scripts/sync_codek_db.py --no-schedule
  uv run python scripts/sync_codek_db.py --days 14
"""

import re
import ssl
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

SITE_URL = "http://www.code-k.co.kr"
BOOKING_BASE = "http://codek5678.cafe24.com"
SCHEDULE_URL = BOOKING_BASE + "/sub/code_sub04_1.html"
REQUEST_DELAY = 0.8

CAFE_ID = "1475074228"
BRANCH_NAME = "인천구월점"
AREA = "incheon"
ADDRESS = "인천 남동구 구월동 1467-1"

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": BOOKING_BASE + "/",
}


def _fetch(target_date: date) -> bytes:
    url = f"{SCHEDULE_URL}?JIJEM_CODE=S1&CHOIS_DATE={target_date.strftime('%Y-%m-%d')}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as r:
            return r.read()
    except Exception as e:
        print(f"  [WARN] GET {url} 실패: {e}")
        return b""


def _parse_page(raw: bytes, target_date: date) -> dict[str, list[dict]]:
    """
    HTML 파싱 → {theme_name: [{time, status, booking_url}]}
    테마 섹션은 <li class="thema1">테마명</li> 기준으로 분리.
    """
    try:
        html = raw.decode("euc-kr", errors="replace")
    except Exception:
        html = raw.decode("utf-8", errors="replace")

    # Split by theme section
    sections = re.split(r'<li\s+class="thema1">', html)
    if len(sections) < 2:
        return {}

    result: dict[str, list[dict]] = {}

    for section in sections[1:]:
        # Extract theme name (text before </li>)
        name_match = re.match(r"([^\n<]+)", section)
        if not name_match:
            continue
        theme_name = name_match.group(1).strip()
        if not theme_name:
            continue

        slots: list[dict] = []

        # Available slots: <a href="...room_time=HH:MM..."><li class="timeOn">
        for m in re.finditer(
            r'href="(code_sub04_2\.html\?[^"]+)">\s*<li\s+class="timeOn">',
            section
        ):
            href = m.group(1)
            t_match = re.search(r"room_time=([\d]{2}:[\d]{2})", href)
            if not t_match:
                continue
            time_str = t_match.group(1)
            booking_url = BOOKING_BASE + "/sub/" + href
            slots.append({
                "time": time_str,
                "status": "available",
                "booking_url": booking_url,
            })

        # Unavailable slots: <li class="timeOff">★ HH:MM</li> (not inside <a>)
        pos = 0
        for m in re.finditer(r'<li\s+class="timeOff">[^\d]*(\d{2}:\d{2})', section):
            before = section[max(0, m.start() - 60):m.start()]
            if "<a " in before:
                continue
            time_str = m.group(1)
            slots.append({
                "time": time_str,
                "status": "full",
                "booking_url": None,
            })

        if slots:
            result[theme_name] = slots

    return result


# ── DB 동기화 ──────────────────────────────────────────────────────────────────

def sync_cafe_meta(db) -> None:
    upsert_cafe(db, CAFE_ID, {
        "name":        "코드케이",
        "branch_name": BRANCH_NAME,
        "address":     ADDRESS,
        "area":        AREA,
        "website_url": SITE_URL,
        "engine":      "codek",
        "crawled":     True,
        "is_active":   True,
    })
    print(f"  [UPSERT] 카페: 코드케이 {BRANCH_NAME} (id={CAFE_ID})")


def sync_schedules(db, days: int = 14) -> None:
    today = date.today()
    crawled_at = datetime.now()

    # 테마 이름 → doc_id 매핑 (첫 날짜에서 수집)
    theme_doc_map: dict[str, str] = {}

    # date_str → {theme_doc_id: {slots: [...]}}
    date_themes: dict[str, dict] = {}

    for i in range(days + 1):
        target_date = today + timedelta(days=i)
        date_str = target_date.strftime("%Y-%m-%d")

        raw = _fetch(target_date)
        time.sleep(REQUEST_DELAY)
        if not raw:
            continue

        theme_slots = _parse_page(raw, target_date)
        avail = full = 0

        for theme_name, slots in theme_slots.items():
            # Upsert theme if new
            if theme_name not in theme_doc_map:
                doc_id = get_or_create_theme(db, CAFE_ID, theme_name, {
                    "poster_url": None,
                    "is_active":  True,
                })
                theme_doc_map[theme_name] = doc_id
                print(f"  [UPSERT] 테마: {theme_name}")

            doc_id = theme_doc_map[theme_name]

            for slot in slots:
                time_str = slot["time"]
                try:
                    hh, mm = int(time_str[:2]), int(time_str[3:5])
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

    print(f"\n  스케줄 동기화 완료: {writes}개 날짜 문서 작성")


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main(run_schedule: bool = True, days: int = 14) -> None:
    print("=" * 60)
    print("코드케이(code-k.co.kr) → DB 동기화")
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
    parser = argparse.ArgumentParser(description="코드케이 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
