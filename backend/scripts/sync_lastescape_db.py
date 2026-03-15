"""
라스트이스케이프(lastescape.co.kr) 테마 + 스케줄 DB 동기화 스크립트.

사이트: http://lastescape.co.kr
플랫폼: Gnuboard + wz.bookingC.prm 실시간 예약 플러그인

API: POST http://lastescape.co.kr/g5/plugin/wz.bookingC.prm/step.1.skin.room.php
  Body: cp_code=&bo_table=reservation1&sch_day=YYYY-MM-DD&arr_rm_ix=
  응답: HTML
    h4.media-heading → 테마명 (span 텍스트)
    a.btn-time.cal_rm_list[data-time="HH:MM"] → 예약가능
    div.btn-time.closed span.time (HH시MM분) → 예약마감

지점:
  강남점 cafe_id=225341934 (서울 강남구 강남대로98길 20)

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_lastescape_db.py
  uv run python scripts/sync_lastescape_db.py --no-schedule
  uv run python scripts/sync_lastescape_db.py --days 14
"""

import re
import ssl
import sys
import time
import urllib.request
import urllib.parse
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings
from app.firestore_db import (
    init_firestore, get_db, upsert_cafe,
    get_or_create_theme, upsert_cafe_date_schedules,
    load_cafe_hashes, save_cafe_hashes,
)

SITE_URL = "http://lastescape.co.kr"
SLOT_API_URL = SITE_URL + "/g5/plugin/wz.bookingC.prm/step.1.skin.room.php"
BOOKING_PAGE_URL = SITE_URL + "/g5/bbs/board.php?bo_table=reservation1"
REQUEST_DELAY = 0.7

CAFE_ID = "225341934"

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Content-Type": "application/x-www-form-urlencoded",
    "Referer": BOOKING_PAGE_URL,
}


def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html)


def fetch_slots(target_date: date) -> list[dict]:
    """날짜별 슬롯 조회. 반환: [{name, poster_url, slots: [{time, status}]}]"""
    date_str = target_date.strftime("%Y-%m-%d")
    body = urllib.parse.urlencode({
        "cp_code": "",
        "bo_table": "reservation1",
        "sch_day": date_str,
        "arr_rm_ix": "",
    }).encode()
    req = urllib.request.Request(SLOT_API_URL, data=body, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [WARN] POST 실패 (date={date_str}): {e}")
        return []

    themes: list[dict] = []

    # 테마 블록 분리 (h4.media-heading 기준)
    # Each block contains theme name and time slots
    blocks = re.split(r'<h4[^>]*class="[^"]*media-heading[^"]*"', html)
    for block in blocks[1:]:
        # 테마명 추출
        m_name = re.search(r'<span[^>]*>\s*(.*?)\s*</span>', block, re.DOTALL)
        if not m_name:
            continue
        name = _strip_tags(m_name.group(1)).strip()
        if not name:
            continue

        # 포스터: 없음 (라스트이스케이프는 별도 포스터 이미지 없음)
        poster_url = None

        slots: list[dict] = []

        # 예약가능: a.btn-time.cal_rm_list
        for m_avail in re.finditer(
            r'<a[^>]+class="[^"]*btn-time[^"]*cal_rm_list[^"]*"[^>]+data-time="([^"]+)"[^>]*>',
            block
        ):
            time_str = m_avail.group(1)  # "HH:MM"
            slots.append({"time": time_str, "status": "available"})

        # 예약마감: div.btn-time.closed
        for m_full in re.finditer(
            r'<div[^>]+class="[^"]*btn-time[^"]*closed[^"]*"[^>]*>.*?<span[^>]*class="[^"]*time[^"]*"[^>]*>([^<]+)</span>',
            block, re.DOTALL
        ):
            time_raw = m_full.group(1).strip()  # "09시50분"
            m_t = re.search(r"(\d+)시(\d+)분", time_raw)
            if m_t:
                hh, mm = int(m_t.group(1)), int(m_t.group(2))
                time_str = f"{hh:02d}:{mm:02d}"
                slots.append({"time": time_str, "status": "full"})

        if slots:
            themes.append({"name": name, "poster_url": poster_url, "slots": slots})

    return themes


# ── DB 동기화 ─────────────────────────────────────────────────────────────────

def sync_cafe_meta(db) -> None:
    upsert_cafe(db, CAFE_ID, {
        "name":        "라스트이스케이프",
        "branch_name": "강남점",
        "address":     "서울 강남구 강남대로98길 20",
        "area":        "gangnam",
        "website_url": SITE_URL,
        "engine":      "lastescape",
        "crawled":     True,
        "is_active":   True,
    })
    print(f"  [UPSERT] 카페: 라스트이스케이프 강남점 (id={CAFE_ID})")


def sync_schedules(days: int = 14) -> None:
    db = get_db()
    today = date.today()
    target_dates = [today + timedelta(days=i) for i in range(days + 1)]
    crawled_at = datetime.now()
    total_writes = 0

    cafe_doc = db.collection("cafes").document(CAFE_ID).get()
    if not cafe_doc.exists:
        print(f"  [WARN] cafe {CAFE_ID} Firestore 미존재 — 건너뜀")
        return

    theme_cache: dict[str, str] = {}
    date_themes: dict[str, dict] = {}

    for target_date in target_dates:
        date_str = target_date.strftime("%Y-%m-%d")
        raw_themes = fetch_slots(target_date)
        time.sleep(REQUEST_DELAY)

        if not raw_themes:
            print(f"  {date_str}: 데이터 없음")
            continue

        avail_cnt = full_cnt = 0

        for t in raw_themes:
            name = t["name"]
            if name not in theme_cache:
                doc_id = get_or_create_theme(db, CAFE_ID, name, {
                    "poster_url": t.get("poster_url"),
                    "is_active":  True,
                })
                theme_cache[name] = doc_id
                print(f"  [UPSERT] 테마: {name}")
            theme_doc_id = theme_cache[name]

            for slot in t["slots"]:
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
                    "booking_url": BOOKING_PAGE_URL if status == "available" else None,
                })

                if status == "available":
                    avail_cnt += 1
                else:
                    full_cnt += 1

        print(f"  {date_str}: 가능 {avail_cnt} / 마감 {full_cnt}")

    known_hashes = load_cafe_hashes(db, CAFE_ID)
    new_hashes: dict[str, str] = {}
    for date_str, themes_map in date_themes.items():
        h = upsert_cafe_date_schedules(
            db, date_str, CAFE_ID, themes_map, crawled_at,
            known_hash=known_hashes.get(date_str),
        )
        if h:
            new_hashes[date_str] = h
            total_writes += 1

    if new_hashes:
        today_str = today.isoformat()
        save_cafe_hashes(db, CAFE_ID, {
            k: v for k, v in {**known_hashes, **new_hashes}.items()
            if k >= today_str
        })

    print(f"  스케줄 동기화 완료: {total_writes}개 날짜 문서 작성")


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main(run_schedule: bool = True, days: int = 14):
    print("=" * 60)
    print("라스트이스케이프(lastescape.co.kr) → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)
    db = get_db()

    print("\n[ 1단계 ] 카페 메타 동기화")
    sync_cafe_meta(db)

    if run_schedule:
        print(f"\n[ 2단계 ] 스케줄 동기화 (오늘~{days}일 후)")
        sync_schedules(days=days)

    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="라스트이스케이프 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
