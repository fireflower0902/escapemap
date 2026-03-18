"""
미스터리룸이스케이프 (mysteryroomescape.com) 테마 + 스케줄 DB 동기화 스크립트.

사이트: http://mysteryroomescape.com
지점:
  a=27  강남점   (서울 강남구 역삼동 823-17 강남파인애플 B1F, 카카오 place_id=27367643)
  a=44  홍대2호점 (서울 마포구 서교동 398-1, 카카오 place_id=727312827)

API:
  GET http://mysteryroomescape.com/reservation/reservation.html?a={N}&select_date={YYYY-MM-DD}
  HTML 응답: #reservation_list_con li 단위 테마별 슬롯
    - div.title_con > span (ROOM.N) + span (테마명)
    - span.time_text.possible   → 예약가능 (시간: "HH:MM ~ HH:MM" 또는 "HH:MM~HH:MM")
    - span.time_text.disabled   → 예약완료

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_mysteryroom_db.py
  uv run python scripts/sync_mysteryroom_db.py --no-schedule
  uv run python scripts/sync_mysteryroom_db.py --days 14
"""

import re
import sys
import time
import urllib.request
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

RESERVE_BASE = "http://mysteryroomescape.com/reservation/reservation.html"
REQUEST_DELAY = 1.0

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": "http://mysteryroomescape.com/",
}

BRANCH_MAP: dict[int, dict] = {
    27: {
        "cafe_id":     "27367643",
        "cafe_name":   "미스터리룸이스케이프",
        "branch_name": "강남점",
        "address":     "서울 강남구 역삼동 823-17 강남파인애플 B1F",
        "area":        "gangnam",
    },
    44: {
        "cafe_id":     "727312827",
        "cafe_name":   "미스터리룸이스케이프",
        "branch_name": "홍대2호점",
        "address":     "서울 마포구 서교동 398-1",
        "area":        "hongdae",
    },
}


# ── HTTP 유틸 ─────────────────────────────────────────────────────────────────

def _fetch_page(branch_id: int, target_date: date) -> str:
    date_str = target_date.strftime("%Y-%m-%d")
    url = f"{RESERVE_BASE}?a={branch_id}&select_date={date_str}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"  [WARN] 페이지 로드 실패 a={branch_id} {date_str}: {e}")
        return ""


# ── HTML 파싱 ─────────────────────────────────────────────────────────────────

def _parse_slots(html: str, target_date: date, booking_url: str) -> dict[str, list[dict]]:
    """
    #reservation_list_con li 파싱.
    반환: {테마명 → [{time, status, booking_url}]}
    """
    soup = BeautifulSoup(html, "html.parser")
    result: dict[str, list[dict]] = {}

    for li in soup.select("#reservation_list_con li"):
        title_div = li.select_one(".title_con")
        if not title_div:
            continue
        spans = title_div.select("span")
        theme_name = spans[1].get_text(strip=True) if len(spans) > 1 else ""
        if not theme_name:
            continue

        slots = []
        for slot_span in li.select(".time_text"):
            css = slot_span.get("class", [])
            time_raw = slot_span.get_text(strip=True)
            # "10:30~11:30" or "10:30 ~ 11:30" → start time
            m = re.search(r"(\d{1,2}):(\d{2})", time_raw)
            if not m:
                continue
            try:
                time_obj = dtime(int(m.group(1)), int(m.group(2)))
            except Exception:
                continue

            slot_dt = datetime(
                target_date.year, target_date.month, target_date.day,
                time_obj.hour, time_obj.minute,
            )
            if slot_dt <= datetime.now():
                continue

            if "possible" in css:
                status = "available"
                url = booking_url
            else:
                status = "full"
                url = None

            slots.append({"time": time_obj, "status": status, "booking_url": url})

        if slots:
            result[theme_name] = slots

    return result


# ── DB 동기화 ─────────────────────────────────────────────────────────────────

def sync_cafe_meta(branch_id: int) -> None:
    info = BRANCH_MAP[branch_id]
    db = get_db()
    upsert_cafe(db, info["cafe_id"], {
        "name":        info["cafe_name"],
        "branch_name": info["branch_name"],
        "address":     info["address"],
        "area":        info["area"],
        "phone":       None,
        "website_url": "http://mysteryroomescape.com/",
        "engine":      "mysteryroom",
        "crawled":     True,
        "lat":         None,
        "lng":         None,
        "is_active":   True,
    })
    print(f"  [UPSERT] 카페: {info['cafe_name']} {info['branch_name']} (id={info['cafe_id']})")


def sync_themes(branch_id: int, theme_names: list[str]) -> dict[str, str]:
    """테마 upsert. 반환: {theme_name → theme_doc_id}"""
    info = BRANCH_MAP[branch_id]
    cafe_id = info["cafe_id"]
    db = get_db()

    cafe_doc = db.collection("cafes").document(cafe_id).get()
    if not cafe_doc.exists:
        print(f"  [ERROR] cafe {cafe_id} Firestore 미존재")
        return {}

    name_to_doc: dict[str, str] = {}
    for name in theme_names:
        doc_id = get_or_create_theme(db, cafe_id, name, {
            "difficulty":   None,
            "duration_min": None,
            "poster_url":   None,
            "is_active":    True,
        })
        name_to_doc[name] = doc_id
        print(f"  [UPSERT] 테마: {name} (doc={doc_id})")

    return name_to_doc


def sync_schedules(
    branch_id: int, name_to_doc: dict[str, str], days: int = 14
) -> None:
    info = BRANCH_MAP[branch_id]
    cafe_id = info["cafe_id"]
    db = get_db()
    today = date.today()
    crawled_at = datetime.now()
    writes = 0

    known_hashes = load_cafe_hashes(db, cafe_id)
    new_hashes: dict[str, str] = {}

    for i in range(days + 1):
        target_date = today + timedelta(days=i)
        date_str = target_date.strftime("%Y-%m-%d")
        booking_url = f"{RESERVE_BASE}?a={branch_id}&select_date={date_str}"

        html = _fetch_page(branch_id, target_date)
        time.sleep(REQUEST_DELAY)

        theme_slot_map = _parse_slots(html, target_date, booking_url)
        avail = full = 0
        themes: dict[str, dict] = {}

        for theme_name, slots in theme_slot_map.items():
            theme_doc_id = name_to_doc.get(theme_name)
            if not theme_doc_id:
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


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main(run_schedule: bool = True, days: int = 14) -> None:
    print("=" * 60)
    print("미스터리룸이스케이프 (mysteryroomescape.com) → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)

    for branch_id in BRANCH_MAP:
        info = BRANCH_MAP[branch_id]
        print(f"\n{'=' * 40}")
        print(f"[ {info['branch_name']} (a={branch_id}) ]")
        print(f"{'=' * 40}")

        # 오늘 날짜 데이터로 테마 목록 파악
        html = _fetch_page(branch_id, date.today())
        theme_map = _parse_slots(html, date.today(), "")
        theme_names = list(theme_map.keys())
        if not theme_names:
            print("  테마 없음, 건너뜀.")
            continue

        print("\n[ 1단계 ] 카페 메타 동기화")
        sync_cafe_meta(branch_id)

        print("\n[ 2단계 ] 테마 동기화")
        name_to_doc = sync_themes(branch_id, theme_names)
        if not name_to_doc:
            print("  테마 동기화 실패, 건너뜀.")
            continue

        if run_schedule:
            print(f"\n[ 3단계 ] 스케줄 동기화 (오늘~{days}일 후)")
            sync_schedules(branch_id, name_to_doc, days=days)

    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="미스터리룸이스케이프 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
