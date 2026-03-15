"""
플레이33 (play33.kr) 테마 + 스케줄 DB 동기화 스크립트.

사이트: https://play33.kr
지점:
  branch=1  건대점  (서울 광진구 자양동 13-3 지하1층, 카카오 place_id=1385414031)

API:
  GET https://play33.kr/reservation?branch={N}&theme={N}&date={YYYY-MM-DD}
  HTML 응답: div.restimes ul li button
    - button[disabled] → 예약 불가 (full)
    - button (활성)    → 예약 가능 (available)
    - button span → 시간 (HH:MM)
  날짜 파라미터 없으면 오늘 날짜 기준

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_play33_db.py
  uv run python scripts/sync_play33_db.py --no-schedule
  uv run python scripts/sync_play33_db.py --days 14
"""

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
from app.firestore_db import (
    init_firestore, get_db, upsert_cafe,
    get_or_create_theme, upsert_cafe_date_schedules,
    load_cafe_hashes, save_cafe_hashes,
)

RESERVE_BASE = "https://play33.kr/reservation"
REQUEST_DELAY = 1.0

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": "https://play33.kr/reservation",
}

# branch_id → (cafe_id, cafe_name, branch_name, address, area)
BRANCH_MAP: dict[int, dict] = {
    1: {
        "cafe_id":     "1385414031",
        "cafe_name":   "플레이33",
        "branch_name": "건대점",
        "address":     "서울 광진구 자양동 13-3 지하1층",
        "area":        "konkuk",
    },
    # branch=4: 홍대점 (카카오 place_id 미확인, 추후 추가)
}

# branch_id → [(theme_id, theme_name)]
# play33.kr/reservation 선택 옵션에서 확인
THEME_MAP: dict[int, list[dict]] = {
    1: [
        {"theme_id": 16, "name": "그 날"},
        {"theme_id": 15, "name": "다이얼"},
    ],
    # branch=4 홍대점 테마도 추후 추가
}


# ── HTTP 유틸 ────────────────────────────────────────────────────────────────────

def _fetch_page(branch: int, theme_id: int, target_date: date) -> str:
    """날짜별 예약 페이지 HTML 반환."""
    date_str = target_date.strftime("%Y-%m-%d")
    url = f"{RESERVE_BASE}?branch={branch}&theme={theme_id}&date={date_str}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"  [WARN] 페이지 로드 실패 branch={branch} theme={theme_id} {date_str}: {e}")
        return ""


# ── HTML 파싱 ────────────────────────────────────────────────────────────────────

def _parse_slots(html: str, target_date: date, booking_url: str) -> list[dict]:
    """
    div.restimes 파싱 → 슬롯 목록 반환.

    반환: [{"time": dtime, "status": str, "booking_url": str | None}]
    """
    soup = BeautifulSoup(html, "html.parser")
    restimes = soup.select_one("div.restimes")
    if not restimes:
        return []

    slots = []
    for li in restimes.select("ul li"):
        btn = li.find("button")
        if not btn:
            continue
        span = btn.find("span")
        if not span:
            continue
        time_str = span.get_text(strip=True)
        try:
            hh, mm = map(int, time_str.split(":"))
            time_obj = dtime(hh, mm)
        except Exception:
            continue

        disabled = btn.get("disabled") is not None

        # 과거 시간 건너뜀
        slot_dt = datetime(
            target_date.year, target_date.month, target_date.day,
            time_obj.hour, time_obj.minute,
        )
        if slot_dt <= datetime.now():
            continue

        status = "full" if disabled else "available"
        slots.append({
            "time":        time_obj,
            "status":      status,
            "booking_url": booking_url if not disabled else None,
        })

    return slots


# ── DB 동기화 ────────────────────────────────────────────────────────────────────

def sync_cafe_meta(branch: int) -> None:
    info = BRANCH_MAP[branch]
    db = get_db()
    upsert_cafe(db, info["cafe_id"], {
        "name":        info["cafe_name"],
        "branch_name": info["branch_name"],
        "address":     info["address"],
        "area":        info["area"],
        "phone":       None,
        "website_url": RESERVE_BASE,
        "engine":      "play33",
        "crawled":     True,
        "lat":         None,
        "lng":         None,
        "is_active":   True,
    })
    print(f"  [UPSERT] 카페: {info['cafe_name']} {info['branch_name']} (id={info['cafe_id']})")


