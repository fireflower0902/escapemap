"""
플레이이스케이프(playescape.co.kr) 테마 + 스케줄 DB 동기화 스크립트.

사이트: http://www.playescape.co.kr
플랫폼: JIJEM 계열 자체 PHP (EUC-KR, cafe24 호스팅)

지점:
  원주점  place_id=1416262413  area=etc  (강원특별자치도 원주시 단계동 855-1)

API:
  GET http://www.playescape.co.kr/sub_02/sub02_1.html
      ?JIJEM=S2&D_ROOM={A~F}&H_Date={YYYY-MM-DD}
  응답: EUC-KR HTML
    .reservTime h3         → 테마명
    .time span             → 시간 (HH:MM)
    .possibility span      → 상태 텍스트 ("예약불가" or 예약가능)
    li style color:#aaa    → 예약불가 (어두운 색상)

테마 (6개):
  A=귀곡산장, B=007 다이아몬드, C=러브스토리,
  D=검은 그림자, E=폐쇄 병동, F=금잔화

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_playescape_db.py
  uv run python scripts/sync_playescape_db.py --no-schedule
  uv run python scripts/sync_playescape_db.py --days 14
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

SITE_URL = "http://www.playescape.co.kr"
RESERVE_URL = SITE_URL + "/sub_02/sub02_1.html"
BOOK_URL = SITE_URL + "/sub_02/sub02_1.html"
REQUEST_DELAY = 0.8

CAFE_ID = "1416262413"
CAFE_META = {
    "name":        "플레이이스케이프",
    "branch_name": "원주점",
    "address":     "강원특별자치도 원주시 단계동 855-1",
    "area":        "etc",
    "website_url": SITE_URL,
    "engine":      "playescape",
    "crawled":     True,
    "is_active":   True,
}

# 룸코드 → 테마명
THEMES: dict[str, str] = {
    "A": "귀곡산장",
    "B": "007 다이아몬드",
    "C": "러브스토리",
    "D": "검은 그림자",
    "E": "폐쇄 병동",
    "F": "금잔화",
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
    "Referer": SITE_URL + "/",
}


def _fetch(room_code: str, target_date: date) -> str:
    date_str = target_date.strftime("%Y-%m-%d")
    url = f"{RESERVE_URL}?JIJEM=S2&D_ROOM={room_code}&H_Date={date_str}"
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


def _parse_slots(html: str, target_date: date) -> list[dict]:
    """HTML에서 슬롯 목록 파싱. 반환: [{time, status, booking_url}]"""
    soup = BeautifulSoup(html, "html.parser")
    slots = []

    reserve_div = soup.find("div", class_="reservTime")
    if not reserve_div:
        return slots

    for li in reserve_div.find_all("li"):
        span_time = li.find("span", class_="time")
        span_poss = li.find("span", class_="possibility")
        if not span_time:
            continue
        time_str = span_time.get_text(strip=True)
        if not re.match(r"^\d{2}:\d{2}$", time_str):
            continue

        # 상태 판단: .possibility 텍스트 or 색상
        status = "available"
        if span_poss:
            poss_text = span_poss.get_text(strip=True)
            if "예약불가" in poss_text or "마감" in poss_text:
                status = "full"
            else:
                # 색상으로 판단: color:#aaa or #555 → full
                poss_style = span_poss.get("style", "")
                if "aaa" in poss_style or "#555" in poss_style:
                    status = "full"
        # li의 전체 스타일 확인
        if status == "available":
            li_style = li.get("style", "")
            time_style = span_time.get("style", "") if span_time else ""
            if "aaa" in time_style or "555" in time_style:
                status = "full"

        slots.append({
            "time":        time_str,
            "status":      status,
            "booking_url": BOOK_URL if status == "available" else None,
        })

    return slots


# ── DB 동기화 ─────────────────────────────────────────────────────────────────

def main(run_schedule: bool = True, days: int = 14):
    print("=" * 60)
    print("플레이이스케이프(playescape.co.kr) → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)
    db = get_db()

    print("\n[ 1단계 ] 카페 메타 동기화")
    upsert_cafe(db, CAFE_ID, CAFE_META)
    print(f"  [UPSERT] 카페: 플레이이스케이프 원주점 (id={CAFE_ID})")

    # 테마 upsert
    print("\n[ 2단계 ] 테마 동기화")
    theme_doc_map: dict[str, str] = {}  # room_code → doc_id
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
            slots = _parse_slots(html, target_date)

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
    parser = argparse.ArgumentParser(description="플레이이스케이프 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
