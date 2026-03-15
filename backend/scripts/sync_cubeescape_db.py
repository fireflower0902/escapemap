"""
큐브이스케이프(cubeescape.co.kr) 테마 + 스케줄 DB 동기화 스크립트.

지점:
  홍대점  http://www.cubeescape.co.kr    rFfice=1  place_id=27413260    area=hongdae
  잠실점  http://jamsil.cubeescape.co.kr rFfice=5  place_id=?           area=jamsil
  천호점  http://cheonho.cubeescape.co.kr rFfice=7 place_id=1857201893  area=jamsil
  수유점  http://suyu.cubeescape.co.kr    rFfice=8  place_id=4331171    area=etc

API:
  1) GET  http://{subdomain}.cubeescape.co.kr/
     → 세션 쿠키(CookieJar) 획득

  2) POST http://{subdomain}.cubeescape.co.kr/theme/basic_room2/_content/makeThemeTime.php
         ?dummytime={random_int}
     Body(form): tmode=&rDate=YYYY-MM-DD&rFfice={N}&rTheme=
     → HTML table: tbody tr
         td[0] = 시간 (HH:MM)
         td[1] = 테마명
         label.label-default.cursor → 예약 가능 (available)
         label.label-success        → 매진 (full)

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_cubeescape_db.py
  uv run python scripts/sync_cubeescape_db.py --no-schedule
  uv run python scripts/sync_cubeescape_db.py --days 14
"""

import random
import ssl
import sys
import time
import urllib.request
import urllib.parse
from datetime import date, datetime, time as dtime, timedelta
from http.cookiejar import CookieJar
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

REQUEST_DELAY = 1.0

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# rFfice 번호 → 지점 정보
BRANCHES: list[dict] = [
    {
        "cafe_id":     "27413260",
        "cafe_name":   "큐브이스케이프",
        "branch_name": "홍대점",
        "address":     "서울 마포구 와우산로29나길 9 2층",
        "area":        "hongdae",
        "subdomain":   "www",
        "office":      1,
    },
    {
        # TODO: 카카오 place_id 미확인 — Firestore 신규 생성됨
        "cafe_id":     "2100000001",
        "cafe_name":   "큐브이스케이프",
        "branch_name": "잠실점",
        "address":     "서울 송파구 잠실동 177-5",
        "area":        "jamsil",
        "subdomain":   "jamsil",
        "office":      5,
    },
    {
        "cafe_id":     "1857201893",
        "cafe_name":   "큐브이스케이프",
        "branch_name": "천호점",
        "address":     "서울 강동구 천호동 488-1 3층",
        "area":        "jamsil",
        "subdomain":   "cheonho",
        "office":      7,
    },
    {
        "cafe_id":     "4331171",
        "cafe_name":   "큐브이스케이프",
        "branch_name": "수유점",
        "address":     "서울 강북구 수유동 174-3 3층",
        "area":        "etc",
        "subdomain":   "suyu",
        "office":      8,
    },
]


# ── HTTP 유틸 ────────────────────────────────────────────────────────────────────

def _base_url(branch: dict) -> str:
    return f"http://{branch['subdomain']}.cubeescape.co.kr"


def _make_opener(base_url: str) -> urllib.request.OpenerDirector:
    """메인 페이지 방문 → 세션 쿠키 획득."""
    cj = CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cj),
        urllib.request.HTTPSHandler(context=_SSL_CTX),
    )
    req = urllib.request.Request(base_url + "/", headers=HEADERS)
    try:
        with opener.open(req, timeout=15) as r:
            r.read()
    except Exception as e:
        print(f"  [WARN] 세션 획득 실패: {e}")
    return opener


