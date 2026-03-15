"""
이스케이프하우스(escapehouse.co.kr) 테마 + 스케줄 DB 동기화 스크립트.

사이트: http://www.escapehouse.co.kr
플랫폼: 자체 PHP (레거시 커스텀)

지점:
  홍대점  cafe_id=340303350  area=hongdae  (서울 마포구 와우산로21길 28-9)

API:
  GET http://www.escapehouse.co.kr/view/thema.php?bdate={YYYY-MM-DD}&jiJeom=
  응답: <table class="tb_list"> 조각 (full HTML 아님)
    tr 단위 슬롯:
      td > img[alt] → 테마명
      td (3번째) → 시간 범위 (HH:MM ~ HH:MM)
      td (4번째):
        a.apply onClick="inBooking('테마명','HH:MM-HH:MM','gid','tcd')" → 예약가능
        a.soldout → 매진

예약 URL: http://www.escapehouse.co.kr/reservation.php (직접 슬롯 링크 없음)

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_escapehouse_db.py
  uv run python scripts/sync_escapehouse_db.py --no-schedule
  uv run python scripts/sync_escapehouse_db.py --days 14
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

from app.config import settings
from app.firestore_db import (
    init_firestore, get_db, upsert_cafe,
    get_or_create_theme, upsert_cafe_date_schedules,
    load_cafe_hashes, save_cafe_hashes,
)

SITE_URL = "http://www.escapehouse.co.kr"
API_URL = SITE_URL + "/view/thema.php"
BOOKING_URL = SITE_URL + "/reservation.php"
REQUEST_DELAY = 0.8

BRANCHES = [
    {
        "cafe_id":     "340303350",
        "branch_name": "홍대점",
        "area":        "hongdae",
        "address":     "서울 마포구 와우산로21길 28-9",
    },
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
    "Referer": SITE_URL + "/",
}


def _fetch(target_date: date) -> str:
    date_str = target_date.strftime("%Y-%m-%d")
    url = f"{API_URL}?bdate={date_str}&jiJeom="
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [WARN] GET {url} 실패: {e}")
        return ""


def parse_page(html: str) -> list[dict]:
    """
    테이블 HTML 파싱.
    반환: [{theme_name, time, status}]
    """
    slots: list[dict] = []

    row_pattern = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL)
    for m_row in row_pattern.finditer(html):
        row = m_row.group(1)

        # 테마명: img[alt]
        m_img = re.search(r'<img[^>]+alt="([^"]+)"', row)
        if not m_img:
            continue
        theme_name = m_img.group(1).strip()
        if not theme_name:
            continue

        # 시간: "HH:MM ~ HH:MM" 또는 "HH:MM-HH:MM" 중 시작 시간
        m_time = re.search(r"(\d{2}:\d{2})\s*[~\-]\s*\d{2}:\d{2}", row)
        if not m_time:
            continue
        time_str = m_time.group(1)

        # 상태: a.apply → 가능, a.soldout → 매진
        if re.search(r'<a[^>]+class="[^"]*apply[^"]*"', row):
            slots.append({"theme_name": theme_name, "time": time_str, "status": "available"})
        elif re.search(r'<a[^>]+class="[^"]*soldout[^"]*"', row):
            slots.append({"theme_name": theme_name, "time": time_str, "status": "full"})

    return slots


# ── DB 동기화 ─────────────────────────────────────────────────────────────────

def sync_cafe_meta(db, branch: dict) -> None:
    upsert_cafe(db, branch["cafe_id"], {
        "name":        "이스케이프하우스",
        "branch_name": branch["branch_name"],
        "address":     branch["address"],
        "area":        branch["area"],
        "website_url": SITE_URL,
        "engine":      "escapehouse",
        "crawled":     True,
        "is_active":   True,
    })
    print(f"  [UPSERT] 카페: 이스케이프하우스 {branch['branch_name']} (id={branch['cafe_id']})")


def sync_branch(branch: dict, days: int = 14) -> int:
    db = get_db()
    cafe_id = branch["cafe_id"]
    today = date.today()
    target_dates = [today + timedelta(days=i) for i in range(days + 1)]
    crawled_at = datetime.now()
    total_writes = 0

    cafe_doc = db.collection("cafes").document(cafe_id).get()
    if not cafe_doc.exists:
        print(f"  [WARN] cafe {cafe_id} Firestore 미존재 — 건너뜀")
        return 0

    theme_cache: dict[str, str] = {}
    date_themes: dict[str, dict] = {}

    for target_date in target_dates:
        date_str = target_date.strftime("%Y-%m-%d")
        html = _fetch(target_date)
        time.sleep(REQUEST_DELAY)

        if not html:
            print(f"  {date_str}: 데이터 없음")
            continue

        raw_slots = parse_page(html)
        if not raw_slots:
            print(f"  {date_str}: 슬롯 없음")
            continue

        avail_cnt = full_cnt = 0

        for slot in raw_slots:
            theme_name = slot["theme_name"]
            time_str = slot["time"]
            status = slot["status"]

            try:
                hh, mm = int(time_str[:2]), int(time_str[3:5])
            except Exception:
                continue

            slot_dt = datetime(
                target_date.year, target_date.month, target_date.day, hh, mm,
            )
            if slot_dt <= datetime.now():
                continue

            if theme_name not in theme_cache:
                doc_id = get_or_create_theme(db, cafe_id, theme_name, {
                    "poster_url": None,
                    "is_active":  True,
                })
                theme_cache[theme_name] = doc_id
                print(f"  [UPSERT] 테마: {theme_name}")
            theme_doc_id = theme_cache[theme_name]

            date_themes.setdefault(date_str, {}).setdefault(
                theme_doc_id, {"slots": []}
            )["slots"].append({
                "time":        f"{hh:02d}:{mm:02d}",
                "status":      status,
                "booking_url": BOOKING_URL if status == "available" else None,
            })

            if status == "available":
                avail_cnt += 1
            else:
                full_cnt += 1

        print(f"  {date_str}: 가능 {avail_cnt} / 마감 {full_cnt}")

    known_hashes = load_cafe_hashes(db, cafe_id)
    new_hashes: dict[str, str] = {}
    for date_str, themes_map in date_themes.items():
        h = upsert_cafe_date_schedules(
            db, date_str, cafe_id, themes_map, crawled_at,
            known_hash=known_hashes.get(date_str),
        )
        if h:
            new_hashes[date_str] = h
            total_writes += 1

    if new_hashes:
        today_str = today.isoformat()
        save_cafe_hashes(db, cafe_id, {
            k: v for k, v in {**known_hashes, **new_hashes}.items()
            if k >= today_str
        })

    print(f"  스케줄 동기화 완료: {total_writes}개 날짜 문서 작성")
    return total_writes


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main(run_schedule: bool = True, days: int = 14):
    print("=" * 60)
    print("이스케이프하우스(escapehouse.co.kr) → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)
    db = get_db()

    print("\n[ 1단계 ] 카페 메타 동기화")
    for branch in BRANCHES:
        sync_cafe_meta(db, branch)

    if run_schedule:
        for branch in BRANCHES:
            print(f"\n[ 2단계 ] {branch['branch_name']} 스케줄 동기화 (오늘~{days}일 후)")
            sync_branch(branch, days=days)

    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="이스케이프하우스 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
