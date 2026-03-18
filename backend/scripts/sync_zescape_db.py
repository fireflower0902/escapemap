"""
제트방탈출카페(zescape.co.kr) 테마 + 스케줄 DB 동기화 스크립트.

사이트: http://www.zescape.co.kr
플랫폼: 자체 PHP (UTF-8)

지점:
  울산점  place_id=1713311920  area=etc  (울산 중구 성남동 219-158)

API:
  GET http://www.zescape.co.kr/reservation.html?rdate={YYYY-MM-DD}
  응답: HTML
    div.col1 > div.row : 테마명 목록 (순서 일치)
    div.col2 > div.row : 슬롯 목록 (col1과 인덱스 일치)
      div.time           → 예약가능 (onclick에 time/prdno)
      div.time.disabled  → 예약불가

테마 (9개, prdno 13~21):
  13=태화여고의 괴담, 14=중화만두, 15=시크릿제트, 16=삐에로,
  17=연애편지, 18=캣츠앤도그, 19=지하묘지의비밀, 20=매직트레인, 21=올림푸스의초대

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_zescape_db.py
  uv run python scripts/sync_zescape_db.py --no-schedule
  uv run python scripts/sync_zescape_db.py --days 14
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

SITE_URL = "http://www.zescape.co.kr"
RESERVE_URL = SITE_URL + "/reservation.html"
REQUEST_DELAY = 0.8

CAFE_ID = "1713311920"
CAFE_META = {
    "name":        "제트방탈출카페",
    "branch_name": "",
    "address":     "울산 중구 성남동 219-158",
    "area":        "etc",
    "website_url": SITE_URL,
    "engine":      "zescape",
    "crawled":     True,
    "is_active":   True,
}

# prdno → 테마명
THEME_NAMES: dict[str, str] = {
    "13": "태화여고의 괴담",
    "14": "중화만두",
    "15": "시크릿제트",
    "16": "삐에로",
    "17": "연애편지",
    "18": "캣츠앤도그",
    "19": "지하묘지의비밀",
    "20": "매직트레인",
    "21": "올림푸스의초대",
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
    "Referer": SITE_URL + "/reservation.html",
}


def _fetch(target_date: date) -> str:
    date_str = target_date.strftime("%Y-%m-%d")
    url = f"{RESERVE_URL}?rdate={date_str}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [WARN] GET {url} 실패: {e}")
        return ""


def _parse_slots(html: str, target_date: date) -> dict[str, list[dict]]:
    """
    반환: {prdno → [{time, status, booking_url}]}
    col1/col2 인덱스 매칭으로 테마별 슬롯 추출.
    """
    soup = BeautifulSoup(html, "html.parser")
    result: dict[str, list[dict]] = {}

    col1 = soup.find("div", class_="col1")
    col2 = soup.find("div", class_="col2")
    if not col1 or not col2:
        return result

    col1_rows = col1.find_all("div", class_="row", recursive=False)
    col2_rows = col2.find_all("div", class_="row", recursive=False)

    # prdno를 인덱스로 대응 (테마 순서 col1 == col2)
    theme_order: list[str] = []
    for row in col1_rows:
        # 테마명에서 prdno 찾기: theme 링크에 prdno 있음
        link = row.find("a", href=re.compile(r"prdno=(\d+)"))
        if link:
            m = re.search(r"prdno=(\d+)", link["href"])
            if m:
                theme_order.append(m.group(1))
                continue
        # prdno 없으면 skip
        theme_order.append(None)

    for idx, (prdno, col2_row) in enumerate(zip(theme_order, col2_rows)):
        if prdno is None:
            continue
        row_inner = col2_row.find("div", class_="row_inner")
        if not row_inner:
            continue

        for div_time in row_inner.find_all("div", class_="time"):
            classes = div_time.get("class", [])
            time_text = div_time.get_text(strip=True)
            if not re.match(r"^\d{2}:\d{2}$", time_text):
                continue

            if "disabled" in classes:
                status = "full"
                booking_url = None
            else:
                status = "available"
                booking_url = SITE_URL + "/reservation.html"

            result.setdefault(prdno, []).append({
                "time":        time_text,
                "status":      status,
                "booking_url": booking_url,
            })

    return result


# ── DB 동기화 ─────────────────────────────────────────────────────────────────

def main(run_schedule: bool = True, days: int = 14):
    print("=" * 60)
    print("제트방탈출카페(zescape.co.kr) → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)
    db = get_db()

    print("\n[ 1단계 ] 카페 메타 동기화")
    upsert_cafe(db, CAFE_ID, CAFE_META)
    print(f"  [UPSERT] 카페: 제트방탈출카페 (id={CAFE_ID})")

    # 테마 upsert
    print("\n[ 2단계 ] 테마 동기화")
    theme_doc_map: dict[str, str] = {}  # prdno → doc_id
    for prdno, name in THEME_NAMES.items():
        doc_id = get_or_create_theme(db, CAFE_ID, name, {
            "poster_url": None,
            "is_active":  True,
        })
        theme_doc_map[prdno] = doc_id
        print(f"  [UPSERT] 테마: {name} (prdno={prdno})")

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

        html = _fetch(target_date)
        time.sleep(REQUEST_DELAY)
        slots_by_prdno = _parse_slots(html, target_date)
        avail = full = 0

        for prdno, slots in slots_by_prdno.items():
            doc_id = theme_doc_map.get(prdno)
            if not doc_id:
                continue
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
    parser = argparse.ArgumentParser(description="제트방탈출카페 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
