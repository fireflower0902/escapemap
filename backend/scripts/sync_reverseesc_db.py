"""
리버스이스케이프(reverseesc.com) 테마 + 스케줄 DB 동기화 스크립트.

사이트: http://reverseesc.com
플랫폼: Node.js/Express 자체 API

지점:
  향남점  cafe_id=21592693   area=gyeonggi  (경기 화성시 향남읍 향남로 459)
  안산점  cafe_id=1095782451  area=gyeonggi  (경기 안산시 단원구 광덕대로 130)

API:
  GET http://reverseesc.com/service/get_data
  → 인증 없음, 전체 지점 데이터 한번에 반환
  응답:
    theme_data: [{
      _id, theme_name, genre, difficulty, degree_fear, esti_time, price,
      recomm_p: {min_p, max_p},
      location: "향남" | "안산",
      time_table: [{ week_name: "평일"|"금요일"|"주말", start_t: ["HH:MM",...] }]
    }]
    reserv_data: [{
      reserv_date: "YYYY-MM-DD",
      reserv_time: "HH:MM",
      theme_name: str
    }]  ← 미래 예약 완료 슬롯만 포함
  휴무: 화요일(Tuesday) 전체 휴무

요일 분류:
  평일 = 월·수·목 (weekday 0,2,3)
  금요일 = 금 (weekday 4)
  주말 = 토·일 (weekday 5,6)

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_reverseesc_db.py
  uv run python scripts/sync_reverseesc_db.py --no-schedule
  uv run python scripts/sync_reverseesc_db.py --days 14
"""

import json
import ssl
import sys
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

SITE_URL = "http://reverseesc.com"
API_URL = SITE_URL + "/service/get_data"
BOOKING_URL = SITE_URL + "/"
REQUEST_TIMEOUT = 15

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": SITE_URL + "/",
}

# location 필드 → cafe_id / area / address
LOCATION_MAP = {
    "향남": {
        "cafe_id":     "1231888375",
        "branch_name": "향남점",
        "area":        "gyeonggi",
        "address":     "경기 화성시 향남읍",
    },
    "안산": {
        "cafe_id":     "1772504569",
        "branch_name": "안산점",
        "area":        "gyeonggi",
        "address":     "경기 안산시",
    },
}

# 요일 번호(0=월)→ week_name 매핑 (화요일=1 은 휴무)
_WEEKDAY_MAP = {
    0: "평일",   # 월
    # 1 → 화요일 → 휴무
    2: "평일",   # 수
    3: "평일",   # 목
    4: "금요일", # 금
    5: "주말",   # 토
    6: "주말",   # 일
}


# ── API 호출 ───────────────────────────────────────────────────────────────────

def _fetch_data() -> dict:
    req = urllib.request.Request(API_URL, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT, context=_SSL_CTX) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"  [WARN] GET /service/get_data 실패: {e}")
        return {}


# ── DB 동기화 ──────────────────────────────────────────────────────────────────

def sync_cafe_meta(db) -> None:
    for loc, info in LOCATION_MAP.items():
        upsert_cafe(db, info["cafe_id"], {
            "name":        "리버스이스케이프",
            "branch_name": info["branch_name"],
            "address":     info["address"],
            "area":        info["area"],
            "website_url": SITE_URL,
            "engine":      "reverseesc",
            "crawled":     True,
            "is_active":   True,
        })
        print(f"  [UPSERT] 카페: 리버스이스케이프 {info['branch_name']} (id={info['cafe_id']})")


def sync_themes(db, theme_data: list[dict]) -> dict[str, dict[str, str]]:
    """
    테마 upsert.
    반환: {location → {theme_name → theme_doc_id}}
    """
    loc_theme_map: dict[str, dict[str, str]] = {}

    for t in theme_data:
        location = t.get("location", "")
        info = LOCATION_MAP.get(location)
        if not info:
            continue
        cafe_id = info["cafe_id"]
        theme_name = t.get("theme_name", "").strip()
        if not theme_name:
            continue

        doc_id = get_or_create_theme(db, cafe_id, theme_name, {
            "difficulty":   None,
            "duration_min": t.get("esti_time"),
            "poster_url":   None,
            "is_active":    True,
        })
        loc_theme_map.setdefault(location, {})[theme_name] = doc_id
        print(f"  [UPSERT] 테마: {theme_name} ({location}) — {t.get('esti_time')}분")

    return loc_theme_map


