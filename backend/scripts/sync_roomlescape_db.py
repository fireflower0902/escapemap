"""
룸엘이스케이프(roomlescape.com) 테마 + 스케줄 DB 동기화 스크립트.

사이트: http://www.roomlescape.com
플랫폼: 자체 PHP CMS (rev.theme.*.php REST-like API)

지점:
  홍대1호점  showroomSeq=2  cafe_id=596589943  area=hongdae  (서울 마포구 잔다리로 4 2층)
  신림점     showroomSeq=1  cafe_id=628138029  area=etc      (서울 관악구 신림동)
  당곡점     showroomSeq=3  cafe_id=1735229345 area=etc      (서울 관악구 보라매로 4 2-3층)
  신림2호점  showroomSeq=6  cafe_id=782208965  area=etc      (서울 관악구 신림로59길 15-12 1층)

API:
  1) POST http://www.roomlescape.com/rev.theme.list.php
     Body: showroomSeq={N}
     응답 HTML: li[data-themeSeq="{N}"] → 테마 목록

  2) POST http://www.roomlescape.com/rev.theme.time.php
     Body: themeSeq={N}&reservationDate={YYYY-MM-DD}
     응답 HTML:
       a href="javascript:selectTime(...)" > li.possible → 예약가능
       li.impossible → 예약불가

예약 URL: http://www.roomlescape.com/home.php?go=rev.make (예약 페이지 직접 링크 없음)

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_roomlescape_db.py
  uv run python scripts/sync_roomlescape_db.py --no-schedule
  uv run python scripts/sync_roomlescape_db.py --days 14
"""

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

from app.config import settings
from app.firestore_db import (
    init_firestore, get_db, upsert_cafe,
    get_or_create_theme, upsert_cafe_date_schedules,
    load_cafe_hashes, save_cafe_hashes,
)

SITE_URL = "http://www.roomlescape.com"
REQUEST_DELAY = 0.8

