"""
keyescape.com 테마 + 스케줄을 DB에 동기화하는 스크립트.

API:
  [테마 목록]  POST /controller/run_proc.php  data: t=get_theme_info_list&zizum_num={N}
  [스케줄]    POST /controller/run_proc.php  data: t=get_theme_time&date={YYYY-MM-DD}&zizumNum={N}&themeNum={M}&endDay=0

응답 구조:
  테마: { status, data: [{theme_num, zizum_num, info_name, doing, memo}] }
  슬롯: { status, data: [{num, theme_num, hh, mm, enable: "Y"/"N"}] }

예약 가능 판별: enable == "Y"

실행:
  cd escape-aggregator/backend
  python scripts/sync_keyescape_db.py
  python scripts/sync_keyescape_db.py --no-schedule
  python scripts/sync_keyescape_db.py --days 3
"""

import re
import sys
import time
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import requests

from app.config import settings
from app.firestore_db import init_firestore, get_db, get_or_create_theme, upsert_schedule

BASE_URL = "https://keyescape.com/controller/run_proc.php"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://keyescape.com/reservation1.php",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
}
REQUEST_DELAY = 0.5

# zizum_num → 카카오 place_id (cafe.id)
BRANCH_MAP = {
    3:  "1405262610",  # 강남점
    14: "400448256",   # 강남 더오름
    16: "916422770",   # 우주라이크
    18: "459642234",   # 메모리컴퍼니
    19: "99889048",    # LOG_IN1
    20: "320987184",   # LOG_IN2
    22: "298789057",   # STATION
    23: "1872221698",  # 후즈데어
    10: "200411443",   # 홍대점
    9:  "1637143499",  # 부산점
    7:  "48992610",    # 전주점
}


# ── 크롤링 함수 ────────────────────────────────────────────────────────────────

def fetch_themes_for_branch(zizum_num: int) -> list[dict]:
    """지점 테마 목록 반환."""
    resp = requests.post(
        BASE_URL,
        data=f"t=get_theme_info_list&zizum_num={zizum_num}",
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("data", []) if data.get("status") else []


def fetch_schedule_for_theme(zizum_num: int, theme_num: int, target_date: date) -> list[dict]:
    """특정 날짜 슬롯 목록 반환."""
    resp = requests.post(
        BASE_URL,
        data=(
            f"t=get_theme_time"
            f"&date={target_date.strftime('%Y-%m-%d')}"
            f"&zizumNum={zizum_num}"
            f"&themeNum={theme_num}"
            f"&endDay=0"
        ),
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("data", []) if data.get("status") else []


def parse_duration(memo: str) -> int | None:
    """메모에서 소요 시간(분) 추출. 예: '시간: 60분' → 60"""
    m = re.search(r"시간\s*:\s*(\d+)\s*분", memo)
    if m:
        return int(m.group(1))
    return None


def parse_difficulty(memo: str) -> int | None:
    """메모에서 난이도 추출. 예: '난이도: 4' → 4"""
    m = re.search(r"난이도\s*:\s*(\d+)", memo)
    if m:
        val = int(m.group(1))
        return max(1, min(5, val))
    return None


# ── DB 동기화 함수 ─────────────────────────────────────────────────────────────

def sync_themes() -> dict[tuple[int, int], str]:
    """
    키이스케이프 테마를 Firestore에 upsert.
    반환: {(zizum_num, theme_num) → theme_doc_id}
    """
    db = get_db()
    key_to_doc_id: dict[tuple[int, int], str] = {}
    added = updated = 0

    for zizum_num, cafe_id in BRANCH_MAP.items():
        cafe_doc = db.collection("cafes").document(cafe_id).get()
        if not cafe_doc.exists:
            print(f"  [WARN] cafe {cafe_id} Firestore 미존재 — 건너뜀")
            continue

        raw_themes = fetch_themes_for_branch(zizum_num)
        time.sleep(REQUEST_DELAY)

        for rt in raw_themes:
            theme_num = rt["theme_num"]
            name = rt["info_name"]
            memo = rt.get("memo", "")

            duration = parse_duration(memo)
            difficulty = parse_difficulty(memo)
            description = memo.strip() if memo else None

            theme_doc_id = get_or_create_theme(db, cafe_id, name, {
                "difficulty": difficulty,
                "duration_min": duration,
                "description": description,
                "poster_url": None,
                "is_active": True,
            })
            key_to_doc_id[(zizum_num, theme_num)] = theme_doc_id
            print(f"  [UPSERT] {name} (cafe={cafe_id}) — {duration}분 난이도:{difficulty}")

    print(f"\n  테마 동기화 완료: {len(key_to_doc_id)}개")
    return key_to_doc_id


def sync_schedules(key_to_doc_id: dict[tuple[int, int], str], days: int = 6):
    """키이스케이프 스케줄을 Firestore에 upsert (오늘~days일 후)."""
    db = get_db()
    today = date.today()
    dates = [today + timedelta(days=i) for i in range(days + 1)]
    crawled_at = datetime.now()
    added = 0

    for zizum_num in BRANCH_MAP:
        cafe_id = BRANCH_MAP[zizum_num]
        # 이 지점의 테마 목록 수집
        raw_themes = fetch_themes_for_branch(zizum_num)
        time.sleep(REQUEST_DELAY)

        for rt in raw_themes:
            theme_num = rt["theme_num"]
            theme_doc_id = key_to_doc_id.get((zizum_num, theme_num))
            if not theme_doc_id:
                continue

            booking_base = f"https://keyescape.com/reservation1.php?zizum_num={zizum_num}"

            for d in dates:
                slots = fetch_schedule_for_theme(zizum_num, theme_num, d)
                time.sleep(REQUEST_DELAY)

                for slot in slots:
                    hh = int(slot["hh"])
                    mm = int(slot["mm"])
                    time_obj = dtime(hh, mm)
                    enable = slot.get("enable", "N")

                    if enable == "Y":
                        status = "available"
                        booking_url = booking_base
                    else:
                        status = "full"
                        booking_url = None

                    upsert_schedule(
                        db,
                        date_str=d.strftime("%Y-%m-%d"),
                        theme_doc_id=theme_doc_id,
                        cafe_id=cafe_id,
                        time_slot=f"{time_obj.hour:02d}:{time_obj.minute:02d}",
                        data={
                            "status": status,
                            "available_slots": None,
                            "booking_url": booking_url,
                            "crawled_at": crawled_at,
                        },
                    )
                    added += 1

            print(f"  zizum={zizum_num} theme={theme_num} {len(dates)}일치 완료")

    print(f"\n  스케줄 동기화 완료: {added}개 레코드 추가")


def main(run_schedule: bool = True, days: int = 6):
    print("=" * 60)
    print("keyescape.com → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)

    print("\n[ 1단계 ] 테마 동기화")
    key_to_doc_id = sync_themes()
    print(f"  테마 ID 매핑: {len(key_to_doc_id)}개")

    if run_schedule:
        print(f"\n[ 2단계 ] 스케줄 동기화 (오늘~{days}일 후)")
        sync_schedules(key_to_doc_id, days=days)

    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 생략")
    parser.add_argument("--days", type=int, default=6, help="스케줄 조회 일수")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
