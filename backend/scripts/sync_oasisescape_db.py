"""
오아시스 뮤지엄 방탈출 (oasismuseum.com) 테마 + 스케줄 DB 동기화 스크립트.

사이트: https://oasismuseum.com
플랫폼: 자체 PHP/Laravel 기반

지점:
  홍대점  cafe_id=848848018  area=hongdae  (서울 마포구 독막로9길 18)

테마 ID:
  1  업사이드 다운
  5  미씽 삭스 미스터리
  6  배드 타임 (BÆD TIME)
  8  하이 맥스 (HIGH MAX)
  15 4 SUM 1

API:
  1단계 - 슬롯 목록:
    GET https://oasismuseum.com/ticket?id={tm}&date={YYYY-MM-DD}
    HTML:
      span#tm_name{id}        → "[지점명]<br>테마명" 형식
      img.swiper-img.center-crop (첫 번째) → 포스터 URL
      button.room_btn[data-tm={tm}][data-time="HH:MM"][value="{schedule_id}"]
        → 슬롯 목록 (전부 btn-closed로 초기화)

  2단계 - 마감 여부:
    POST https://oasismuseum.com/ticket/getSchedule
    Body (form-urlencoded): tm={tm}&date={YYYY-MM-DD}
    응답 (JSON): 마감된 schedule_id 배열, 없으면 null
    → 반환된 ID에 해당하는 슬롯은 full, 나머지는 available

예약 URL: https://oasismuseum.com/ticket?id={tm} (슬롯별 직접 링크 없음)

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_oasisescape_db.py
  uv run python scripts/sync_oasisescape_db.py --no-schedule
  uv run python scripts/sync_oasisescape_db.py --days 14
"""

import json
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
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

SITE_URL      = "https://oasismuseum.com"
TICKET_URL    = f"{SITE_URL}/ticket"
SCHEDULE_URL  = f"{SITE_URL}/ticket/getSchedule"
REQUEST_DELAY = 0.8

CAFE_ID     = "848848018"
BRANCH_NAME = None
ADDRESS     = "서울 마포구 서교동 403-21"
AREA        = "hongdae"

THEME_IDS = [1, 5, 6, 8, 15]

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

HEADERS_POST = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Referer": TICKET_URL,
    "X-Requested-With": "XMLHttpRequest",
}


def fetch_ticket_page(tm: int, target_date: date) -> str:
    """GET /ticket?id={tm}&date={YYYY-MM-DD} → HTML"""
    date_str = target_date.strftime("%Y-%m-%d")
    url = f"{TICKET_URL}?id={tm}&date={date_str}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [WARN] GET {url} 실패: {e}")
        return ""


def fetch_closed_schedule_ids(tm: int, target_date: date) -> set[str]:
    """POST /ticket/getSchedule → 마감된 schedule_id 집합."""
    date_str = target_date.strftime("%Y-%m-%d")
    body = urllib.parse.urlencode({"tm": str(tm), "date": date_str}).encode("utf-8")
    req = urllib.request.Request(SCHEDULE_URL, data=body, headers=HEADERS_POST)
    try:
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace").strip()
        data = json.loads(raw)
        if data is None:
            return set()
        return {str(x) for x in data}
    except Exception as e:
        print(f"  [WARN] POST getSchedule tm={tm} {date_str} 실패: {e}")
        return set()


def parse_ticket_page(html: str, tm: int) -> dict:
    """
    반환:
      {
        "theme_name": str,
        "poster_url": str | None,
        "slots": [{"schedule_id": str, "time": str}]
      }
    """
    soup = BeautifulSoup(html, "html.parser")

    # 테마명: <span id="tm_name{id}">[지점명]<br>테마명</span>
    name_tag = soup.find("span", id=f"tm_name{tm}")
    if name_tag:
        # <br> 뒤의 텍스트만 추출
        br = name_tag.find("br")
        if br and br.next_sibling:
            theme_name = str(br.next_sibling).strip()
        else:
            theme_name = name_tag.get_text(separator=" ", strip=True)
            # "[지점명] 테마명" → 테마명 추출 시도
            theme_name = re.sub(r"^\[.*?\]\s*", "", theme_name).strip()
    else:
        theme_name = f"테마{tm}"

    # 포스터: 첫 번째 img.swiper-img.center-crop
    poster_url = None
    img_tag = soup.find("img", class_=lambda c: c and "swiper-img" in c and "center-crop" in c)
    if img_tag and img_tag.get("src"):
        src = img_tag["src"]
        if src.startswith("http"):
            poster_url = src
        else:
            poster_url = SITE_URL + src

    # 슬롯: button.room_btn[data-tm="{tm}"][value=schedule_id][data-time=HH:MM]
    slots = []
    for btn in soup.find_all("button", attrs={"data-tm": str(tm)}):
        schedule_id = btn.get("value", "").strip()
        time_val = btn.get("data-time", "").strip()
        if schedule_id and time_val:
            slots.append({"schedule_id": schedule_id, "time": time_val})

    return {"theme_name": theme_name, "poster_url": poster_url, "slots": slots}


