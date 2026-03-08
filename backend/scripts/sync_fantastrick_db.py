"""
판타스트릭 강남1호점 테마 + 스케줄 DB 동기화 스크립트.

사이트: http://fantastrick.co.kr/
플랫폼: WordPress + Booked 예약 플러그인

API:
  POST http://fantastrick.co.kr/wp-admin/admin-ajax.php
  Body: action=booked_calendar_date&date=YYYY-MM-DD&calendar_id=N
  응답: HTML (div.timeslot > button + span.spots-available)
  - span.spots-available 텍스트 "예약가능" → available
  - span.spots-available 텍스트 "예약완료" → full
  - button[data-timeslot="HHMM-HHMM"] → 시작 시간 파싱

테마 (calendar_id):
  - 태초의 신부: 17
  - 사자의 서:   23
  - LOCKDOWN CITY: 24

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_fantastrick_db.py
  uv run python scripts/sync_fantastrick_db.py --no-schedule
  uv run python scripts/sync_fantastrick_db.py --days 3
"""

import re
import sys
import time
import urllib.request
import urllib.parse
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from bs4 import BeautifulSoup

from app.config import settings
from app.firestore_db import init_firestore, get_db, get_or_create_theme, upsert_cafe_date_schedules, load_cafe_hashes, save_cafe_hashes

AJAX_URL = "http://fantastrick.co.kr/wp-admin/admin-ajax.php"
BOOKING_URL = "http://fantastrick.co.kr/booking/"
REQUEST_DELAY = 0.8

# 테마 정의: 각 테마별 cafe_id (지점별로 다름)
# 1호점 (강남대로79길 39, cafe_id=1421844037): 태초의 신부
# 2호점 (사평대로 353,  cafe_id=192767471):   사자의 서
# 3호점 (강남대로83길 34, cafe_id=2020129484): LOCKDOWN CITY (판타스트릭TGC)
THEMES = [
    {
        "cafe_id": "1421844037",  # 1호점
        "name": "태초의 신부",
        "calendar_id": 17,
        "slug": "firstfoundbride",
        "poster_url": "http://fantastrick.co.kr/wp-content/uploads/2018/10/poster-scaled.jpg",
    },
    {
        "cafe_id": "192767471",   # 2호점
        "name": "사자의 서",
        "calendar_id": 23,
        "slug": "bookofduat",
        "poster_url": None,
    },
    {
        "cafe_id": "2020129484",  # 3호점 (판타스트릭TGC, 강남대로83길 34)
        "name": "LOCKDOWN CITY",
        "calendar_id": 24,
        "slug": "ldc",
        "poster_url": None,
    },
]


def _fetch_room_info(slug: str) -> dict:
    """테마 rooms 페이지에서 포스터 이미지와 calendar_id 파싱."""
    url = f"http://fantastrick.co.kr/rooms/{slug}/"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", errors="ignore")
        soup = BeautifulSoup(html, "html.parser")
        # calendar_id
        table = soup.find("table", class_="booked-calendar")
        cal_id = int(table["data-calendar-id"]) if table else None
        # 포스터: wp-content/uploads 이미지 중 poster 포함된 첫 번째
        poster = None
        for img in soup.find_all("img"):
            src = img.get("src", "")
            if "fantastrick.co.kr/wp-content/uploads" in src and "poster" in src.lower():
                poster = src
                break
        return {"calendar_id": cal_id, "poster_url": poster}
    except Exception as e:
        print(f"  [WARN] {slug} rooms 페이지 파싱 실패: {e}")
        return {"calendar_id": None, "poster_url": None}


