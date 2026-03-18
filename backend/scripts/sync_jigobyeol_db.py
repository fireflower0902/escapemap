"""
지구별방탈출 홍대 두 지점 테마 + 스케줄 DB 동기화 스크립트.

사이트: https://지구별.com (https://www.xn--2e0b040a4xj.com)
지점:
  - 홍대어드벤처점 (branch=2): 카카오맵 place_id=2070697879
    주소: 서울 마포구 와우산로21길 31 3층
  - 홍대라스트시티점 (branch=4): 카카오맵 place_id=399012410
    주소: 서울 마포구 홍익로 10 지하2층
  - 대구점 (branch=1): 카카오맵 place_id=7690632, 테마=[잉카(20)]
    주소: 대구 중구 동성로2가 127-2

⚠️  제한사항:
  이 사이트는 오늘 날짜의 슬롯만 표시합니다 (날짜 파라미터 미지원).
  따라서 매 크롤링 시 오늘 예약 현황만 갱신됩니다.

API:
  GET https://www.xn--2e0b040a4xj.com/reservation?branch={BRANCH}&theme={THEME_ID}
  응답: HTML
    - div.res-times-btn 하위에 슬롯 목록
    - label 텍스트 "예약가능" → available
    - label 텍스트 "예약불가" → full
    - span.ff-bhs → 시간 "HH:MM"

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_jigobyeol_db.py
  uv run python scripts/sync_jigobyeol_db.py --no-schedule
"""

import re
import sys
import time
import urllib.request
import urllib.parse
from datetime import date, datetime, time as dtime
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

BASE_URL = "https://www.xn--2e0b040a4xj.com"
RESERVATION_URL = BASE_URL + "/reservation"
BOOKING_URL = BASE_URL + "/reservation"
REQUEST_DELAY = 1.0

# 지점 정의
BRANCHES = [
    {
        "branch": 2,
        "cafe_id": "2070697879",
        "name": "지구별방탈출",
        "branch_name": "홍대어드벤처점",
        "address": "서울 마포구 와우산로21길 31 3층",
        "area": "hongdae",
        "website_url": "https://xn--2e0b040a4xj.com",
        "theme_ids": [25, 23, 18, 17, 9, 8],
    },
    {
        "branch": 4,
        "cafe_id": "399012410",
        "name": "지구별방탈출",
        "branch_name": "홍대라스트시티점",
        "address": "서울 마포구 홍익로 10 지하2층",
        "area": "hongdae",
        "website_url": "https://xn--2e0b040a4xj.com",
        "theme_ids": [24, 22, 21, 19, 15, 14, 13, 12],
    },
    {
        "branch": 1,
        "cafe_id": "7690632",
        "name": "지구별방탈출",
        "branch_name": "대구점",
        "address": "대구 중구 동성로2가 127-2",
        "area": "daegu",
        "website_url": "https://xn--2e0b040a4xj.com",
        "theme_ids": [20],
    },
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": BASE_URL + "/",
}


# ── HTML 파싱 ─────────────────────────────────────────────────────────────────

def _fetch_theme_page(branch: int, theme_id: int) -> str:
    """예약 페이지 HTML을 가져옵니다."""
    url = f"{RESERVATION_URL}?branch={branch}&theme={theme_id}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"  [WARN] 페이지 조회 실패 branch={branch} theme={theme_id}: {e}")
        return ""


def _parse_theme_name(html: str, theme_id: int) -> str:
    """HTML에서 테마명을 파싱합니다. 실패 시 'Theme {theme_id}' 반환."""
    soup = BeautifulSoup(html, "html.parser")

    # 공통 테마 제목 선택자 시도
    for selector in [".theme-title", ".room-title", "h1.title", ".res-theme-name", "h2", "h1"]:
        el = soup.select_one(selector)
        if el:
            text = el.get_text(strip=True)
            if text and len(text) < 50:
                return text

    # select 옵션에서 현재 theme_id에 해당하는 것 찾기
    for opt in soup.select(f"option[value='{theme_id}']"):
        text = opt.get_text(strip=True)
        if text:
            return text

    return f"테마{theme_id}"


def _parse_slots(html: str) -> list[dict]:
    """
    HTML에서 슬롯 목록을 파싱합니다.
    반환: [{"time": dtime, "status": "available"|"full"}]
    """
    soup = BeautifulSoup(html, "html.parser")
    slots = []

    for slot_div in soup.select("div.res-times-btn"):
        # 시간 파싱
        time_span = slot_div.select_one("span.ff-bhs")
        if not time_span:
            # 다른 시간 표시 방법 시도
            time_span = slot_div.find("span", string=re.compile(r"\d{1,2}:\d{2}"))
        if not time_span:
            continue

        time_text = time_span.get_text(strip=True)
        m = re.search(r"(\d{1,2}):(\d{2})", time_text)
        if not m:
            continue

        try:
            time_obj = dtime(int(m.group(1)), int(m.group(2)))
        except Exception:
            continue

        # 가용성 파싱
        label = slot_div.find("label")
        if label:
            label_text = label.get_text(strip=True)
            if "예약가능" in label_text:
                status = "available"
            else:
                status = "full"
        else:
            # input type=radio 로 판단
            inp = slot_div.find("input", {"type": "radio"})
            status = "available" if inp and not inp.get("disabled") else "full"

        slots.append({"time": time_obj, "status": status})

    return slots


