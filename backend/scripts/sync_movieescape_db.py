"""
bucheonroute Django 플랫폼 방탈출 카페 통합 동기화 스크립트.

플랫폼: Django 자체 개발 (bucheonroute S3 기반)
공통 URL 구조: {site_url}/theme/{YYYY-MM-DD}/

지원 사이트:
  무비이스케이프 동탄남광장점  http://movieescape.kr       cafe_id=1855837227
  루트이스케이프 수원점         http://route-sw.com         cafe_id=857573680
  루트이스케이프 안산점         http://www.routeescape.co.kr cafe_id=1609773844
  루트이스케이프 평택점         http://routeescape.com       cafe_id=136198096

API:
  GET {site_url}/theme/{YYYY-MM-DD}/
  HTML:
    <a href="/theme/{date}/{theme_name}/{HH:MM}/" class="{themeId}time{N}date_a text-white">
      <button>HH:MM</button>
    </a>
  - 링크가 있으면 예약가능 (마감 슬롯은 HTML에서 미노출)

예약 URL: {site_url}/theme/{date}/{theme_name}/{time}/

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_movieescape_db.py
  uv run python scripts/sync_movieescape_db.py --no-schedule
  uv run python scripts/sync_movieescape_db.py --days 14
"""

import re
import ssl
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import unquote

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from bs4 import BeautifulSoup

from app.config import settings
from app.firestore_db import (
    init_firestore, get_db, upsert_cafe,
    get_or_create_theme, upsert_cafe_date_schedules,
    load_cafe_hashes, save_cafe_hashes,
)

REQUEST_DELAY = 0.8

BRANCHES = [
    {
        "site_url":    "http://movieescape.kr",
        "cafe_name":   "무비이스케이프",
        "cafe_id":     "1855837227",
        "branch_name": "동탄남광장점",
        "address":     "경기 화성시 동탄구 동탄중심상가1길 35",
        "area":        "gyeonggi",
    },
    {
        "site_url":    "http://route-sw.com",
        "cafe_name":   "루트이스케이프",
        "cafe_id":     "857573680",
        "branch_name": "수원점",
        "address":     "경기 수원시 팔달구 향교로 12-1",
        "area":        "gyeonggi",
    },
    {
        "site_url":    "http://www.routeescape.co.kr",
        "cafe_name":   "루트이스케이프",
        "cafe_id":     "1609773844",
        "branch_name": "안산점",
        "address":     "경기 안산시 단원구 고잔1길 40",
        "area":        "gyeonggi",
    },
    {
        "site_url":    "http://routeescape.com",
        "cafe_name":   "루트이스케이프",
        "cafe_id":     "136198096",
        "branch_name": "평택점",
        "address":     "경기 평택시 평택로 41",
        "area":        "gyeonggi",
    },
]

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "ko-KR,ko;q=0.9",
}


def _fetch(site_url: str, target_date: date) -> str:
    date_str = target_date.strftime("%Y-%m-%d")
    url = f"{site_url}/theme/{date_str}/"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=15) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [WARN] GET {url} 실패: {e}")
        return ""


def _parse_page(html: str, site_url: str, target_date: date) -> dict[str, list[dict]]:
    """
    반환: {theme_name: [{"time", "status", "booking_url"}]}
    가용 슬롯만 파싱 (사이트에서 마감 슬롯 미노출)
    """
    soup = BeautifulSoup(html, "html.parser")
    date_str = target_date.strftime("%Y-%m-%d")

    slot_pattern = re.compile(
        r"^/theme/" + re.escape(date_str) + r"/([^/]+)/(\d{2}:\d{2})/$"
    )

    result: dict[str, list[dict]] = {}
    seen: set = set()  # deduplicate (HTML에 중복 섹션 있음)

    for link in soup.find_all("a", href=True):
        href = link["href"]
        m = slot_pattern.match(href)
        if not m:
            continue
        theme_name = unquote(m.group(1))
        time_str = m.group(2)
        key = (theme_name, time_str)
        if key in seen:
            continue
        seen.add(key)

        booking_url = site_url + href
        result.setdefault(theme_name, []).append({
            "time":        time_str,
            "status":      "available",
            "booking_url": booking_url,
        })

    return result


# ── DB 동기화 ─────────────────────────────────────────────────────────────────

def sync_cafe_meta(db, branch: dict) -> None:
    upsert_cafe(db, branch["cafe_id"], {
        "name":        branch["cafe_name"],
        "branch_name": branch["branch_name"],
        "address":     branch["address"],
        "area":        branch["area"],
        "website_url": branch["site_url"],
        "engine":      "bucheonroute",
        "crawled":     True,
        "is_active":   True,
    })
    print(f"  [UPSERT] 카페: {branch['cafe_name']} {branch.get('branch_name','')} (id={branch['cafe_id']})")


def sync_branch(branch: dict, days: int = 14) -> int:
    db = get_db()
    cafe_id = branch["cafe_id"]
    site_url = branch["site_url"]
    today = date.today()
    crawled_at = datetime.now()

    cafe_doc = db.collection("cafes").document(cafe_id).get()
    if not cafe_doc.exists:
        print(f"  [WARN] cafe {cafe_id} Firestore 미존재 — 건너뜀")
        return 0

    theme_cache: dict[str, str] = {}
    date_themes: dict[str, dict] = {}
    writes = 0

    for i in range(days + 1):
        target_date = today + timedelta(days=i)
        date_str = target_date.strftime("%Y-%m-%d")

        html = _fetch(site_url, target_date)
        time.sleep(REQUEST_DELAY)
        if not html:
            continue

        themes_map = _parse_page(html, site_url, target_date)
        avail = 0

        for theme_name, slots in themes_map.items():
            if theme_name not in theme_cache:
                doc_id = get_or_create_theme(db, cafe_id, theme_name, {
                    "poster_url": None,
                    "is_active":  True,
                })
                theme_cache[theme_name] = doc_id
                print(f"  [UPSERT] 테마: {theme_name}")
            theme_doc_id = theme_cache[theme_name]

            for slot in slots:
                try:
                    hh, mm = map(int, slot["time"].split(":"))
                except Exception:
                    continue
                slot_dt = datetime(
                    target_date.year, target_date.month, target_date.day, hh, mm
                )
                if slot_dt <= datetime.now():
                    continue

                date_themes.setdefault(date_str, {}).setdefault(
                    theme_doc_id, {"slots": []}
                )["slots"].append({
                    "time":        f"{hh:02d}:{mm:02d}",
                    "status":      slot["status"],
                    "booking_url": slot["booking_url"],
                })
                avail += 1

        print(f"  {date_str}: 가능 {avail}")

    known_hashes = load_cafe_hashes(db, cafe_id)
    new_hashes: dict[str, str] = {}
    for date_str, themes in date_themes.items():
        h = upsert_cafe_date_schedules(
            db, date_str, cafe_id, themes, crawled_at,
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
    print("bucheonroute 플랫폼 (무비이스케이프/루트이스케이프) → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)
    db = get_db()

    print("\n[ 1단계 ] 카페 메타 동기화")
    for branch in BRANCHES:
        sync_cafe_meta(db, branch)

    if run_schedule:
        for branch in BRANCHES:
            print(f"\n[ 2단계 ] {branch['branch_name']} 스케줄 동기화 (오늘~{days}일 후)")
            sync_branch(branch, days=days)

    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="무비이스케이프 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