def _fetch_schedule(opener: urllib.request.OpenerDirector, branch: dict, target_date: date) -> str:
    base = _base_url(branch)
    date_str = target_date.strftime("%Y-%m-%d")
    dummy = random.randint(1000000, 9999999)
    url = f"{base}/theme/basic_room2/_content/makeThemeTime.php?dummytime={dummy}"
    body = urllib.parse.urlencode({
        "tmode":  "",
        "rDate":  date_str,
        "rFfice": branch["office"],
        "rTheme": "",
    }).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            **HEADERS,
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": base + "/",
        },
    )
    try:
        with opener.open(req, timeout=15) as r:
            return r.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"  [WARN] 페이지 로드 실패 {date_str}: {e}")
        return ""


# ── HTML 파싱 ────────────────────────────────────────────────────────────────────

def _parse_schedule(html: str, branch: dict, target_date: date) -> dict[str, list[dict]]:
    """
    table tbody tr 파싱.
    반환: {테마명 → [{time, status, booking_url}]}
    """
    soup = BeautifulSoup(html, "html.parser")
    result: dict[str, list[dict]] = {}
    base = _base_url(branch)

    for tr in soup.select("table tbody tr"):
        tds = tr.find_all("td")
        if len(tds) < 2:
            continue

        # 시간
        time_text = tds[0].get_text(strip=True)
        try:
            hh, mm = map(int, time_text.split(":"))
            time_obj = dtime(hh, mm)
        except Exception:
            continue

        slot_dt = datetime(
            target_date.year, target_date.month, target_date.day,
            time_obj.hour, time_obj.minute,
        )
        if slot_dt <= datetime.now():
            continue

        # 테마명
        theme_name = tds[1].get_text(strip=True)
        if not theme_name:
            continue

        # 가용성
        label = tr.select_one("label")
        if label is None:
            continue
        classes = label.get("class", [])
        class_str = " ".join(classes)

        if "label-default" in class_str and "cursor" in class_str:
            status = "available"
            booking_url = base + "/"
        elif "label-success" in class_str:
            status = "full"
            booking_url = None
        else:
            continue

        result.setdefault(theme_name, []).append({
            "time":        time_obj,
            "status":      status,
            "booking_url": booking_url,
        })

    return result


# ── DB 동기화 ────────────────────────────────────────────────────────────────────

def sync_one_branch(branch: dict, run_schedule: bool, days: int) -> None:
    print(f"\n{'=' * 50}")
    print(f"[ {branch['cafe_name']} {branch['branch_name']} (office={branch['office']}) ]")
    print(f"{'=' * 50}")

    db = get_db()
    cafe_id = branch["cafe_id"]
    base = _base_url(branch)

    # 1. 카페 메타
    upsert_cafe(db, cafe_id, {
        "name":        branch["cafe_name"],
        "branch_name": branch["branch_name"],
        "address":     branch["address"],
        "area":        branch["area"],
        "phone":       None,
        "website_url": base + "/",
        "engine":      "cubeescape",
        "crawled":     True,
        "lat":         None,
        "lng":         None,
        "is_active":   True,
    })
    print(f"  [UPSERT] 카페 (id={cafe_id})")

    opener = _make_opener(base)
    time.sleep(REQUEST_DELAY)

    # 2. 테마 추출 (오늘 + fallback)
    today = date.today()
    name_map: dict[str, list[dict]] = {}
    for i in range(8):
        target = today + timedelta(days=i)
        html = _fetch_schedule(opener, branch, target)
        time.sleep(REQUEST_DELAY)
        name_map = _parse_schedule(html, branch, target)
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
        html = _fetch_schedule(opener, branch, target_date)
        time.sleep(REQUEST_DELAY)
        parsed = _parse_schedule(html, branch, target_date)
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


# ── 메인 ─────────────────────────────────────────────────────────────────────────

def main(run_schedule: bool = True, days: int = 14) -> None:
    print("=" * 60)
    print("큐브이스케이프(cubeescape.co.kr) → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)

    for branch in BRANCHES:
        sync_one_branch(branch, run_schedule, days)

    print("\n" + "=" * 60)
    print("모든 지점 동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="큐브이스케이프 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
