"""
크라임씬카페 퍼즐팩토리(puzzlefactory.co.kr) 테마 + 스케줄 DB 동기화 스크립트.

사이트: http://www.puzzlefactory.co.kr
예약 URL: POST http://www.puzzlefactory.co.kr/reservation/detail.html
  Body: JIJEM={code}&H_Date={YYYY-MM-DD}&D_ROOM=

응답 HTML (EUC-KR 인코딩):
  li.lg-4
    h2.res-subtitle              → 테마명
    div.dbox img[src]            → 포스터
    a.res-time.bs-bb (href 있음) → 예약가능, href에서 ROOM_TIME 파싱
    a.res-time.bs-bb.active1     → 예약완료

지점 (JIJEM code → 카카오 place_id):
  S7: 홍대 3호점  (서울 마포구 양화로 120)    → 315548029
  S8: 성수점      (서울 성동구 연무장3길 10-1) → 2022859547
  S4: 강남점      (서울 강남구)               → 카카오 미확인
  (홍대 본점 S1, 홍대 2호점 S2, 강남 2호점 S5 — place_id 미발견, 제외)

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_puzzlefactory_db.py
  uv run python scripts/sync_puzzlefactory_db.py --no-schedule
  uv run python scripts/sync_puzzlefactory_db.py --days 6
"""

import re
import ssl
import sys
import time
import urllib.request
import urllib.parse
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings
from app.firestore_db import (
    init_firestore, get_db, upsert_cafe,
    get_or_create_theme, upsert_cafe_date_schedules,
    load_cafe_hashes, save_cafe_hashes,
)

SITE_URL = "http://www.puzzlefactory.co.kr"
REV_URL = SITE_URL + "/reservation/detail.html"
REQUEST_DELAY = 0.7

BRANCHES = [
    {
        "cafe_id":     "315548029",
        "branch_name": "홍대3호점",
        "jijem":       "S7",
        "area":        "hongdae",
        "address":     "서울 마포구 양화로 120",
    },
    {
        "cafe_id":     "2022859547",
        "branch_name": "성수점",
        "jijem":       "S8",
        "area":        "etc",
        "address":     "서울 성동구 연무장3길 10-1",
    },
]

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Content-Type": "application/x-www-form-urlencoded",
    "Referer": SITE_URL + "/reservation/",
}


def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html)


