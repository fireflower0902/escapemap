"""
클레버타운 (clevertown.co.kr) 테마 + 스케줄 DB 동기화 스크립트.

사이트: https://clevertown.co.kr
플랫폼: sinbiweb PHP CMS (studioesc.co.kr과 동일 구조)
지점: 신촌점 (서울 서대문구 신촌동 57-7, 카카오 place_id=949587061)

API:
  1) 세션 획득: GET https://clevertown.co.kr/ (PHPSESSID 쿠키)
  2) 날짜별 예약 현황:
     GET https://clevertown.co.kr/layout/res/home.php?go=rev.make&rev_days=YYYY-MM-DD
     HTML 응답: div.theme_box 단위로 테마별 슬롯 정보
     - span.possible   → 예약 가능 (a[href] = 예약 링크)
     - span.impossible → 예약 마감
     - theme_box 없으면 예약 미오픈 → 건너뜀

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_clevertown_db.py
  uv run python scripts/sync_clevertown_db.py --no-schedule
  uv run python scripts/sync_clevertown_db.py --days 14
"""

import ssl
import sys
import time
import urllib.request
import urllib.parse
from datetime import date, datetime, time as dtime, timedelta
from http.cookiejar import CookieJar
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

CAFE_ID = "949587061"
CAFE_NAME = "클레버타운"
BRANCH_NAME = "신촌점"
ADDRESS = "서울 서대문구 신촌동 57-7"
AREA = "sinchon"

SITE_ROOT = "https://clevertown.co.kr/"
BASE_URL = "https://clevertown.co.kr/layout/res/home.php"
RESERVE_URL = BASE_URL + "?go=rev.make"
REQUEST_DELAY = 1.0

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9",
}


# ── HTTP 유틸 ────────────────────────────────────────────────────────────────────

def _make_opener() -> urllib.request.OpenerDirector:
    """쿠키 핸들러 + SSL 우회가 포함된 opener 생성."""
    cj = CookieJar()
    https_handler = urllib.request.HTTPSHandler(context=_SSL_CTX)
    return urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cj),
        https_handler,
    )


def _get_session(opener: urllib.request.OpenerDirector) -> bool:
    """루트 페이지 GET → PHPSESSID 세션 쿠키 획득."""
    req = urllib.request.Request(SITE_ROOT, headers=HEADERS)
    try:
        with opener.open(req, timeout=15) as r:
            r.read()
        print(f"  세션 획득 완료 (status={r.status})")
        return True
    except Exception as e:
        print(f"  [ERROR] 세션 획득 실패: {e}")
        return False


def _fetch_reserve_page(opener: urllib.request.OpenerDirector, target_date: date) -> str:
    """날짜별 예약 페이지 HTML 반환."""
    date_str = target_date.strftime("%Y-%m-%d")
    url = f"{RESERVE_URL}&rev_days={date_str}"
    req = urllib.request.Request(
        url,
        headers={**HEADERS, "Referer": SITE_ROOT},
    )
    try:
        with opener.open(req, timeout=15) as r:
            return r.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"  [WARN] 페이지 로드 실패 {date_str}: {e}")
        return ""


# ── HTML 파싱 ────────────────────────────────────────────────────────────────────

