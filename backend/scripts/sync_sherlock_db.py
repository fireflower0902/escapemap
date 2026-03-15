"""
셜록홈즈 (sherlock-holmes.co.kr) 방탈출 테마 + 스케줄 DB 동기화 스크립트.

지점 (서울):
  bno=107  잠실새내점  place_id=45777628   area=jamsil   (서울 송파구 올림픽로10길 13-1)
  bno=35   잠실1호점   place_id=466116790  area=jamsil   (서울 송파구 백제고분로7길 19)
  bno=69   종각점      place_id=462553617  area=myeongdong (서울 종로구 삼일대로17길 17)
  bno=88   대학로점    place_id=270131531  area=daehakro  (서울 종로구 대학로10길 5)
  bno=48   노원점      place_id=1367009941 area=etc      (서울 노원구 노해로81길 12-20)
  bno=54   성신여대점  place_id=10098327   area=daehakro  (서울 성북구 동선동1가 87)
  bno=57   노량진점    place_id=8143798    area=etc      (서울 동작구 노량진동 118-8)

API:
  GET https://sherlock-holmes.co.kr/reservation/res_schedule.php
      ?sido={sido}&bno={bno}&date={YYYY-MM-DD}
  HTML: .theme-item 단위 테마 → .col.true(available) / .col.false(full)
    - .theme-title → 테마명 (형식: "테마명 (N분)")
    - .col.true > a[href] → 예약 링크 (/reservation/res_write.php?...)
    - .col.false → 예약불가
    - p.time → 시간 텍스트 (HH:MM)

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_sherlock_db.py
  uv run python scripts/sync_sherlock_db.py --no-schedule
  uv run python scripts/sync_sherlock_db.py --days 14
"""

import re
import ssl
import sys
import time
import urllib.request
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from bs4 import BeautifulSoup

from app.config import settings
from app.firestore_db import (
    init_firestore, get_db, upsert_cafe,
    get_or_create_theme, upsert_cafe_date_schedules,
    load_cafe_hashes, save_cafe_hashes,
)

BASE_URL = "https://sherlock-holmes.co.kr"
REQUEST_DELAY = 1.0

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": "https://sherlock-holmes.co.kr/reservation",
}

BRANCHES: list[dict] = [
    {
        "cafe_id":     "45777628",
        "cafe_name":   "셜록홈즈",
        "branch_name": "잠실새내점",
        "address":     "서울 송파구 올림픽로10길 13-1 은성빌딩 2층",
        "area":        "jamsil",
        "sido":        1,
        "bno":         107,
    },
    {
        "cafe_id":     "466116790",
        "cafe_name":   "셜록홈즈",
        "branch_name": "잠실1호점",
        "address":     "서울 송파구 백제고분로7길 19 3,4층",
        "area":        "jamsil",
        "sido":        1,
        "bno":         35,
    },
    {
        "cafe_id":     "462553617",
        "cafe_name":   "셜록홈즈",
        "branch_name": "종각점",
        "address":     "서울 종로구 삼일대로17길 17 4층",
        "area":        "myeongdong",
        "sido":        1,
        "bno":         69,
    },
    {
        "cafe_id":     "270131531",
        "cafe_name":   "셜록홈즈",
        "branch_name": "대학로점",
        "address":     "서울 종로구 대학로10길 5 4층",
        "area":        "daehakro",
        "sido":        1,
        "bno":         88,
    },
    {
        "cafe_id":     "1367009941",
        "cafe_name":   "셜록홈즈",
        "branch_name": "노원점",
        "address":     "서울 노원구 노해로81길 12-20 민진빌딩 5층",
        "area":        "etc",
        "sido":        1,
        "bno":         48,
    },
    {
        "cafe_id":     "10098327",
        "cafe_name":   "셜록홈즈",
        "branch_name": "성신여대점",
        "address":     "서울 성북구 동선동1가 87 4층",
        "area":        "daehakro",
        "sido":        1,
        "bno":         54,
    },
    {
        "cafe_id":     "8143798",
        "cafe_name":   "셜록홈즈",
        "branch_name": "노량진점",
        "address":     "서울 동작구 노량진동 118-8 지하1층",
        "area":        "etc",
        "sido":        1,
        "bno":         57,
    },
]


# ── HTTP 유틸 ─────────────────────────────────────────────────────────────────

def _fetch_schedule(sido: int, bno: int, target_date: date) -> str:
    date_str = target_date.strftime("%Y-%m-%d")
    url = (
        f"{BASE_URL}/reservation/res_schedule.php"
        f"?sido={sido}&bno={bno}&date={date_str}"
    )
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=15) as r:
            return r.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"  [WARN] 페이지 로드 실패 bno={bno} {date_str}: {e}")
        return ""


# ── HTML 파싱 ─────────────────────────────────────────────────────────────────

