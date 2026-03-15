"""
코난방탈출(conanescape.kr) 테마 + 스케줄 DB 동기화 스크립트.

사이트: http://conanescape.kr
플랫폼: 자체 PHP (레거시 커스텀)

지점:
  구로디지털단지역점  cafe_id=1757443413  area=etc  (서울 구로구 구로동 1124-54 3층)

API:
  POST http://conanescape.kr/sub/sub03_01.php
  Body: s_date={YYYY-MM-DD}
  응답 HTML:
    ul.res1-top > li → 테마 블록
      p.res-txt1 → "RoomN 테마명" (Room 접두사 제거)
      ul.res-time > li.active > a[href="/sub/sub03_01.php?idx={N}&s_date={DATE}&time={HH:MM}"]
        → 예약가능 슬롯 (예약완료 슬롯은 렌더링되지 않음)

예약 URL: http://conanescape.kr/sub/sub03_01.php?idx={N}&s_date={DATE}&time={HH:MM}

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_conanescape_db.py
  uv run python scripts/sync_conanescape_db.py --no-schedule
  uv run python scripts/sync_conanescape_db.py --days 14
"""

import re
import sys
import time
import urllib.parse
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

SITE_URL = "http://conanescape.kr"
API_URL = SITE_URL + "/sub/sub03_01.php"
REQUEST_DELAY = 0.8

BRANCHES = [
    {
        "cafe_id":     "1757443413",
        "branch_name": "구로디지털단지역점",
        "area":        "etc",
        "address":     "서울 구로구 구로동 1124-54 3층",
    },
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Content-Type": "application/x-www-form-urlencoded",
    "Referer": SITE_URL + "/sub/sub03_01.php",
}


def _fetch(target_date: date) -> str:
    date_str = target_date.strftime("%Y-%m-%d")
    data = urllib.parse.urlencode({"s_date": date_str}).encode()
    req = urllib.request.Request(API_URL, data=data, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
        try:
            return raw.decode("utf-8", errors="replace")
        except Exception:
            return raw.decode("euc-kr", errors="replace")
    except Exception as e:
        print(f"  [WARN] POST {API_URL} 실패: {e}")
        return ""


def parse_page(html: str) -> list[dict]:
    """
    예약 페이지 HTML 파싱.
    반환: [{theme_name, time, status, booking_url}]
    예약완료(full) 슬롯은 렌더링되지 않으므로 available 슬롯만 수집.
    """
    slots: list[dict] = []

    # 테마 블록: p.res-txt1 + ul.res-time 쌍 추출
    theme_block_pattern = re.compile(
        r'<p[^>]+class="[^"]*res-txt1[^"]*"[^>]*>(.*?)</p>.*?'
        r'<ul[^>]+class="[^"]*res-time[^"]*"[^>]*>(.*?)</ul>',
        re.DOTALL,
    )
    for m_block in theme_block_pattern.finditer(html):
        raw_name = m_block.group(1).strip()
        slots_html = m_block.group(2)

        # "RoomN 테마명" → "테마명" (Room 접두사 제거)
        theme_name = re.sub(r"^Room\d+\s*", "", raw_name).strip()
        if not theme_name:
            theme_name = raw_name

        # 가용 슬롯: li.active > a[href]
        avail_pattern = re.compile(
            r'<li[^>]+class="[^"]*active[^"]*"[^>]*>.*?'
            r'<a[^>]+href="(/sub/sub03_01\.php\?[^"]*time=(\d{2}:\d{2})[^"]*)"',
            re.DOTALL,
        )
        for m_slot in avail_pattern.finditer(slots_html):
            href = m_slot.group(1)
            time_str = m_slot.group(2)
            slots.append({
                "theme_name":  theme_name,
                "time":        time_str,
                "status":      "available",
                "booking_url": SITE_URL + href,
            })

    return slots


# ── DB 동기화 ─────────────────────────────────────────────────────────────────

def sync_cafe_meta(db, branch: dict) -> None:
    upsert_cafe(db, branch["cafe_id"], {
        "name":        "코난방탈출",
        "branch_name": branch["branch_name"],
        "address":     branch["address"],
        "area":        branch["area"],
        "website_url": SITE_URL,
        "engine":      "conanescape",
        "crawled":     True,
        "is_active":   True,
    })
    print(f"  [UPSERT] 카페: 코난방탈출 {branch['branch_name']} (id={branch['cafe_id']})")


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

        avail_cnt = 0

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
                "booking_url": slot["booking_url"],
            })
            avail_cnt += 1

        print(f"  {date_str}: 가능 {avail_cnt}")

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
    print("코난방탈출(conanescape.kr) → DB 동기화")
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
    parser = argparse.ArgumentParser(description="코난방탈출 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