def sync_schedules(
    db,
    theme_data: list[dict],
    reserv_data: list[dict],
    loc_theme_map: dict[str, dict[str, str]],
    days: int = 14,
) -> None:
    today = date.today()
    crawled_at = datetime.now()

    # 예약 완료 슬롯 빠른 조회: {(date, time, theme_name)}
    booked_set: set[tuple] = {
        (r["reserv_date"], r["reserv_time"], r["theme_name"])
        for r in reserv_data
        if "reserv_date" in r and "reserv_time" in r and "theme_name" in r
    }

    # 테마별 time_table 인덱스: {(location, theme_name) → {week_name → [start_t, ...]}}
    theme_timetable: dict[tuple, dict[str, list[str]]] = {}
    for t in theme_data:
        location = t.get("location", "")
        theme_name = t.get("theme_name", "").strip()
        if not location or not theme_name:
            continue
        tt: dict[str, list[str]] = {}
        for entry in t.get("time_table", []):
            wname = entry.get("week_name", "")
            tt[wname] = entry.get("start_t", [])
        theme_timetable[(location, theme_name)] = tt

    # 지점별 date_themes 구성
    # { cafe_id → { date_str → { theme_doc_id → { "slots": [...] } } } }
    loc_date_themes: dict[str, dict[str, dict]] = {}

    for i in range(days + 1):
        target_date = today + timedelta(days=i)
        weekday = target_date.weekday()  # 0=월 ~ 6=일

        # 화요일 휴무
        if weekday == 1:
            continue

        week_name = _WEEKDAY_MAP.get(weekday)
        if not week_name:
            continue

        date_str = target_date.strftime("%Y-%m-%d")

        for location, theme_name_map in loc_theme_map.items():
            info = LOCATION_MAP[location]
            cafe_id = info["cafe_id"]

            for theme_name, theme_doc_id in theme_name_map.items():
                tt = theme_timetable.get((location, theme_name), {})
                start_times = tt.get(week_name, [])

                for start_t in start_times:
                    if ":" not in start_t:
                        continue
                    try:
                        hh, mm = int(start_t.split(":")[0]), int(start_t.split(":")[1])
                    except Exception:
                        continue

                    slot_dt = datetime(
                        target_date.year, target_date.month, target_date.day, hh, mm
                    )
                    if slot_dt <= datetime.now():
                        continue

                    time_str = f"{hh:02d}:{mm:02d}"
                    is_booked = (date_str, time_str, theme_name) in booked_set
                    status = "full" if is_booked else "available"
                    booking_url = BOOKING_URL if status == "available" else None

                    (
                        loc_date_themes
                        .setdefault(cafe_id, {})
                        .setdefault(date_str, {})
                        .setdefault(theme_doc_id, {"slots": []})
                        ["slots"]
                        .append({
                            "time":        time_str,
                            "status":      status,
                            "booking_url": booking_url,
                        })
                    )

    # Firestore upsert
    total_writes = 0
    for cafe_id, date_themes in loc_date_themes.items():
        known_hashes = load_cafe_hashes(db, cafe_id)
        new_hashes: dict[str, str] = {}

        avail_by_date: dict[str, int] = {}
        full_by_date: dict[str, int] = {}
        for date_str, themes in date_themes.items():
            for theme_doc_id, td in themes.items():
                for slot in td["slots"]:
                    if slot["status"] == "available":
                        avail_by_date[date_str] = avail_by_date.get(date_str, 0) + 1
                    else:
                        full_by_date[date_str] = full_by_date.get(date_str, 0) + 1

        for date_str, themes in sorted(date_themes.items()):
            h = upsert_cafe_date_schedules(
                db, date_str, cafe_id, themes, crawled_at,
                known_hash=known_hashes.get(date_str),
            )
            if h:
                new_hashes[date_str] = h
                total_writes += 1
            print(
                f"  {date_str}: 가능 {avail_by_date.get(date_str, 0)} / "
                f"마감 {full_by_date.get(date_str, 0)}"
            )

        if new_hashes:
            today_str = today.isoformat()
            save_cafe_hashes(db, cafe_id, {
                k: v for k, v in {**known_hashes, **new_hashes}.items()
                if k >= today_str
            })

    print(f"\n  스케줄 동기화 완료: {total_writes}개 날짜 문서 작성")


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main(run_schedule: bool = True, days: int = 14) -> None:
    print("=" * 60)
    print("리버스이스케이프(reverseesc.com) → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)
    db = get_db()

    print("\n[ 데이터 수집 ]")
    raw = _fetch_data()
    theme_data: list[dict] = raw.get("theme_data", [])
    reserv_data: list[dict] = raw.get("reserv_data", [])
    print(f"  테마: {len(theme_data)}개, 예약완료 슬롯: {len(reserv_data)}개")

    if not theme_data:
        print("  [ERROR] 테마 데이터 없음, 종료.")
        return

    print("\n[ 1단계 ] 카페 메타 동기화")
    sync_cafe_meta(db)

    print("\n[ 2단계 ] 테마 동기화")
    loc_theme_map = sync_themes(db, theme_data)
    if not loc_theme_map:
        print("  [ERROR] 테마 동기화 실패, 종료.")
        return

    if run_schedule:
        print(f"\n[ 3단계 ] 스케줄 동기화 (오늘~{days}일 후)")
        sync_schedules(db, theme_data, reserv_data, loc_theme_map, days=days)

    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="리버스이스케이프 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
