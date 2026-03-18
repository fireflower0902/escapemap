"""
서울이스케이프룸(seoul-escape.com) 테마 + 스케줄 DB 동기화 스크립트.

사이트: https://www.seoul-escape.com
플랫폼: 자체 Laravel 기반 (SPA-like, 서버사이드 렌더링)

API: GET https://www.seoul-escape.com/reservation?branch={N}&date={YYYY-MM-DD}
  응답: HTML
    section.res-item → 테마 블록
      figure.res-item-img img[src] → 포스터
      h3.ff-bhs → 테마명
      button → 슬롯
        label → "예약가능" or "예약불가"
        span.ff-bhs → "HH:MM"
        div.d-n.eveHiddenData → JSON {"branch":N,"theme":M,"date":"YYYY-MM-DD","time":"HH:MM"}

예약 URL: https://www.seoul-escape.com/reservation/create?branch={N}&theme={M}&date={YYYY-MM-DD}&time={HH:MM}

지점:
  branch=1: 홍대점  cafe_id=1351400084  (서울 마포구 어울마당로 138)
  branch=2: 인천부평점 cafe_id=427897815  (경기 인천 부평)
  branch=4: 대구동성로점 cafe_id=892545149
  branch=6: 부산서면점 cafe_id=310013350

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_seoulescaperoom_db.py
  uv run python scripts/sync_seoulescaperoom_db.py --no-schedule
  uv run python scripts/sync_seoulescaperoom_db.py --days 14
"""

import html
import json
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

SITE_URL = "https://www.seoul-escape.com"
REQUEST_DELAY = 0.8

BRANCHES = [
    {
        "cafe_id":     "1351400084",
        "branch_name": "홍대점",
        "branch":      1,
        "area":        "hongdae",
        "address":     "서울 마포구 어울마당로 138",
    },
    {
        "cafe_id":     "427897815",
        "branch_name": "인천부평점",
        "branch":      2,
        "area":        "incheon",
        "address":     "인천 부평구 부평대로 153",
    },
    {
        "cafe_id":     "892545149",
        "branch_name": "대구동성로점",
        "branch":      4,
        "area":        "daegu",
        "address":     "대구 중구 동성로2가 144",
    },
    {
        "cafe_id":     "310013350",
        "branch_name": "부산서면점",
        "branch":      6,
        "area":        "busan",
        "address":     "부산 부산진구 서면로68번길 38",
    },
]

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "ko-KR,ko;q=0.9",
}


def _strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s).strip()


def fetch_slots(branch: int, target_date: date) -> list[dict]:
    """날짜별 슬롯 조회. 반환: [{name, poster_url, slots: [{time, status, booking_url}]}]"""
    date_str = target_date.strftime("%Y-%m-%d")
    url = f"{SITE_URL}/reservation?branch={branch}&date={date_str}#list"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [WARN] GET 실패 (date={date_str}): {e}")
        return []

    themes: list[dict] = []

    # 테마 블록 분리 (section.res-item 기준)
    blocks = re.split(r'<section[^>]*class="[^"]*res-item[^"]*"', body)
    for block in blocks[1:]:
        # 포스터
        poster_url = None
        m_img = re.search(r'<img[^>]+src="(https://[^"]+)"[^>]+alt="[^"]*"', block)
        if m_img:
            poster_url = m_img.group(1)

        # 테마명: h3.ff-bhs
        m_name = re.search(r'<h3[^>]*class="[^"]*ff-bhs[^"]*"[^>]*>(.*?)</h3>', block, re.DOTALL)
        if not m_name:
            continue
        name = _strip_tags(m_name.group(1))
        if not name:
            continue

        slots: list[dict] = []

        # 슬롯 파싱: button 단위
        for m_btn in re.finditer(r'<button[^>]*>(.*?)</button>', block, re.DOTALL):
            btn_content = m_btn.group(1)

            # 시간 추출
            m_time = re.search(r'<span[^>]*class="[^"]*ff-bhs[^"]*"[^>]*>(\d{2}:\d{2})</span>', btn_content)
            if not m_time:
                continue
            time_str = m_time.group(1)

            # 상태 판별
            m_label = re.search(r'<label[^>]*>(.*?)</label>', btn_content, re.DOTALL)
            if not m_label:
                continue
            label = _strip_tags(m_label.group(1))

            if label == "예약가능":
                status = "available"
                # JSON eveHiddenData에서 booking URL 구성
                m_json = re.search(r'eveHiddenData[^>]*>([^<]+)<', btn_content)
                booking_url = None
                if m_json:
                    try:
                        data = json.loads(html.unescape(m_json.group(1)))
                        booking_url = (
                            f"{SITE_URL}/reservation/create"
                            f"?branch={data.get('branch', branch)}"
                            f"&theme={data.get('theme', '')}"
                            f"&date={data.get('date', date_str)}"
                            f"&time={data.get('time', time_str)}"
                        )
                    except Exception:
                        booking_url = f"{SITE_URL}/reservation?branch={branch}&date={date_str}"
                else:
                    booking_url = f"{SITE_URL}/reservation?branch={branch}&date={date_str}"
            elif label == "예약불가":
                status = "full"
                booking_url = None
            else:
                continue

            slots.append({"time": time_str, "status": status, "booking_url": booking_url})

        if slots:
            themes.append({"name": name, "poster_url": poster_url, "slots": slots})

    return themes


# ── DB 동기화 ─────────────────────────────────────────────────────────────────

def sync_cafe_meta(db, branch: dict) -> None:
    upsert_cafe(db, branch["cafe_id"], {
        "name":        "서울이스케이프룸",
        "branch_name": branch["branch_name"],
        "address":     branch["address"],
        "area":        branch["area"],
        "website_url": SITE_URL,
        "engine":      "seoulescaperoom",
        "crawled":     True,
        "is_active":   True,
    })
    print(f"  [UPSERT] 카페: 서울이스케이프룸 {branch['branch_name']} (id={branch['cafe_id']})")


def sync_branch(branch: dict, days: int = 14) -> int:
    db = get_db()
    cafe_id = branch["cafe_id"]
    branch_num = branch["branch"]
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
        raw_themes = fetch_slots(branch_num, target_date)
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
    print("서울이스케이프룸(seoul-escape.com) → DB 동기화")
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
    parser = argparse.ArgumentParser(description="서울이스케이프룸 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