BRANCHES = [
    {
        "cafe_id":      "596589943",
        "branch_name":  "홍대1호점",
        "showroom_seq": "2",
        "area":         "hongdae",
        "address":      "서울 마포구 잔다리로 4 2층",
    },
    {
        "cafe_id":      "628138029",
        "branch_name":  "신림점",
        "showroom_seq": "1",
        "area":         "etc",
        "address":      "서울 관악구 신림동",
    },
    {
        "cafe_id":      "1735229345",
        "branch_name":  "당곡점",
        "showroom_seq": "3",
        "area":         "etc",
        "address":      "서울 관악구 보라매로 4 2-3층",
    },
    {
        "cafe_id":      "782208965",
        "branch_name":  "신림2호점",
        "showroom_seq": "6",
        "area":         "etc",
        "address":      "서울 관악구 신림로59길 15-12 1층",
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
    "Accept": "text/html,application/xhtml+xml,*/*",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Content-Type": "application/x-www-form-urlencoded",
    "Referer": SITE_URL + "/home.php?go=rev.make",
}


def _post(path: str, body: dict) -> str:
    url = SITE_URL + path
    data = urllib.parse.urlencode(body).encode()
    req = urllib.request.Request(url, data=data, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [WARN] POST {url} 실패: {e}")
        return ""


def get_themes(showroom_seq: str) -> list[dict]:
    """테마 목록 조회. 반환: [{"seq": str, "name": str}]"""
    html = _post("/rev.theme.list.php", {"showroomSeq": showroom_seq})
    themes = []
    for m in re.finditer(
        r'<li[^>]+data-themeSeq="?(\d+)"?[^>]*>\s*([^<]+?)\s*</li>', html
    ):
        seq = m.group(1)
        name_raw = m.group(2).strip()
        # "[홍대1호점]베니" → "베니" 등 괄호 내 지점명 제거
        name = re.sub(r"^\[[^\]]+\]\s*", "", name_raw).strip() or name_raw
        if name:
            themes.append({"seq": seq, "name": name})
    return themes


def get_slots(theme_seq: str, target_date: date) -> list[dict]:
    """날짜별 슬롯 조회. 반환: [{"time": str, "status": str}]"""
    date_str = target_date.strftime("%Y-%m-%d")
    html = _post("/rev.theme.time.php", {
        "themeSeq":        theme_seq,
        "reservationDate": date_str,
    })
    slots = []

    # 가능: <a href="javascript:selectTime(...)"><li class='possible' ...>HH:MM</li></a>
    avail = re.findall(
        r'<a[^>]+href="javascript:selectTime[^"]*"[^>]*>\s*'
        r'<li[^>]*class=[\'"]possible[\'"][^>]*>\s*(\d{2}:\d{2})\s*</li>',
        html,
    )
    for t in avail:
        slots.append({"time": t, "status": "available"})

    # 불가: <li class='impossible' ...>HH:MM</li>  (링크 없음)
    full = re.findall(
        r'<li[^>]*class=[\'"]impossible[\'"][^>]*>\s*(\d{2}:\d{2})\s*</li>', html
    )
    for t in full:
        slots.append({"time": t, "status": "full"})

    return slots


# ── DB 동기화 ─────────────────────────────────────────────────────────────────

def sync_cafe_meta(db, branch: dict) -> None:
    upsert_cafe(db, branch["cafe_id"], {
        "name":        "룸엘이스케이프",
        "branch_name": branch["branch_name"],
        "address":     branch["address"],
        "area":        branch["area"],
        "website_url": SITE_URL,
        "engine":      "roomlescape",
        "crawled":     True,
        "is_active":   True,
    })
    print(f"  [UPSERT] 카페: 룸엘이스케이프 {branch['branch_name']} (id={branch['cafe_id']})")


def sync_one_branch(branch: dict, days: int) -> int:
    db = get_db()
    cafe_id = branch["cafe_id"]
    showroom_seq = branch["showroom_seq"]
    today = date.today()
    crawled_at = datetime.now()

    cafe_doc = db.collection("cafes").document(cafe_id).get()
    if not cafe_doc.exists:
        print(f"  [WARN] cafe {cafe_id} Firestore 미존재 — 건너뜀")
        return 0

    # 테마 목록 조회
    themes = get_themes(showroom_seq)
    time.sleep(REQUEST_DELAY)

    if not themes:
        print(f"  [{branch['branch_name']}] 테마 정보를 찾을 수 없음, 건너뜀.")
        return 0

    seq_to_doc: dict[str, str] = {}
    for theme in themes:
        doc_id = get_or_create_theme(db, cafe_id, theme["name"], {
            "poster_url": None,
            "is_active":  True,
        })
        seq_to_doc[theme["seq"]] = doc_id
        print(f"  [UPSERT] 테마: {theme['name']} (seq={theme['seq']})")

    # 스케줄 upsert
    target_dates = [today + timedelta(days=i) for i in range(days + 1)]
    known_hashes = load_cafe_hashes(db, cafe_id)
    new_hashes: dict[str, str] = {}
    date_themes: dict[str, dict] = {}
    writes = 0

    for target_date in target_dates:
        date_str = target_date.strftime("%Y-%m-%d")
        avail = full = 0

        for theme in themes:
            doc_id = seq_to_doc[theme["seq"]]
            slots = get_slots(theme["seq"], target_date)
            time.sleep(REQUEST_DELAY)

            for slot in slots:
                time_str = slot["time"]
                try:
                    hh, mm = int(time_str[:2]), int(time_str[3:5])
                except Exception:
                    continue
                slot_dt = datetime(
                    target_date.year, target_date.month, target_date.day, hh, mm,
                )
                if slot_dt <= datetime.now():
                    continue

                date_themes.setdefault(date_str, {}).setdefault(
                    doc_id, {"slots": []}
                )["slots"].append({
                    "time":        f"{hh:02d}:{mm:02d}",
                    "status":      slot["status"],
                    "booking_url": SITE_URL + "/home.php?go=rev.make",
                })
                if slot["status"] == "available":
                    avail += 1
                else:
                    full += 1

        print(f"  {date_str}: 가능 {avail} / 마감 {full}")

    for date_str, themes_map in date_themes.items():
        h = upsert_cafe_date_schedules(
            db, date_str, cafe_id, themes_map, crawled_at,
            known_hash=known_hashes.get(date_str),
        )
        if h:
            new_hashes[date_str] = h
            writes += 1

    if new_hashes:
        today_str = today.isoformat()
        save_cafe_hashes(db, cafe_id, {
            k: v for k, v in {**known_hashes, **new_hashes}.items()
            if k >= today_str
        })

    print(f"  스케줄 동기화: {writes}개 날짜 작성")
    return writes


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main(run_schedule: bool = True, days: int = 14):
    print("=" * 60)
    print("룸엘이스케이프(roomlescape.com) → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)
    db = get_db()

    print("\n[ 1단계 ] 카페 메타 동기화")
    for branch in BRANCHES:
        sync_cafe_meta(db, branch)

    if run_schedule:
        for branch in BRANCHES:
            print(f"\n[ 2단계 ] {branch['branch_name']} 스케줄 동기화 (오늘~{days}일 후)")
                try:
                sync_one_branch(branch, days=days)
            except Exception as e:
                print(f"  [ERROR] {branch['branch_name']} 크롤링 실패: {e}")

    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="룸엘이스케이프 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