# ── DB 동기화 ─────────────────────────────────────────────────────────────────

def sync_cafe_meta(db) -> None:
    upsert_cafe(db, CAFE_ID, {
        "name":        "오아시스 뮤지엄",
        "branch_name": BRANCH_NAME,
        "address":     ADDRESS,
        "area":        AREA,
        "website_url": SITE_URL,
        "engine":      "oasisescape",
        "crawled":     True,
        "is_active":   True,
    })
    print(f"  [UPSERT] 카페: 오아시스 뮤지엄 (id={CAFE_ID})")


def sync_schedules(db, days: int = 14) -> int:
    today = date.today()
    crawled_at = datetime.now()

    cafe_doc = db.collection("cafes").document(CAFE_ID).get()
    if not cafe_doc.exists:
        print(f"  [WARN] cafe {CAFE_ID} Firestore 미존재 — 건너뜀")
        return 0

    theme_cache: dict[str, str] = {}   # theme_name → theme_doc_id
    poster_cache: dict[str, str | None] = {}  # theme_name → poster_url
    date_themes: dict[str, dict] = {}
    writes = 0

    for i in range(days + 1):
        target_date = today + timedelta(days=i)
        date_str = target_date.strftime("%Y-%m-%d")

        avail = full = 0

        for tm in THEME_IDS:
            html = fetch_ticket_page(tm, target_date)
            time.sleep(REQUEST_DELAY)

            if not html:
                print(f"  {date_str} tm={tm}: HTML 없음")
                continue

            parsed = parse_ticket_page(html, tm)
            theme_name = parsed["theme_name"]
            slots_raw = parsed["slots"]

            if not slots_raw:
                # 슬롯이 없는 날은 미오픈
                print(f"  {date_str} {theme_name}: 슬롯 없음 (미오픈)")
                continue

            # 테마 등록
            if theme_name not in theme_cache:
                doc_id = get_or_create_theme(db, CAFE_ID, theme_name, {
                    "poster_url": parsed["poster_url"],
                    "is_active":  True,
                })
                theme_cache[theme_name] = doc_id
                poster_cache[theme_name] = parsed["poster_url"]
                print(f"  [UPSERT] 테마: {theme_name} (poster={parsed['poster_url']})")
            theme_doc_id = theme_cache[theme_name]

            # 마감된 schedule_id 조회
            closed_ids = fetch_closed_schedule_ids(tm, target_date)
            time.sleep(REQUEST_DELAY)

            booking_url = f"{TICKET_URL}?id={tm}"

            for slot in slots_raw:
                schedule_id = slot["schedule_id"]
                time_val = slot["time"]

                # 시간 파싱
                try:
                    hh, mm = map(int, time_val.split(":"))
                except Exception:
                    continue

                slot_dt = datetime(
                    target_date.year, target_date.month, target_date.day, hh, mm
                )
                if slot_dt <= datetime.now():
                    continue

                status = "full" if schedule_id in closed_ids else "available"

                date_themes.setdefault(date_str, {}).setdefault(
                    theme_doc_id, {"slots": []}
                )["slots"].append({
                    "time":        f"{hh:02d}:{mm:02d}",
                    "status":      status,
                    "booking_url": booking_url if status == "available" else None,
                })

                if status == "available":
                    avail += 1
                else:
                    full += 1

        print(f"  {date_str}: 가능 {avail} / 마감 {full}")

    known_hashes = load_cafe_hashes(db, CAFE_ID)
    new_hashes: dict[str, str] = {}
    for date_str, themes in date_themes.items():
        h = upsert_cafe_date_schedules(
            db, date_str, CAFE_ID, themes, crawled_at,
            known_hash=known_hashes.get(date_str),
        )
        if h:
            new_hashes[date_str] = h
            writes += 1

    if new_hashes:
        today_str = today.isoformat()
        save_cafe_hashes(db, CAFE_ID, {
            k: v for k, v in {**known_hashes, **new_hashes}.items()
            if k >= today_str
        })

    print(f"  스케줄 동기화 완료: {writes}개 날짜 문서 작성")
    return writes


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main(run_schedule: bool = True, days: int = 14):
    print("=" * 60)
    print("오아시스 뮤지엄(oasismuseum.com) → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)
    db = get_db()

    print("\n[ 1단계 ] 카페 메타 동기화")
    sync_cafe_meta(db)

    if run_schedule:
        print(f"\n[ 2단계 ] 스케줄 동기화 (오늘~{days}일 후)")
        sync_schedules(db, days=days)

    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="오아시스 뮤지엄 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
