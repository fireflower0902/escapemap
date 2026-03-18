"""
덤앤더머 방탈출카페(dumbndumber.kr) 테마 + 스케줄 DB 동기화 스크립트.

플랫폼: 자체 PHP (sinbiweb 유사 구조)

API: GET {site_url}/reservation.html?k_shopno={N}&rdate={YYYY-MM-DD}
  응답: HTML
    div.theme_box → 테마 블록
      h3.h3_theme → 테마명
      div.theme_pic img[src] → 포스터
      ul.reserve_Time > li > a → 슬롯
        - a[href^="reservation_02.html?..."] → 예약가능
        - a.end[href="javascript:;"] → 예약마감

지점:
  http://www.dumbndumber.kr    k_shopno=1: 대학로점  cafe_id=203642029  (서울 종로구 대학로12길 40 3층)
  http://www.dumbndumber-sm.kr k_shopno=1: 서면점    cafe_id=28574930   (부산 부산진구 서면문화로 27)

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_dumbndumber_db.py
  uv run python scripts/sync_dumbndumber_db.py --no-schedule
  uv run python scripts/sync_dumbndumber_db.py --days 14
"""

import re
import ssl
import sys
import time
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

REQUEST_DELAY = 0.8

BRANCHES = [
    {
        "cafe_id":     "203642029",
        "branch_name": "대학로점",
        "shopno":      1,
        "area":        "myeongdong",
        "address":     "서울 종로구 대학로12길 40 3층",
        "site_url":    "http://www.dumbndumber.kr",
    },
    {
        "cafe_id":     "28574930",
        "branch_name": "서면점",
        "shopno":      1,
        "area":        "busan",
        "address":     "부산 부산진구 서면문화로 27",
        "site_url":    "http://www.dumbndumber-sm.kr",
    },
]

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

_BASE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "ko-KR,ko;q=0.9",
}


def _strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s).strip()


def fetch_slots(site_url: str, shopno: int, target_date: date) -> list[dict]:
    """날짜별 슬롯 조회. 반환: [{name, poster_url, slots: [{time, status, booking_url}]}]"""
    date_str = target_date.strftime("%Y-%m-%d")
    url = f"{site_url}/reservation.html?k_shopno={shopno}&rdate={date_str}"
    headers = {**_BASE_HEADERS, "Referer": site_url + "/"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [WARN] GET 실패 (date={date_str}): {e}")
        return []

    themes: list[dict] = []

    # 테마 블록 분리 (div.theme_box 기준)
    blocks = re.split(r'<div[^>]+class="[^"]*theme_box[^"]*"', body)
    for block in blocks[1:]:
        # 테마명: h3.h3_theme
        m_name = re.search(r'<h3[^>]*class="[^"]*h3_theme[^"]*"[^>]*>(.*?)</h3>', block, re.DOTALL)
        if not m_name:
            continue
        name = _strip_tags(m_name.group(1)).strip()
        if not name:
            continue

        # 포스터: theme_pic img
        poster_url = None
        m_img = re.search(r'<div[^>]*class="[^"]*theme_pic[^"]*"[^>]*>.*?<img[^>]+src="([^"]+)"', block, re.DOTALL)
        if m_img:
            src = m_img.group(1)
            if src.startswith("http"):
                poster_url = src
            elif src.startswith("/"):
                poster_url = site_url + src
            else:
                poster_url = site_url + "/" + src

        slots: list[dict] = []

        # 슬롯: ul.reserve_Time > li > a
        for m_li in re.finditer(r'<li[^>]*>(.*?)</li>', block, re.DOTALL):
            li_content = m_li.group(1)

            # 시간 추출
            m_time = re.search(r'<span[^>]*class="[^"]*time[^"]*"[^>]*>(\d{2}:\d{2})</span>', li_content)
            if not m_time:
                continue
            time_str = m_time.group(1)

            # a 태그 분석
            m_a = re.search(r'<a[^>]+href="([^"]*)"[^>]*class="([^"]*)"[^>]*>|<a[^>]+class="([^"]*)"[^>]+href="([^"]*)"[^>]*>|<a[^>]+href="([^"]*)"[^>]*>', li_content)
            if not m_a:
                continue

            href = m_a.group(1) or m_a.group(4) or m_a.group(5) or ""
            cls = m_a.group(2) or m_a.group(3) or ""

            if "end" in cls or href == "javascript:;":
                status = "full"
                booking_url = None
            elif "reservation_02.html" in href:
                status = "available"
                booking_url = site_url + "/" + href if not href.startswith("http") else href
            else:
                continue

            slots.append({"time": time_str, "status": status, "booking_url": booking_url})

        if slots:
            themes.append({"name": name, "poster_url": poster_url, "slots": slots})

    return themes


# ── DB 동기화 ─────────────────────────────────────────────────────────────────

def sync_cafe_meta(db, branch: dict) -> None:
    upsert_cafe(db, branch["cafe_id"], {
        "name":        "덤앤더머 방탈출카페",
        "branch_name": branch["branch_name"],
        "address":     branch["address"],
        "area":        branch["area"],
        "website_url": branch["site_url"],
        "engine":      "dumbndumber",
        "crawled":     True,
        "is_active":   True,
    })
    print(f"  [UPSERT] 카페: 덤앤더머 {branch['branch_name']} (id={branch['cafe_id']})")


def sync_branch(branch: dict, days: int = 14) -> int:
    db = get_db()
    cafe_id = branch["cafe_id"]
    shopno = branch["shopno"]
    site_url = branch["site_url"]
    today = date.today()
    target_dates = [today + timedelta(days=i) for i in range(days + 1)]
    crawled_at = datetime.now()
    total_writes = 0

    cafe_doc = db.collection("cafes").document(cafe_id).get()
    if not cafe_doc.exists:
        print(f"  [WARN] cafe {cafe_id} Firestore 미존재 — 건너뜀")
        return 0

    theme_cache: dict[str, str] = {}
    date_themes: dict[str, dict] = {}

    for target_date in target_dates:
        date_str = target_date.strftime("%Y-%m-%d")
        raw_themes = fetch_slots(site_url, shopno, target_date)
        time.sleep(REQUEST_DELAY)

        if not raw_themes:
            print(f"  {date_str}: 데이터 없음")
            continue

        avail_cnt = full_cnt = 0

        for t in raw_themes:
            name = t["name"]
            if name not in theme_cache:
                doc_id = get_or_create_theme(db, cafe_id, name, {
                    "poster_url": t.get("poster_url"),
                    "is_active":  True,
                })
                theme_cache[name] = doc_id
                print(f"  [UPSERT] 테마: {name}")
            theme_doc_id = theme_cache[name]

            for slot in t["slots"]:
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

        print(f"  {date_str}: 가능 {avail_cnt} / 마감 {full_cnt}")

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
        today_str = today.isoformat()
        save_cafe_hashes(db, cafe_id, {
            k: v for k, v in {**known_hashes, **new_hashes}.items()
            if k >= today_str
        })

    print(f"  스케줄 동기화 완료: {total_writes}개 날짜 문서 작성")
    return total_writes


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main(run_schedule: bool = True, days: int = 14):
    print("=" * 60)
    print("덤앤더머 방탈출카페(dumbndumber.kr) → DB 동기화")
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
                sync_branch(branch, days=days)
            except Exception as e:
                print(f"  [ERROR] {branch['branch_name']} 크롤링 실패: {e}")

    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="덤앤더머 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
