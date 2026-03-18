"""
더트랩 수유점(thetrapsy.co.kr) 테마 + 스케줄 DB 동기화 스크립트.

사이트: http://www.thetrapsy.co.kr
플랫폼: leezeno.com CMS

지점:
  수유점  cafe_id=911063716  area=etc  (서울 강북구 도봉로 363 구봉빌딩 4층)

API:
  POST http://www.thetrapsy.co.kr/re/l/
  Body: d={YYYY-MM-DD}&q=
  응답: 부분 HTML <ul>
    li#pdt{N} → 테마 블록
      strong.tof → 테마명
      p > a[onclick="fnc_rsv('pdt_id','date','slot_id')"] + 텍스트 "HH:MM (예약하기)" → 예약가능
      p.fcCCC → 매진 (시간 정보 없음)

주의:
  leezeno CMS는 테마당 마지막 가용 슬롯 1개만 표시 (전체 슬롯 목록이 아님)

예약 URL: http://www.thetrapsy.co.kr/re/

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_thetrapsy_db.py
  uv run python scripts/sync_thetrapsy_db.py --no-schedule
  uv run python scripts/sync_thetrapsy_db.py --days 14
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

SITE_URL = "http://www.thetrapsy.co.kr"
API_URL = SITE_URL + "/re/l/"
BOOKING_URL = SITE_URL + "/re/"
REQUEST_DELAY = 0.8

BRANCHES = [
    {
        "cafe_id":     "911063716",
        "branch_name": "수유점",
        "area":        "etc",
        "address":     "서울 강북구 도봉로 363 구봉빌딩 4층",
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
    "Referer": SITE_URL + "/re/",
}


def _fetch(target_date: date) -> str:
    date_str = target_date.strftime("%Y-%m-%d")
    data = urllib.parse.urlencode({"d": date_str, "q": ""}).encode()
    req = urllib.request.Request(API_URL, data=data, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [WARN] POST {API_URL} 실패: {e}")
        return ""


def parse_slots(html: str) -> list[dict]:
    """
    부분 HTML 파싱.
    반환: [{theme_name, time, status}]
    leezeno CMS는 테마당 마지막 가용 슬롯 1개 또는 매진 상태만 표시.
    """
    slots: list[dict] = []

    # li#pdt{N} 단위로 분리
    block_pattern = re.compile(
        r'<li[^>]+id="pdt\d+"[^>]*>(.*?)</li>',
        re.DOTALL,
    )
    for m in block_pattern.finditer(html):
        block = m.group(1)

        # 테마명: strong.tof
        m_name = re.search(r'<strong[^>]+class="[^"]*tof[^"]*"[^>]*>([^<]+)</strong>', block)
        if not m_name:
            continue
        theme_name = m_name.group(1).strip()
        if not theme_name:
            continue

        # 예약가능: fnc_rsv 함수 호출 + "HH:MM (예약하기)" 텍스트
        m_avail = re.search(
            r"fnc_rsv\('[^']+',\s*'[^']+',\s*'[^']+'\)[^>]*>(\d{2}:\d{2})\s*\(예약하기\)",
            block,
        )
        if m_avail:
            time_str = m_avail.group(1)
            slots.append({"theme_name": theme_name, "time": time_str, "status": "available"})

    return slots


# ── DB 동기화 ─────────────────────────────────────────────────────────────────

def sync_cafe_meta(db, branch: dict) -> None:
    upsert_cafe(db, branch["cafe_id"], {
        "name":        "더트랩",
        "branch_name": branch["branch_name"],
        "address":     branch["address"],
        "area":        branch["area"],
        "website_url": SITE_URL,
        "engine":      "thetrapsy",
        "crawled":     True,
        "is_active":   True,
    })
    print(f"  [UPSERT] 카페: 더트랩 {branch['branch_name']} (id={branch['cafe_id']})")


def sync_branch(branch: dict, days: int = 14) -> int:
    db = get_db()
    cafe_id = branch["cafe_id"]
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
        html = _fetch(target_date)
        time.sleep(REQUEST_DELAY)

        if not html:
            print(f"  {date_str}: 데이터 없음")
            continue

        raw_slots = parse_slots(html)
        if not raw_slots:
            print(f"  {date_str}: 슬롯 없음")
            continue

        avail_cnt = 0

        for slot in raw_slots:
            theme_name = slot["theme_name"]
            time_str = slot["time"]
            status = slot["status"]

            try:
                hh, mm = int(time_str[:2]), int(time_str[3:5])
            except Exception:
                continue

            slot_dt = datetime(
                target_date.year, target_date.month, target_date.day, hh, mm,
            )
            if slot_dt <= datetime.now():
                continue

            if theme_name not in theme_cache:
                doc_id = get_or_create_theme(db, cafe_id, theme_name, {
                    "poster_url": None,
                    "is_active":  True,
                })
                theme_cache[theme_name] = doc_id
                print(f"  [UPSERT] 테마: {theme_name}")
            theme_doc_id = theme_cache[theme_name]

            date_themes.setdefault(date_str, {}).setdefault(
                theme_doc_id, {"slots": []}
            )["slots"].append({
                "time":        f"{hh:02d}:{mm:02d}",
                "status":      status,
                "booking_url": BOOKING_URL if status == "available" else None,
            })
            avail_cnt += 1

        print(f"  {date_str}: 가능 {avail_cnt}")

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
    print("더트랩(thetrapsy.co.kr) → DB 동기화")
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
    parser = argparse.ArgumentParser(description="더트랩 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