def fetch_rev_page(jijem: str, target_date: date) -> list[dict]:
    """
    날짜별 예약 현황 파싱.
    반환: [{name, poster_url, slots: [{time, status, booking_url}]}]
    """
    date_str = target_date.strftime("%Y-%m-%d")
    body = urllib.parse.urlencode({"JIJEM": jijem, "H_Date": date_str, "D_ROOM": ""}).encode()
    req = urllib.request.Request(REV_URL, data=body, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            raw = resp.read()
    except Exception as e:
        print(f"  [WARN] POST {REV_URL} (JIJEM={jijem}) 실패: {e}")
        return []

    try:
        html = raw.decode("euc-kr", errors="replace")
    except Exception:
        html = raw.decode("utf-8", errors="replace")

    themes: list[dict] = []

    # li.lg-4 단위로 분리 (각 테마 블록)
    blocks = re.split(r'<li[^>]+class="[^"]*lg-4[^"]*"', html)
    for block in blocks[1:]:
        # 테마명: h2.res-subtitle
        m_name = re.search(r'<h2[^>]+class="[^"]*res-subtitle[^"]*"[^>]*>(.*?)</h2>', block, re.DOTALL)
        if not m_name:
            continue
        name = _strip_tags(m_name.group(1)).strip()
        if not name:
            continue

        # 포스터 이미지
        poster_url = None
        m_img = re.search(r'<img[^>]+src="(/upload_file/[^"]+)"', block, re.IGNORECASE)
        if m_img:
            poster_url = SITE_URL + m_img.group(1)

        # 슬롯 파싱
        slots: list[dict] = []
        for a_html in re.split(r'<a\b', block)[1:]:
            a_full = "<a" + a_html.split("</a>")[0] + "</a>"
            cls_m = re.search(r'class="([^"]*)"', a_full)
            if not cls_m:
                continue
            cls = cls_m.group(1)
            if "res-time" not in cls:
                continue

            # 시간 추출 (텍스트에서 HH:MM)
            text = _strip_tags(a_full).strip()
            m_time = re.search(r"(\d{2}):(\d{2})", text)
            if not m_time:
                continue
            time_str = f"{m_time.group(1)}:{m_time.group(2)}"

            if "active1" in cls:
                # 예약완료
                slots.append({"time": time_str, "status": "full", "booking_url": None})
            else:
                # href에서 booking_url 추출
                href_m = re.search(r'href="([^"]+)"', a_full)
                booking_url = (SITE_URL + href_m.group(1)) if href_m else SITE_URL
                slots.append({"time": time_str, "status": "available", "booking_url": booking_url})

        themes.append({"name": name, "poster_url": poster_url, "slots": slots})

    return themes


# ── DB 동기화 ─────────────────────────────────────────────────────────────────

def sync_cafe_meta(db, branch: dict) -> None:
    upsert_cafe(db, branch["cafe_id"], {
        "name":        "크라임씬카페 퍼즐팩토리",
        "branch_name": branch["branch_name"],
        "address":     branch["address"],
        "area":        branch["area"],
        "website_url": SITE_URL,
        "engine":      "puzzlefactory",
        "crawled":     True,
        "is_active":   True,
    })
    print(f"  [UPSERT] 카페: 크라임씬카페 퍼즐팩토리 {branch['branch_name']} (id={branch['cafe_id']})")


def sync_schedules(days: int = 6) -> None:
    db = get_db()
    today = date.today()
    target_dates = [today + timedelta(days=i) for i in range(days + 1)]
    crawled_at = datetime.now()
    total_writes = 0

    for branch in BRANCHES:
        cafe_id = branch["cafe_id"]
        jijem = branch["jijem"]
        print(f"\n  {branch['branch_name']} (JIJEM={jijem}, id={cafe_id})")

        cafe_doc = db.collection("cafes").document(cafe_id).get()
        if not cafe_doc.exists:
            print(f"  [WARN] cafe {cafe_id} Firestore 미존재 — 건너뜀")
            continue

        theme_cache: dict[str, str] = {}
        date_themes: dict[str, dict] = {}

        for target_date in target_dates:
            date_str = target_date.strftime("%Y-%m-%d")
            themes = fetch_rev_page(jijem, target_date)
            time.sleep(REQUEST_DELAY)

            if not themes:
                continue

            avail_cnt = full_cnt = 0

            for t in themes:
                name = t["name"]
                if not name:
                    continue

                if name not in theme_cache:
                    doc_id = get_or_create_theme(db, cafe_id, name, {
                        "poster_url": t.get("poster_url"),
                        "is_active":  True,
                    })
                    theme_cache[name] = doc_id
                    print(f"  [UPSERT] 테마: {name}")
                theme_doc_id = theme_cache[name]

                for slot in t["slots"]:
                    time_str = slot.get("time")
                    if not time_str:
                        continue
                    try:
                        hh, mm = int(time_str[:2]), int(time_str[3:5])
                    except Exception:
                        continue

                    slot_dt = datetime(
                        target_date.year, target_date.month, target_date.day, hh, mm,
                    )
                    if slot_dt <= datetime.now():
                        continue

                    status = slot["status"]
                    date_themes.setdefault(date_str, {}).setdefault(
                        theme_doc_id, {"slots": []}
                    )["slots"].append({
                        "time":        f"{hh:02d}:{mm:02d}",
                        "status":      status,
                        "booking_url": slot.get("booking_url"),
                    })

                    if status == "available":
                        avail_cnt += 1
                    else:
                        full_cnt += 1

            print(f"    {date_str}: 가능 {avail_cnt} / 마감 {full_cnt}")

        known_hashes = load_cafe_hashes(db, cafe_id)
        new_hashes: dict[str, str] = {}
        for date_str, themes_map in date_themes.items():
            h = upsert_cafe_date_schedules(
                db, date_str, cafe_id, themes_map, crawled_at,
                known_hash=known_hashes.get(date_str),
            )
            if h:
                new_hashes[date_str] = h
                total_writes += 1

        if new_hashes:
            today_str = date.today().isoformat()
            save_cafe_hashes(db, cafe_id, {
                k: v for k, v in {**known_hashes, **new_hashes}.items()
                if k >= today_str
            })

    print(f"\n  스케줄 동기화 완료: {total_writes}개 날짜 문서 작성")


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main(run_schedule: bool = True, days: int = 6):
    print("=" * 60)
    print("크라임씬카페 퍼즐팩토리(puzzlefactory.co.kr) → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)
    db = get_db()

    print("\n[ 1단계 ] 카페 메타 동기화")
    for branch in BRANCHES:
        sync_cafe_meta(db, branch)

    if run_schedule:
        print(f"\n[ 2단계 ] 스케줄 동기화 (오늘~{days}일 후)")
        sync_schedules(days=days)

    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="퍼즐팩토리 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=6, help="오늘부터 며칠치 수집 (기본 6)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