def _fetch_slots(calendar_id: int, target_date: date) -> list[dict]:
    """Booked AJAX API로 날짜별 슬롯 조회."""
    date_str = target_date.strftime("%Y-%m-%d")
    body = urllib.parse.urlencode({
        "action": "booked_calendar_date",
        "date": date_str,
        "calendar_id": str(calendar_id),
    }).encode()
    req = urllib.request.Request(
        AJAX_URL,
        data=body,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": BOOKING_URL,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"  [WARN] slots 조회 실패 calendar_id={calendar_id} date={date_str}: {e}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    slots = []
    for slot_div in soup.find_all("div", class_="timeslot"):
        btn = slot_div.find("button")
        if not btn:
            continue
        timeslot = btn.get("data-timeslot", "")  # "HHMM-HHMM"
        if not timeslot or "-" not in timeslot:
            continue
        start_str = timeslot.split("-")[0]  # "HHMM"
        if len(start_str) != 4:
            continue
        hh = int(start_str[:2])
        mm = int(start_str[2:])
        # 예약 가능 여부
        avail_span = slot_div.find("span", class_="spots-available")
        if avail_span:
            status = "available" if "예약가능" in avail_span.text else "full"
        else:
            status = "full"
        slots.append({
            "time": dtime(hh, mm),
            "status": status,
        })
    return slots


# ── DB 동기화 ──────────────────────────────────────────────────────────────────

def sync_themes() -> dict[int, str]:
    """판타스트릭 테마를 Firestore에 upsert.
    반환: {calendar_id → theme_doc_id}
    """
    db = get_db()
    cal_to_doc_id: dict[int, str] = {}

    for t in THEMES:
        cafe_id = t["cafe_id"]
        name = t["name"]
        cal_id = t["calendar_id"]
        poster = t.get("poster_url")

        cafe_doc = db.collection("cafes").document(cafe_id).get()
        if not cafe_doc.exists:
            print(f"  [ERROR] cafe {cafe_id} Firestore 미존재 — {name} 건너뜀")
            continue

        # rooms 페이지에서 추가 정보 갱신
        info = _fetch_room_info(t["slug"])
        if info["calendar_id"]:
            cal_id = info["calendar_id"]
        if info["poster_url"]:
            poster = info["poster_url"]
        time.sleep(REQUEST_DELAY)

        theme_doc_id = get_or_create_theme(db, cafe_id, name, {
            "difficulty": None,
            "duration_min": None,
            "poster_url": poster,
            "is_active": True,
        })
        cal_to_doc_id[cal_id] = theme_doc_id
        print(f"  [UPSERT] {name} (cafe={cafe_id}) calendar_id={cal_id}")

    print(f"\n  테마 동기화 완료: {len(cal_to_doc_id)}개")
    return cal_to_doc_id


def sync_schedules(cal_to_doc_id: dict[int, str], days: int = 6):
    """판타스트릭 스케줄을 Firestore에 upsert (오늘~days일 후)."""
    db = get_db()
    today = date.today()
    target_dates = [today + timedelta(days=i) for i in range(days + 1)]
    crawled_at = datetime.now()
    writes = 0

    # calendar_id → cafe_id 역매핑 구성
    cal_to_cafe: dict[int, str] = {}
    for t in THEMES:
        cal_to_cafe[t["calendar_id"]] = t["cafe_id"]

    for cal_id, theme_doc_id in cal_to_doc_id.items():
        cafe_id = cal_to_cafe.get(cal_id, "")

        # {date_str: {theme_doc_id: {"slots": [...]}}}
        date_themes: dict[str, dict] = {}

        for target_date in target_dates:
            slots = _fetch_slots(cal_id, target_date)
            time.sleep(REQUEST_DELAY)

            date_str = target_date.strftime("%Y-%m-%d")
            for slot in slots:
                time_obj = slot["time"]
                status = slot["status"]

                slot_dt = datetime(
                    target_date.year, target_date.month, target_date.day,
                    time_obj.hour, time_obj.minute,
                )
                if slot_dt <= datetime.now():
                    continue

                booking_url = BOOKING_URL if status == "available" else None

                date_themes.setdefault(date_str, {}).setdefault(theme_doc_id, {"slots": []})["slots"].append({
                    "time": f"{time_obj.hour:02d}:{time_obj.minute:02d}",
                    "status": status,
                    "booking_url": booking_url,
                })

        known_hashes = load_cafe_hashes(db, cafe_id)
        new_hashes: dict[str, str] = {}
        for date_str, themes in date_themes.items():
            h = upsert_cafe_date_schedules(db, date_str, cafe_id, themes, crawled_at,
                                           known_hash=known_hashes.get(date_str))
            if h:
                new_hashes[date_str] = h
                writes += 1
        if new_hashes:
            today_str = date.today().isoformat()
            save_cafe_hashes(db, cafe_id, {k: v for k, v in {**known_hashes, **new_hashes}.items() if k >= today_str})

        print(f"  calendar_id={cal_id} 완료")

    print(f"\n  스케줄 동기화 완료: {writes}개 날짜 문서 작성")


def main(run_schedule: bool = True, days: int = 6):
    print("=" * 60)
    print("판타스트릭 강남1호점 → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)

    print("\n[ 1단계 ] 테마 동기화")
    cal_to_doc_id = sync_themes()
    print(f"  calendar_id 매핑: {cal_to_doc_id}")

    if run_schedule and cal_to_doc_id:
        print(f"\n[ 2단계 ] 스케줄 동기화 (오늘~{days}일 후)")
        sync_schedules(cal_to_doc_id, days=days)

    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-schedule", action="store_true")
    parser.add_argument("--days", type=int, default=6)
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