# ── DB 동기화 ─────────────────────────────────────────────────────────────────

def sync_cafe_meta(branch_info: dict):
    """카페 메타데이터를 Firestore에 upsert합니다."""
    db = get_db()
    upsert_cafe(db, branch_info["cafe_id"], {
        "name":        branch_info["name"],
        "branch_name": branch_info["branch_name"],
        "address":     branch_info["address"],
        "area":        branch_info["area"],
        "phone":       None,
        "website_url": branch_info["website_url"],
        "engine":      "jigobyeol",
        "crawled":     True,
        "lat":         None,
        "lng":         None,
        "is_active":   True,
    })
    print(f"  [UPSERT] 카페: {branch_info['name']} {branch_info['branch_name']} (id={branch_info['cafe_id']})")


def sync_branch(branch_info: dict) -> int:
    """
    한 지점의 테마 + 오늘 스케줄을 Firestore에 동기화합니다.
    반환: 작성된 날짜 문서 수
    """
    db = get_db()
    cafe_id = branch_info["cafe_id"]
    branch = branch_info["branch"]

    cafe_doc = db.collection("cafes").document(cafe_id).get()
    if not cafe_doc.exists:
        print(f"  [ERROR] cafe {cafe_id} Firestore 미존재")
        return 0

    today = date.today()
    date_str = today.strftime("%Y-%m-%d")
    crawled_at = datetime.now()
    writes = 0

    # {theme_doc_id: {"slots": [...]}}
    themes_today: dict[str, dict] = {}

    for theme_id in branch_info["theme_ids"]:
        html = _fetch_theme_page(branch, theme_id)
        time.sleep(REQUEST_DELAY)

        if not html:
            continue

        theme_name = _parse_theme_name(html, theme_id)
        slots = _parse_slots(html)

        if not slots:
            print(f"  branch={branch} theme={theme_id} ({theme_name}): 슬롯 없음 (오픈 전 또는 파싱 실패)")
            continue

        # 테마 upsert
        theme_doc_id = get_or_create_theme(db, cafe_id, theme_name, {
            "difficulty":   None,
            "duration_min": None,
            "poster_url":   None,
            "is_active":    True,
        })

        avail_cnt = 0
        full_cnt = 0

        for slot in slots:
            time_obj = slot["time"]
            status = slot["status"]

            # 과거 시간 건너뜀
            slot_dt = datetime(
                today.year, today.month, today.day,
                time_obj.hour, time_obj.minute,
            )
            if slot_dt <= datetime.now():
                continue

            booking_url = f"{BOOKING_URL}?branch={branch}&theme={theme_id}" if status == "available" else None

            themes_today.setdefault(theme_doc_id, {"slots": []})["slots"].append({
                "time":        f"{time_obj.hour:02d}:{time_obj.minute:02d}",
                "status":      status,
                "booking_url": booking_url,
            })

            if status == "available":
                avail_cnt += 1
            else:
                full_cnt += 1

        print(f"  branch={branch} theme={theme_id} ({theme_name}): 가능 {avail_cnt} / 마감 {full_cnt}")

    if themes_today:
        known_hashes = load_cafe_hashes(db, cafe_id)
        h = upsert_cafe_date_schedules(
            db, date_str, cafe_id, themes_today, crawled_at,
            known_hash=known_hashes.get(date_str),
        )
        if h:
            today_str = date.today().isoformat()
            save_cafe_hashes(db, cafe_id, {
                k: v for k, v in {**known_hashes, date_str: h}.items()
                if k >= today_str
            })
            writes += 1
            print(f"  → {date_str} 스케줄 저장 완료")
        else:
            print(f"  → {date_str} 변경 없음, 건너뜀")

    return writes


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main(run_schedule: bool = True):
    print("=" * 60)
    print("지구별방탈출 홍대 두 지점 → DB 동기화")
    print("=" * 60)
    print("⚠️  오늘 날짜 슬롯만 수집됩니다 (사이트 제한)")

    init_firestore(settings.firebase_credentials_path)

    total_writes = 0
    for branch_info in BRANCHES:
        print(f"\n[ {branch_info['branch_name']} (branch={branch_info['branch']}) ]")
        try:
            print("  카페 메타 동기화 중...")
            sync_cafe_meta(branch_info)

            if run_schedule:
                w = sync_branch(branch_info)
                total_writes += w
        except Exception as e:
            print(f"  [ERROR] {branch_info['branch_name']} 크롤링 실패: {e}")

    print(f"\n총 {total_writes}개 날짜 문서 작성")
    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="지구별방탈출 홍대점 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule)