def _parse_schedule(html: str, target_date: date) -> dict[str, list[dict]]:
    """
    .theme-item 파싱.
    반환: {테마명 → [{time, status, booking_url}]}
    """
    soup = BeautifulSoup(html, "html.parser")
    result: dict[str, list[dict]] = {}

    for item in soup.select(".theme-item"):
        title_el = item.select_one(".theme-title")
        if not title_el:
            continue
        raw = title_el.get_text(strip=True)
        # "테마명 (N분)" → "테마명" (괄호 제거)
        theme_name = re.sub(r"\s*\(\d+분\)\s*$", "", raw).strip()
        if not theme_name:
            continue

        slots = []
        for col in item.select(".time-area .col"):
            classes = col.get("class", [])
            time_el = col.select_one("p.time")
            if not time_el:
                continue
            time_str = time_el.get_text(strip=True)
            m = re.match(r"(\d{1,2}):(\d{2})", time_str)
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

            if "true" in classes:
                status = "available"
                a_tag = col.select_one("a[href]")
                href = a_tag.get("href", "") if a_tag else ""
                if href.startswith("http"):
                    booking_url = href
                elif href.startswith("/"):
                    booking_url = BASE_URL + href
                else:
                    booking_url = BASE_URL + "/reservation"
            else:
                status = "full"
                booking_url = None

            slots.append({"time": time_obj, "status": status, "booking_url": booking_url})

        if slots:
            result[theme_name] = slots

    return result


# ── DB 동기화 ─────────────────────────────────────────────────────────────────

def sync_one_branch(branch: dict, run_schedule: bool, days: int) -> None:
    print(f"\n{'=' * 50}")
    print(f"[ {branch['cafe_name']} {branch['branch_name']} (bno={branch['bno']}) ]")
    print(f"{'=' * 50}")

    db = get_db()
    cafe_id = branch["cafe_id"]

    # 1. 카페 메타
    upsert_cafe(db, cafe_id, {
        "name":        branch["cafe_name"],
        "branch_name": branch["branch_name"],
        "address":     branch["address"],
        "area":        branch["area"],
        "phone":       None,
        "website_url": f"{BASE_URL}/reservation/index.php?sido={branch['sido']}&bno={branch['bno']}#reservation",
        "engine":      "sherlock",
        "crawled":     True,
        "lat":         None,
        "lng":         None,
        "is_active":   True,
    })
    print(f"  [UPSERT] 카페 (id={cafe_id})")

    # 2. 테마 추출 (오늘 + fallback)
    today = date.today()
    name_map: dict[str, list[dict]] = {}
    for i in range(8):
        target = today + timedelta(days=i)
        html = _fetch_schedule(branch["sido"], branch["bno"], target)
        time.sleep(REQUEST_DELAY)
        name_map = _parse_schedule(html, target)
        if name_map:
            print(f"  기준 날짜: {target} (테마 {len(name_map)}개)")
            break

    if not name_map:
        print("  테마 정보를 찾을 수 없음, 건너뜀.")
        return

    # 3. 테마 upsert
    cafe_doc = db.collection("cafes").document(cafe_id).get()
    if not cafe_doc.exists:
        print(f"  [ERROR] cafe {cafe_id} Firestore 미존재")
        return

    name_to_doc: dict[str, str] = {}
    for theme_name in name_map:
        doc_id = get_or_create_theme(db, cafe_id, theme_name, {
            "difficulty":   None,
            "duration_min": None,
            "poster_url":   None,
            "is_active":    True,
        })
        name_to_doc[theme_name] = doc_id
        print(f"  [UPSERT] 테마: {theme_name} (doc={doc_id})")

    if not run_schedule:
        return

    # 4. 스케줄 upsert
    target_dates = [today + timedelta(days=i) for i in range(days + 1)]
    crawled_at = datetime.now()
    writes = 0
    known_hashes = load_cafe_hashes(db, cafe_id)
    new_hashes: dict[str, str] = {}

    for target_date in target_dates:
        html = _fetch_schedule(branch["sido"], branch["bno"], target_date)
        time.sleep(REQUEST_DELAY)
        parsed = _parse_schedule(html, target_date)
        date_str = target_date.strftime("%Y-%m-%d")

        if not parsed:
            print(f"  {date_str}: 미오픈")
            continue

        themes_data: dict[str, dict] = {}
        avail = full = 0

        for theme_name, slots in parsed.items():
            doc_id = name_to_doc.get(theme_name)
            if not doc_id:
                print(f"  [WARN] 알 수 없는 테마: {theme_name!r}")
                continue
            for slot in slots:
                themes_data.setdefault(doc_id, {"slots": []})["slots"].append({
                    "time":        f"{slot['time'].hour:02d}:{slot['time'].minute:02d}",
                    "status":      slot["status"],
                    "booking_url": slot["booking_url"],
                })
                if slot["status"] == "available":
                    avail += 1
                else:
                    full += 1

        if themes_data:
            h = upsert_cafe_date_schedules(
                db, date_str, cafe_id, themes_data, crawled_at,
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

    print(f"  스케줄 동기화: {writes}개 날짜 작성")


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main(run_schedule: bool = True, days: int = 14) -> None:
    print("=" * 60)
    print("셜록홈즈 (sherlock-holmes.co.kr) → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)

    for branch in BRANCHES:
        sync_one_branch(branch, run_schedule, days)

    print("\n" + "=" * 60)
    print("모든 지점 동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="셜록홈즈 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