def _parse_reserve_page(html: str, target_date: date) -> list[dict]:
    """
    예약 페이지 HTML에서 테마별 슬롯 파싱.

    반환: [
      {
        "theme_name": str,
        "poster_url": str | None,
        "slots": [{"time": dtime, "status": str, "booking_url": str | None}]
      }, ...
    ]
    """
    soup = BeautifulSoup(html, "html.parser")
    boxes = soup.select(".theme_box")
    if not boxes:
        return []

    date_str = target_date.strftime("%Y-%m-%d")
    results = []

    for box in boxes:
        h3 = box.select_one("h3.h3_theme")
        if not h3:
            continue
        theme_name = h3.text.strip()

        # 포스터 이미지
        img_tag = box.select_one(".theme_pic img")
        poster_url = None
        if img_tag and img_tag.get("src"):
            raw_src = img_tag["src"].split("?")[0]
            if raw_src.startswith("../../"):
                poster_url = "https://clevertown.co.kr/" + raw_src[6:]
            elif raw_src.startswith("http"):
                poster_url = raw_src
            elif raw_src.startswith("/"):
                poster_url = "https://clevertown.co.kr" + raw_src

        slots = []
        for li in box.select("ul.reserve_Time li"):
            time_span = li.select_one("span.time")
            if not time_span:
                continue
            time_str = time_span.text.strip()
            try:
                hh, mm = map(int, time_str.split(":"))
                time_obj = dtime(hh, mm)
            except Exception:
                continue

            possible = li.select_one("span.possible")
            impossible = li.select_one("span.impossible")
            a_tag = li.select_one("a")

            if possible:
                status = "available"
                href = a_tag.get("href", "") if a_tag else ""
                if href:
                    if href.startswith("http"):
                        booking_url = href
                    elif href.startswith("/"):
                        booking_url = "https://clevertown.co.kr" + href
                    else:
                        booking_url = "https://clevertown.co.kr/layout/res/" + href
                else:
                    booking_url = RESERVE_URL + f"&rev_days={date_str}"
            elif impossible:
                status = "full"
                booking_url = None
            else:
                continue

            slots.append({
                "time": time_obj,
                "status": status,
                "booking_url": booking_url,
            })

        if slots:
            results.append({
                "theme_name": theme_name,
                "poster_url": poster_url,
                "slots": slots,
            })

    return results


# ── DB 동기화 ────────────────────────────────────────────────────────────────────

def sync_cafe_meta() -> None:
    """카페 메타데이터를 Firestore에 upsert합니다."""
    db = get_db()
    upsert_cafe(db, CAFE_ID, {
        "name":        CAFE_NAME,
        "branch_name": BRANCH_NAME,
        "address":     ADDRESS,
        "area":        AREA,
        "phone":       None,
        "website_url": SITE_ROOT,
        "engine":      "clevertown",
        "crawled":     True,
        "lat":         None,
        "lng":         None,
        "is_active":   True,
    })
    print(f"  [UPSERT] 카페: {CAFE_NAME} {BRANCH_NAME} (id={CAFE_ID})")


def sync_themes(themes_info: list[dict]) -> dict[str, str]:
    """
    테마를 Firestore에 upsert.
    반환: {테마명 → theme_doc_id}
    """
    db = get_db()
    cafe_doc = db.collection("cafes").document(CAFE_ID).get()
    if not cafe_doc.exists:
        print(f"  [ERROR] cafe {CAFE_ID} Firestore 미존재")
        return {}

    name_to_doc_id: dict[str, str] = {}

    for info in themes_info:
        theme_name = info["theme_name"]
        poster_url = info.get("poster_url")

        theme_doc_id = get_or_create_theme(db, CAFE_ID, theme_name, {
            "difficulty":   None,
            "duration_min": None,
            "poster_url":   poster_url,
            "is_active":    True,
        })
        name_to_doc_id[theme_name] = theme_doc_id
        print(f"  [UPSERT] {theme_name} (doc_id={theme_doc_id})")

    print(f"\n  테마 동기화 완료: {len(name_to_doc_id)}개")
    return name_to_doc_id


