"""
앨리스이스케이프(alice-escape.com) 테마 + 스케줄 DB 동기화 스크립트.

사이트: http://alice-escape.com
플랫폼: 자체 PHP (EUC-KR, IIS/ASP.NET)

지점:
  동성로점  place_id=338628640  area=daegu  (대구 중구 동성로2가 151-3)

API:
  GET http://alice-escape.com/sub/03_1.html
      ?JIJEM_CODE=&CHOIS_DATE={YYYY-MM-DD}
  응답: EUC-KR HTML
    div.reservTime → 테마 블록
      h3 → 테마명
      a href="03_2.html?...ROOM_TIME=HH:MM..." → 예약가능 슬롯
        li > span.possibility "예약가능"
      li (no a) > span.possibility "예약불가" → 예약불가 슬롯
        span.time → HH:MM

테마 (9개):
  아빠의 서재, 금두꺼비, 달빛 서커스, 왕따 교실, 레드 주식회사,
  환상 크루즈, 사가와 잇세이, 지퍼스 크리퍼스, 동성로 앨리스

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_aliceescape_db.py
  uv run python scripts/sync_aliceescape_db.py --no-schedule
  uv run python scripts/sync_aliceescape_db.py --days 14
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

SITE_URL = "http://alice-escape.com"
RESERVE_URL = SITE_URL + "/sub/03_1.html"
REQUEST_DELAY = 0.8

CAFE_ID = "338628640"
CAFE_META = {
    "name":        "앨리스이스케이프",
    "branch_name": "",
    "address":     "대구 중구 동성로2가 151-3",
    "area":        "daegu",
    "website_url": SITE_URL,
    "engine":      "aliceescape",
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
    "Referer": SITE_URL + "/sub/03_1.html",
}


def _fetch(target_date: date) -> str:
    date_str = target_date.strftime("%Y-%m-%d")
    url = f"{RESERVE_URL}?JIJEM_CODE=&CHOIS_DATE={date_str}"
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


def _parse_themes(html: str) -> dict[str, list[dict]]:
    """
    반환: {테마명 → [{time, status, booking_url}]}
    div.reservTime 단위로 테마 파싱.
    """
    soup = BeautifulSoup(html, "html.parser")
    result: dict[str, list[dict]] = {}

    for block in soup.find_all("div", class_="reservTime"):
        h3 = block.find("h3")
        if not h3:
            continue
        theme_name = h3.get_text(strip=True)
        if not theme_name:
            continue

        slots: list[dict] = []

        # 예약가능: a href 포함 (ROOM_TIME 파라미터)
        for a_tag in block.find_all("a", href=True):
            href = a_tag["href"]
            m = re.search(r"ROOM_TIME=([^&]+)", href, re.IGNORECASE)
            if not m:
                continue
            time_str = m.group(1).strip()
            if not re.match(r"^\d{2}:\d{2}$", time_str):
                continue
            booking_url = SITE_URL + "/sub/" + href if not href.startswith("http") else href
            slots.append({
                "time":        time_str,
                "status":      "available",
                "booking_url": booking_url,
            })

        # 예약불가: li without a, with span.possibility "예약불가"
        for li in block.find_all("li"):
            if li.find("a"):
                continue  # skip available slots
            poss = li.find("span", class_="possibility")
            if not poss or "예약불가" not in poss.get_text():
                continue
            span_time = li.find("span", class_="time")
            if not span_time:
                continue
            time_str = span_time.get_text(strip=True)
            if not re.match(r"^\d{2}:\d{2}$", time_str):
                continue
            slots.append({
                "time":        time_str,
                "status":      "full",
                "booking_url": None,
            })

        if slots:
            result[theme_name] = slots

    return result


# ── DB 동기화 ─────────────────────────────────────────────────────────────────

def main(run_schedule: bool = True, days: int = 14):
    print("=" * 60)
    print("앨리스이스케이프(alice-escape.com) → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)
    db = get_db()

    print("\n[ 1단계 ] 카페 메타 동기화")
    upsert_cafe(db, CAFE_ID, CAFE_META)
    print(f"  [UPSERT] 카페: 앨리스이스케이프 (id={CAFE_ID})")

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
        themes_map = _parse_themes(html)
        avail = full = 0

        for theme_name, slots in themes_map.items():
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
    parser = argparse.ArgumentParser(description="앨리스이스케이프 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
