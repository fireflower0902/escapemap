"""
지니어스이스케이프(geniusescape.kr) 테마 + 스케줄 DB 동기화 스크립트.

사이트: http://www.geniusescape.kr
플랫폼: JIJEM 계열 자체 PHP (EUC-KR, cafe24 호스팅)

지점:
  익산점  place_id=1394599334  area=etc  (전북특별자치도 익산시 모현동1가 868)

API:
  POST http://www.geniusescape.kr/sub/03_1_1.html
  Body: H_Date={YYYY-MM-DD}&D_ROOM={A~E}
  응답: EUC-KR HTML
    li 3개 구조: 시간 | 테마명 | 상태
    span.possibility "매진" → 예약불가
    a 태그 존재 → 예약가능

테마 (5개):
  A=잃어버린 기억, B=도플갱어, C=수상한 회사원, D=피의 성전, E=메이저리그

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_geniusescape_db.py
  uv run python scripts/sync_geniusescape_db.py --no-schedule
  uv run python scripts/sync_geniusescape_db.py --days 14
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

SITE_URL = "http://www.geniusescape.kr"
RESERVE_URL = SITE_URL + "/sub/03_1_1.html"
REQUEST_DELAY = 0.8

CAFE_ID = "1394599334"
CAFE_META = {
    "name":        "지니어스이스케이프",
    "branch_name": "",
    "address":     "전북특별자치도 익산시 모현동1가 868",
    "area":        "etc",
    "website_url": SITE_URL,
    "engine":      "geniusescape",
    "crawled":     True,
    "is_active":   True,
}

THEMES: dict[str, str] = {
    "A": "잃어버린 기억",
    "B": "도플갱어",
    "C": "수상한 회사원",
    "D": "피의 성전",
    "E": "메이저리그",
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
    "Content-Type": "application/x-www-form-urlencoded",
    "Referer": SITE_URL + "/",
}


def _fetch(room_code: str, target_date: date) -> str:
    date_str = target_date.strftime("%Y-%m-%d")
    body = urllib.parse.urlencode({
        "H_Date": date_str,
        "D_ROOM": room_code,
    }).encode()
    req = urllib.request.Request(RESERVE_URL, data=body, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            raw = resp.read()
    except Exception as e:
        print(f"  [WARN] POST {RESERVE_URL} ({room_code}/{date_str}) 실패: {e}")
        return ""
    try:
        return raw.decode("euc-kr", errors="replace")
    except Exception:
        return raw.decode("utf-8", errors="replace")


def _parse_slots(html: str, target_date: date) -> list[dict]:
    """
    li 3개 구조: 시간 | 테마명 | 상태
    span.possibility "매진" → full, a tag → available
    """
    soup = BeautifulSoup(html, "html.parser")
    slots = []

    # li 3개씩 묶어서 처리 (시간, 테마명, 상태)
    all_li = soup.find_all("li")
    i = 0
    while i + 2 < len(all_li):
        time_li = all_li[i]
        # 테마명 li = all_li[i+1] (검증용)
        status_li = all_li[i + 2]

        time_text = time_li.get_text(strip=True)
        if not re.match(r"^\d{2}:\d{2}$", time_text):
            i += 1
            continue

        # 상태 판단
        span_poss = status_li.find("span", class_="possibility")
        a_tag = status_li.find("a")

        if span_poss:
            poss_text = span_poss.get_text(strip=True)
            if "매진" in poss_text or "불가" in poss_text:
                status = "full"
                booking_url = None
            else:
                status = "available"
                booking_url = SITE_URL + "/sub/03_1_1.html"
        elif a_tag:
            status = "available"
            href = a_tag.get("href", "")
            booking_url = SITE_URL + href if href.startswith("/") else SITE_URL + "/sub/" + href
        else:
            i += 3
            continue

        slots.append({
            "time":        time_text,
            "status":      status,
            "booking_url": booking_url,
        })
        i += 3

    return slots


# ── DB 동기화 ─────────────────────────────────────────────────────────────────

def main(run_schedule: bool = True, days: int = 14):
    print("=" * 60)
    print("지니어스이스케이프(geniusescape.kr) → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)
    db = get_db()

    print("\n[ 1단계 ] 카페 메타 동기화")
    upsert_cafe(db, CAFE_ID, CAFE_META)
    print(f"  [UPSERT] 카페: 지니어스이스케이프 (id={CAFE_ID})")

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
    parser = argparse.ArgumentParser(description="지니어스이스케이프 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