def sync_schedules(
    opener: urllib.request.OpenerDirector,
    name_to_doc_id: dict[str, str],
    days: int = 14,
) -> None:
    """스케줄을 Firestore에 upsert (오늘~days일 후)."""
    db = get_db()
    today = date.today()
    target_dates = [today + timedelta(days=i) for i in range(days + 1)]
    crawled_at = datetime.now()
    writes = 0

    known_hashes = load_cafe_hashes(db, CAFE_ID)
    new_hashes: dict[str, str] = {}

    for target_date in target_dates:
        html = _fetch_reserve_page(opener, target_date)
        time.sleep(REQUEST_DELAY)

        parsed = _parse_reserve_page(html, target_date)
        date_str = target_date.strftime("%Y-%m-%d")

        if not parsed:
            print(f"  {date_str}: 예약 미오픈 — 건너뜀")
            continue

        # {theme_doc_id: {"slots": [...]}}
        themes: dict[str, dict] = {}
        avail = full = 0

        for theme_data in parsed:
            theme_name = theme_data["theme_name"]
            theme_doc_id = name_to_doc_id.get(theme_name)
            if theme_doc_id is None:
                print(f"  [WARN] Firestore에 없는 테마: {theme_name!r}")
                continue

            for slot in theme_data["slots"]:
                time_obj = slot["time"]
                status = slot["status"]
                booking_url = slot["booking_url"]

                slot_dt = datetime(
                    target_date.year, target_date.month, target_date.day,
                    time_obj.hour, time_obj.minute,
                )
                if slot_dt <= datetime.now():
                    continue

                themes.setdefault(theme_doc_id, {"slots": []})["slots"].append({
                    "time":        f"{time_obj.hour:02d}:{time_obj.minute:02d}",
                    "status":      status,
                    "booking_url": booking_url,
                })

                if status == "available":
                    avail += 1
                else:
                    full += 1

        if themes:
            h = upsert_cafe_date_schedules(
                db, date_str, CAFE_ID, themes, crawled_at,
                known_hash=known_hashes.get(date_str),
            )
            if h:
                new_hashes[date_str] = h
                writes += 1

        print(f"  {date_str}: 가능 {avail}개 / 마감 {full}개")

    if new_hashes:
        today_str = today.isoformat()
        save_cafe_hashes(db, CAFE_ID, {
            k: v for k, v in {**known_hashes, **new_hashes}.items()
            if k >= today_str
        })

    print(f"\n  스케줄 동기화 완료: {writes}개 날짜 문서 작성")


# ── 메인 ─────────────────────────────────────────────────────────────────────────

def main(run_schedule: bool = True, days: int = 14):
    print("=" * 60)
    print("클레버타운 (clevertown.co.kr) → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)

    print("\n[ 1단계 ] 카페 메타 동기화")
    sync_cafe_meta()

    opener = _make_opener()

    print("\n[ 2단계 ] 세션 획득")
    if not _get_session(opener):
        print("세션 획득 실패, 종료.")
        return
    time.sleep(REQUEST_DELAY)

    # 테마 목록을 오늘 날짜 페이지에서 추출
    print("\n[ 3단계 ] 테마 목록 추출 (오늘 날짜 기준)")
    today = date.today()
    html_today = _fetch_reserve_page(opener, today)
    time.sleep(REQUEST_DELAY)
    parsed_today = _parse_reserve_page(html_today, today)

    if not parsed_today:
        print("  오늘 미오픈 → 다음 날짜 시도")
        for i in range(1, 8):
            next_date = today + timedelta(days=i)
            html = _fetch_reserve_page(opener, next_date)
            time.sleep(REQUEST_DELAY)
            parsed_today = _parse_reserve_page(html, next_date)
            if parsed_today:
                print(f"  {next_date} 기준 테마 {len(parsed_today)}개 발견")
                break

    if not parsed_today:
        print("  테마 정보를 찾을 수 없음, 종료.")
        return

    for t in parsed_today:
        print(f"  테마: {t['theme_name']!r} | poster={t['poster_url']}")

    print("\n[ 4단계 ] 테마 DB 동기화")
    name_to_doc_id = sync_themes(parsed_today)
    if not name_to_doc_id:
        print("테마 동기화 실패, 종료.")
        return

    if run_schedule:
        print(f"\n[ 5단계 ] 스케줄 동기화 (오늘~{days}일 후)")
        sync_schedules(opener, name_to_doc_id, days=days)

    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="클레버타운 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
