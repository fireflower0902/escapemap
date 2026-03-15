"""
더메이즈 건대점(themazegd.co.kr) 테마 + 스케줄 DB 동기화 스크립트.

사이트: http://www.themazegd.co.kr
플랫폼: Gnuboard 기반 자체 PHP

지점:
  건대점  cafe_id=138006966  area=konkuk  (서울 광진구 아차산로26길 13 지하1층)

API:
  GET http://www.themazegd.co.kr/bbs/ajax.get_room.php?date={YYYY-MM-DD}
  응답: HTML fragment
    ul.theme_list > li → 테마 블록
      div.in_cont h3 → 테마명 (■ 접두사 제거)
      a[room_id="N"] → 룸 ID
    ul.time_list > li > a[room_time="HH:MM"] → 슬롯
      p.poss  → 예약가능
      p.sold  → 예약불가
      p.select → 선택됨(예약불가처리)

예약 URL: http://www.themazegd.co.kr/theme/themaze/03/res01.php

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_themazegd_db.py
  uv run python scripts/sync_themazegd_db.py --no-schedule
  uv run python scripts/sync_themazegd_db.py --days 14
"""

import re
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

SITE_URL = "http://www.themazegd.co.kr"
API_URL = SITE_URL + "/bbs/ajax.get_room.php"
BOOKING_URL = SITE_URL + "/theme/themaze/03/res01.php"
REQUEST_DELAY = 0.8

BRANCHES = [
    {
        "cafe_id":     "138006966",
        "branch_name": "건대점",
        "area":        "konkuk",
        "address":     "서울 광진구 아차산로26길 13 지하1층",
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
    "Referer": BOOKING_URL,
    "X-Requested-With": "XMLHttpRequest",
}


def _fetch(target_date: date) -> str:
    date_str = target_date.strftime("%Y-%m-%d")
    url = f"{API_URL}?date={date_str}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
        try:
            return raw.decode("utf-8", errors="replace")
        except Exception:
            return raw.decode("euc-kr", errors="replace")
    except Exception as e:
        print(f"  [WARN] GET {url} 실패: {e}")
        return ""


def parse_rooms(html: str) -> list[dict]:
    """
    HTML fragment 파싱.
    반환: [{name: str, slots: [{time, status}]}]
    """
    rooms: list[dict] = []

    # 테마 블록: theme_list > li 분리
    # 테마명: h3 텍스트 (■ 제거)
    # room_id: a[room_id="N"]
    # 슬롯: time_list > li > a[room_time="HH:MM"] + p.poss/sold
    theme_blocks = re.split(r'<li[^>]*class="[^"]*theme_item[^"]*"', html)
    if len(theme_blocks) <= 1:
        # 다른 분리 시도: li 단위
        theme_blocks = re.split(r'<li\b', html)

    # 더 안정적인 파싱: h3에서 테마명, time_list에서 슬롯 추출
    # 전체 HTML에서 테마 블록 단위 추출
    block_pattern = re.compile(
        r'<div[^>]+class="[^"]*in_cont[^"]*"[^>]*>(.*?)</div>.*?'
        r'<ul[^>]+class="[^"]*time_list[^"]*"[^>]*>(.*?)</ul>',
        re.DOTALL,
    )

    for m_block in block_pattern.finditer(html):
        info_html = m_block.group(1)
        slots_html = m_block.group(2)

        # 테마명
        m_name = re.search(r'<h3[^>]*>([^<]+)</h3>', info_html)
        if not m_name:
            continue
        name = re.sub(r'^■\s*', '', m_name.group(1).strip())
        if not name:
            continue

        slots: list[dict] = []
        # 슬롯: a[room_time="HH:MM"]
        for m_slot in re.finditer(
            r'<a[^>]+room_time="(\d{2}:\d{2})"[^>]*>(.*?)</a>',
            slots_html, re.DOTALL,
        ):
            time_str = m_slot.group(1)
            slot_content = m_slot.group(2)
            if 'poss' in slot_content:
                slots.append({"time": time_str, "status": "available"})
            elif 'sold' in slot_content or 'select' in slot_content:
                slots.append({"time": time_str, "status": "full"})

        if slots:
            rooms.append({"name": name, "slots": slots})

    return rooms


# ── DB 동기화 ─────────────────────────────────────────────────────────────────

def sync_cafe_meta(db, branch: dict) -> None:
    upsert_cafe(db, branch["cafe_id"], {
        "name":        "더메이즈",
        "branch_name": branch["branch_name"],
        "address":     branch["address"],
        "area":        branch["area"],
        "website_url": SITE_URL,
        "engine":      "themazegd",
        "crawled":     True,
        "is_active":   True,
    })
    print(f"  [UPSERT] 카페: 더메이즈 {branch['branch_name']} (id={branch['cafe_id']})")


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
        raw_html = _fetch(target_date)
        time.sleep(REQUEST_DELAY)

        if not raw_html:
            print(f"  {date_str}: 데이터 없음")
            continue

        rooms = parse_rooms(raw_html)
        if not rooms:
            print(f"  {date_str}: 슬롯 없음")
            continue

        avail_cnt = full_cnt = 0

        for room in rooms:
            name = room["name"]
            if name not in theme_cache:
                doc_id = get_or_create_theme(db, cafe_id, name, {
                    "poster_url": None,
                    "is_active":  True,
                })
                theme_cache[name] = doc_id
                print(f"  [UPSERT] 테마: {name}")
            theme_doc_id = theme_cache[name]

            for slot in room["slots"]:
                time_str = slot["time"]
                try:
                    hh, mm = int(time_str[:2]), int(time_str[3:5])
                except Exception:
                    continue

                slot_dt = datetime(
                    target_date.year, target_date.month, target_date.day, hh, mm,
                )
                if slot_dt <= datetime.now():
                    continue

                status = slot["status"]
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
    print("더메이즈 건대점(themazegd.co.kr) → DB 동기화")
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
    parser = argparse.ArgumentParser(description="더메이즈 건대점 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
