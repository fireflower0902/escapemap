"""
트릭이스케이프(trickescape.com) 테마 + 스케줄 DB 동기화 스크립트.

사이트: http://www.trickescape.com
플랫폼: 자체 개발 PHP (EUC-KR, IIS 서버)

지점:
  의정부점  place_id=27504980  area=etc  (경기 의정부시 의정부동 197-4)

API:
  GET http://www.trickescape.com/sub/reservation.html
      ?chois={YYYYMMDD}&today_day={YYYYMMDD}&y={YYYY}&m={MM}&t={DD}
  응답: EUC-KR HTML
    li.conbox → 테마 섹션
      .bTit h2         → 테마명
      ul.timeTable > li > a.time        → 예약가능
      ul.timeTable > li > a.time.disable → 예약불가
      a > h3           → 시간 (HH:MM)

테마 (5개):
  호그와트, 감옥탈출, 뱀파이어의 저주, 마피아, 미스테리 연구소

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_trickescape_db.py
  uv run python scripts/sync_trickescape_db.py --no-schedule
  uv run python scripts/sync_trickescape_db.py --days 14
"""

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

SITE_URL = "http://www.trickescape.com"
RESERVE_URL = SITE_URL + "/sub/reservation.html"
BOOK_URL = SITE_URL + "/sub/reservation_form.html"
REQUEST_DELAY = 0.8

CAFE_ID = "27504980"
CAFE_META = {
    "name":        "트릭이스케이프",
    "branch_name": "",
    "address":     "경기 의정부시 의정부동 197-4",
    "area":        "etc",
    "website_url": SITE_URL,
    "engine":      "trickescape",
    "crawled":     True,
    "is_active":   True,
}

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": SITE_URL + "/sub/reservation.html",
}


def _fetch(target_date: date) -> str:
    y = target_date.strftime("%Y")
    m = target_date.strftime("%m")
    d = target_date.strftime("%d")
    ymd = target_date.strftime("%Y%m%d")
    url = f"{RESERVE_URL}?chois={ymd}&today_day={ymd}&y={y}&m={m}&t={d}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            raw = resp.read()
    except Exception as e:
        print(f"  [WARN] GET {url} 실패: {e}")
        return ""
    try:
        return raw.decode("euc-kr", errors="replace")
    except Exception:
        return raw.decode("utf-8", errors="replace")


def _parse_slots(html: str, target_date: date) -> dict[str, list[dict]]:
    """
    반환: {테마명 → [{time, status, booking_url}]}
    li.conbox > .bTit h2 = 테마명
    ul.timeTable > li > a.time / a.time.disable
    """
    soup = BeautifulSoup(html, "html.parser")
    result: dict[str, list[dict]] = {}

    for conbox in soup.find_all("li", class_="conbox"):
        # 테마명
        btit = conbox.find(class_="bTit")
        if not btit:
            continue
        h2 = btit.find(["h2", "h3"])
        if not h2:
            continue
        theme_name = h2.get_text(strip=True)
        # "(Hoguwarts)" 같은 영문 부분 제거
        theme_name = re.sub(r"\s*\(.*?\)\s*$", "", theme_name).strip()
        if not theme_name:
            continue

        time_table = conbox.find("ul", class_="timeTable")
        if not time_table:
            continue

        for li in time_table.find_all("li"):
            a_tag = li.find("a", class_="time")
            if not a_tag:
                continue

            # 시간
            h3 = a_tag.find("h3")
            if not h3:
                continue
            time_str = h3.get_text(strip=True)
            if not re.match(r"^\d{2}:\d{2}$", time_str):
                continue

            # 상태
            a_classes = a_tag.get("class", [])
            if "disable" in a_classes:
                status = "full"
                booking_url = None
            else:
                status = "available"
                href = a_tag.get("href", "")
                if href and href != "#":
                    booking_url = SITE_URL + href if href.startswith("/") else href
                else:
                    booking_url = BOOK_URL

            result.setdefault(theme_name, []).append({
                "time":        time_str,
                "status":      status,
                "booking_url": booking_url,
            })

    return result


# ── DB 동기화 ─────────────────────────────────────────────────────────────────

def main(run_schedule: bool = True, days: int = 14):
    print("=" * 60)
    print("트릭이스케이프(trickescape.com) → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)
    db = get_db()

    print("\n[ 1단계 ] 카페 메타 동기화")
    upsert_cafe(db, CAFE_ID, CAFE_META)
    print(f"  [UPSERT] 카페: 트릭이스케이프 (id={CAFE_ID})")

    if not run_schedule:
        print("\n동기화 완료 (스케줄 건너뜀)")
        return

    # 스케줄 upsert (테마 동적 발견)
    print(f"\n[ 2단계 ] 스케줄 동기화 (오늘~{days}일 후)")
    today = date.today()
    crawled_at = datetime.now()
    known_hashes = load_cafe_hashes(db, CAFE_ID)
    new_hashes: dict[str, str] = {}
    date_themes: dict[str, dict] = {}
    theme_cache: dict[str, str] = {}  # theme_name → doc_id

    for i in range(days + 1):
        target_date = today + timedelta(days=i)
        date_str = target_date.strftime("%Y-%m-%d")

        html = _fetch(target_date)
        time.sleep(REQUEST_DELAY)
        slots_by_theme = _parse_slots(html, target_date)
        avail = full = 0

        for theme_name, slots in slots_by_theme.items():
            if theme_name not in theme_cache:
                doc_id = get_or_create_theme(db, CAFE_ID, theme_name, {
                    "poster_url": None,
                    "is_active":  True,
                })
                theme_cache[theme_name] = doc_id
                print(f"  [UPSERT] 테마: {theme_name}")

            doc_id = theme_cache[theme_name]
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
    parser = argparse.ArgumentParser(description="트릭이스케이프 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