def sync_themes(branch: int) -> dict[int, str]:
    """
    테마를 Firestore에 upsert.
    반환: {theme_id → theme_doc_id}
    """
    info = BRANCH_MAP[branch]
    cafe_id = info["cafe_id"]
    db = get_db()

    cafe_doc = db.collection("cafes").document(cafe_id).get()
    if not cafe_doc.exists:
        print(f"  [ERROR] cafe {cafe_id} Firestore 미존재")
        return {}

    theme_id_to_doc: dict[int, str] = {}
    for theme in THEME_MAP[branch]:
        theme_doc_id = get_or_create_theme(db, cafe_id, theme["name"], {
            "difficulty":   None,
            "duration_min": None,
            "poster_url":   None,
            "is_active":    True,
        })
        theme_id_to_doc[theme["theme_id"]] = theme_doc_id
        print(f"  [UPSERT] {theme['name']} (theme_id={theme['theme_id']}, doc={theme_doc_id})")

    print(f"\n  테마 동기화 완료: {len(theme_id_to_doc)}개")
    return theme_id_to_doc


def sync_schedules(
    branch: int,
    theme_id_to_doc: dict[int, str],
    days: int = 14,
) -> None:
    """스케줄을 Firestore에 upsert (오늘~days일 후)."""
    info = BRANCH_MAP[branch]
    cafe_id = info["cafe_id"]
    db = get_db()
    today = date.today()
    target_dates = [today + timedelta(days=i) for i in range(days + 1)]
    crawled_at = datetime.now()
    writes = 0

    known_hashes = load_cafe_hashes(db, cafe_id)
    new_hashes: dict[str, str] = {}

    for target_date in target_dates:
        date_str = target_date.strftime("%Y-%m-%d")
        themes: dict[str, dict] = {}
        avail = full = 0

        for theme in THEME_MAP[branch]:
            theme_id = theme["theme_id"]
            theme_doc_id = theme_id_to_doc.get(theme_id)
            if not theme_doc_id:
                continue

            booking_url = (
                f"{RESERVE_BASE}?branch={branch}&theme={theme_id}&date={date_str}"
            )
            html = _fetch_page(branch, theme_id, target_date)
            time.sleep(REQUEST_DELAY)

            slots = _parse_slots(html, target_date, booking_url)
            if not slots:
                continue

            for slot in slots:
                themes.setdefault(theme_doc_id, {"slots": []})["slots"].append({
                    "time":        f"{slot['time'].hour:02d}:{slot['time'].minute:02d}",
                    "status":      slot["status"],
                    "booking_url": slot["booking_url"],
                })
                if slot["status"] == "available":
                    avail += 1
                else:
                    full += 1

        if themes:
            h = upsert_cafe_date_schedules(
                db, date_str, cafe_id, themes, crawled_at,
                known_hash=known_hashes.get(date_str),
            )
            if h:
                new_hashes[date_str] = h
                writes += 1

        print(f"  {date_str}: 가능 {avail}개 / 마감 {full}개")

    if new_hashes:
        today_str = today.isoformat()
        save_cafe_hashes(db, cafe_id, {
            k: v for k, v in {**known_hashes, **new_hashes}.items()
            if k >= today_str
        })

    print(f"\n  스케줄 동기화 완료: {writes}개 날짜 문서 작성")


# ── 메인 ─────────────────────────────────────────────────────────────────────────

def main(run_schedule: bool = True, days: int = 14):
    print("=" * 60)
    print("플레이33 (play33.kr) → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)

    for branch in BRANCH_MAP:
        info = BRANCH_MAP[branch]
        print(f"\n{'='*40}")
        print(f"[ {info['branch_name']} (branch={branch}) ]")
        print(f"{'='*40}")

        print("\n[ 1단계 ] 카페 메타 동기화")
        sync_cafe_meta(branch)

        print("\n[ 2단계 ] 테마 동기화")
        theme_id_to_doc = sync_themes(branch)
        if not theme_id_to_doc:
            print("테마 동기화 실패, 건너뜀.")
            continue

        if run_schedule:
            print(f"\n[ 3단계 ] 스케줄 동기화 (오늘~{days}일 후)")
            sync_schedules(branch, theme_id_to_doc, days=days)

    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="플레이33 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
