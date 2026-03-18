"""
더코드(thecode-escape.com) 테마 + 스케줄 DB 동기화 스크립트.

사이트: http://www.thecode-escape.com
플랫폼: 자체 PHP (EUC-KR, cafe24 호스팅)

지점:
  광주 치평점  place_id=680681357  area=gwangju  (광주 서구 치평동 1230-2)

API:
  GET http://www.thecode-escape.com/sub/code_sub03.html
      ?chois_date={YYYY-MM-DD}&r_thema={esc_01|esc_02|...|esc_10}
  응답: EUC-KR HTML
    div.on  → 예약가능 (a href에 booking_url 포함)
    div.off → 예약불가
    span.time → 시간 (HH:MM)
    booking_url: /sub/code_sub03_1.html?CHOIS_DATE=...&ROOM_CODE=...&ROOM_TIME=...&room_name=...

테마 (10개):
  esc_01=타짜, esc_02=경찰서를털어라, esc_03=곤지암, esc_04=미생,
  esc_05=나홀로집에, esc_06=도둑들, esc_07=탈옥, esc_08=탐정,
  esc_09=비밀의방, esc_10=비밀요원

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_thecode_db.py
  uv run python scripts/sync_thecode_db.py --no-schedule
  uv run python scripts/sync_thecode_db.py --days 14
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

SITE_URL = "http://www.thecode-escape.com"
RESERVE_URL = SITE_URL + "/sub/code_sub03.html"
REQUEST_DELAY = 0.8

CAFE_ID = "680681357"
CAFE_META = {
    "name":        "더코드",
    "branch_name": "",
    "address":     "광주 서구 치평동 1230-2",
    "area":        "gwangju",
    "website_url": SITE_URL,
    "engine":      "thecode",
    "crawled":     True,
    "is_active":   True,
}

# 테마 코드 → 테마명
THEMES: dict[str, str] = {
    "esc_01": "타짜",
    "esc_02": "경찰서를털어라",
    "esc_03": "곤지암",
    "esc_04": "미생",
    "esc_05": "나홀로집에",
    "esc_06": "도둑들",
    "esc_07": "탈옥",
    "esc_08": "탐정",
    "esc_09": "비밀의방",
    "esc_10": "비밀요원",
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
    "Referer": SITE_URL + "/sub/code_sub03.html",
}


def _fetch(theme_code: str, target_date: date) -> str:
    """날짜 + 테마코드별 예약 페이지 HTML 반환 (EUC-KR 디코딩)."""
    date_str = target_date.strftime("%Y-%m-%d")
    url = f"{RESERVE_URL}?chois_date={date_str}&r_thema={theme_code}"
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


def _parse_slots(html: str, theme_name: str, target_date: date) -> list[dict]:
    """HTML에서 슬롯 목록 파싱. 반환: [{time, status, booking_url}]"""
    soup = BeautifulSoup(html, "html.parser")
    slots = []

    # 예약가능: <a href="..."><div class="on"><span class="time">HH:MM</span>...
    for a_tag in soup.find_all("a", href=True):
        div_on = a_tag.find("div", class_="on")
        if not div_on:
            continue
        span_time = div_on.find("span", class_="time")
        if not span_time:
            continue
        time_str = span_time.get_text(strip=True)
        if not re.match(r"^\d{2}:\d{2}$", time_str):
            continue
        href = a_tag["href"]
        if href.startswith("http"):
            booking_url = href
        elif href.startswith("/"):
            booking_url = SITE_URL + href
        else:
            booking_url = SITE_URL + "/sub/" + href
        slots.append({
            "time":        time_str,
            "status":      "available",
            "booking_url": booking_url,
        })

    # 예약불가: <div class="off"><span class="time">HH:MM</span>...
    for div_off in soup.find_all("div", class_="off"):
        span_time = div_off.find("span", class_="time")
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

    return slots


# ── DB 동기화 ─────────────────────────────────────────────────────────────────

def main(run_schedule: bool = True, days: int = 14):
    print("=" * 60)
    print("더코드(thecode-escape.com) → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)
    db = get_db()

    print("\n[ 1단계 ] 카페 메타 동기화")
    upsert_cafe(db, CAFE_ID, CAFE_META)
    print(f"  [UPSERT] 카페: 더코드 (id={CAFE_ID})")

    # 테마 upsert
    print("\n[ 2단계 ] 테마 동기화")
    theme_doc_map: dict[str, str] = {}
    for code, name in THEMES.items():
        doc_id = get_or_create_theme(db, CAFE_ID, name, {
            "poster_url": None,
            "is_active":  True,
        })
        theme_doc_map[code] = doc_id
        print(f"  [UPSERT] 테마: {name} (code={code})")

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

        for code, doc_id in theme_doc_map.items():
            html = _fetch(code, target_date)
            time.sleep(REQUEST_DELAY)
            slots = _parse_slots(html, THEMES[code], target_date)

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
    parser = argparse.ArgumentParser(description="더코드 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
