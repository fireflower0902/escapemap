"""
이스케이퍼스(escapers.co.kr) 테마 + 스케줄 DB 동기화 스크립트.

사이트: http://www.escapers.co.kr
예약 시스템: 자체 Laravel 기반

API 흐름:
  1) GET http://www.escapers.co.kr/reservation/{groupPK}
     → <meta name="csrf-token" content="..."> 에서 CSRF 토큰 추출
  2) POST http://www.escapers.co.kr/reservation/theme
     Headers: X-CSRF-TOKEN, X-Requested-With: XMLHttpRequest
     Body: reservationDate=YYYY-MM-DD&groupPK={N}&groupPhone={phone}
     응답: {
       "data": [{PK, thumb, title}, ...],
       "times": {"themePK": [{themePK, time: "HH:MM:SS", reservation: bool}, ...]},
       "pricing": {...}
     }
  - reservation: true → full, false → available
  - 포스터: http://www.escapers.co.kr/storage/{thumb}

지점:
  groupPK=1: 홍대1호점 (서울 마포구 연희로1길 7 2층) → cafe_id=969459474
  groupPK=4: 대전점 — 네이버 예약만 → 제외

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_escapers_db.py
  uv run python scripts/sync_escapers_db.py --no-schedule
  uv run python scripts/sync_escapers_db.py --days 14
"""

import json
import re
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

from app.config import settings
from app.firestore_db import (
    init_firestore, get_db, upsert_cafe,
    get_or_create_theme, upsert_cafe_date_schedules,
    load_cafe_hashes, save_cafe_hashes,
)

SITE_URL = "http://www.escapers.co.kr"
THEME_API_URL = SITE_URL + "/reservation/theme"
STORAGE_URL = SITE_URL + "/storage/"
REQUEST_DELAY = 1.0

BRANCHES = [
    {
        "cafe_id":     "969459474",
        "branch_name": "홍대1호점",
        "group_pk":    1,
        "group_phone": "010-5594-5216",
        "area":        "hongdae",
        "address":     "서울 마포구 연희로1길 7",
    },
]

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

_HEADERS_BASE = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
}


def _make_opener() -> urllib.request.OpenerDirector:
    cj = CookieJar()
    https_handler = urllib.request.HTTPSHandler(context=_SSL_CTX)
    return urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cj),
        https_handler,
    )


def _get_csrf_token(opener: urllib.request.OpenerDirector, group_pk: int) -> str | None:
    """예약 페이지 GET → 세션 쿠키 획득 + CSRF 토큰 추출."""
    url = f"{SITE_URL}/reservation/{group_pk}"
    req = urllib.request.Request(url, headers={
        **_HEADERS_BASE,
        "Accept": "text/html,application/xhtml+xml",
    })
    try:
        with opener.open(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [ERROR] GET {url} 실패: {e}")
        return None

    m = re.search(r'<meta[^>]+name="csrf-token"[^>]+content="([^"]+)"', html)
    if m:
        return m.group(1)
    print(f"  [ERROR] CSRF 토큰 미발견 (groupPK={group_pk})")
    return None


def _fetch_theme_times(
    opener: urllib.request.OpenerDirector,
    group_pk: int, group_phone: str, csrf_token: str, target_date: date,
) -> dict:
    """날짜별 테마/슬롯 조회."""
    date_str = target_date.strftime("%Y-%m-%d")
    body = urllib.parse.urlencode({
        "reservationDate": date_str,
        "groupPK": str(group_pk),
        "groupPhone": group_phone,
    }).encode()
    req = urllib.request.Request(THEME_API_URL, data=body, headers={
        **_HEADERS_BASE,
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRF-TOKEN": csrf_token,
        "Referer": f"{SITE_URL}/reservation/{group_pk}",
        "Accept": "application/json, text/javascript, */*; q=0.01",
    })
    try:
        with opener.open(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        return json.loads(raw)
    except Exception as e:
        print(f"  [WARN] POST /reservation/theme 실패 (date={date_str}): {e}")
        return {}


# ── DB 동기화 ─────────────────────────────────────────────────────────────────

def sync_cafe_meta(db, branch: dict) -> None:
    upsert_cafe(db, branch["cafe_id"], {
        "name":        "이스케이퍼스",
        "branch_name": branch["branch_name"],
        "address":     branch["address"],
        "area":        branch["area"],
        "website_url": SITE_URL,
        "engine":      "escapers",
        "crawled":     True,
        "is_active":   True,
    })
    print(f"  [UPSERT] 카페: 이스케이퍼스 {branch['branch_name']} (id={branch['cafe_id']})")


def sync_schedules(days: int = 14) -> None:
    db = get_db()
    today = date.today()
    target_dates = [today + timedelta(days=i) for i in range(days + 1)]
    crawled_at = datetime.now()
    total_writes = 0

    for branch in BRANCHES:
        cafe_id = branch["cafe_id"]
        group_pk = branch["group_pk"]
        group_phone = branch["group_phone"]
        print(f"\n  {branch['branch_name']} (groupPK={group_pk}, id={cafe_id})")

        cafe_doc = db.collection("cafes").document(cafe_id).get()
        if not cafe_doc.exists:
            print(f"  [WARN] cafe {cafe_id} Firestore 미존재 — 건너뜀")
            continue

        opener = _make_opener()
        csrf_token = _get_csrf_token(opener, group_pk)
        if not csrf_token:
            print(f"  [ERROR] CSRF 토큰 획득 실패 — 건너뜀")
            continue
        time.sleep(REQUEST_DELAY)

        # themePK → theme_doc_id 캐시 (첫 번째 유효 응답에서 구축)
        theme_cache: dict[int, str] = {}  # themePK (int) → doc_id
        theme_name_cache: dict[int, str] = {}  # themePK → name
        theme_thumb_cache: dict[int, str] = {}  # themePK → poster_url
        date_themes: dict[str, dict] = {}
        booking_url = f"{SITE_URL}/reservation/{group_pk}"

        for target_date in target_dates:
            date_str = target_date.strftime("%Y-%m-%d")
            data = _fetch_theme_times(opener, group_pk, group_phone, csrf_token, target_date)
            time.sleep(REQUEST_DELAY)

            times_map = data.get("times", {})
            theme_data = data.get("data", [])
            if not times_map:
                continue

            # 처음 데이터 들어올 때 테마 메타 구성
            if not theme_name_cache and theme_data:
                for t in theme_data:
                    pk = t.get("PK")
                    title = t.get("title", "").strip()
                    thumb = t.get("thumb", "")
                    if pk and title:
                        theme_name_cache[pk] = title
                        if thumb:
                            theme_thumb_cache[pk] = STORAGE_URL + thumb

            avail_cnt = full_cnt = 0

            for theme_pk_str, slots in times_map.items():
                theme_pk = int(theme_pk_str)
                name = theme_name_cache.get(theme_pk)
                if not name:
                    # 이름 없는 경우 skip
                    continue

                if theme_pk not in theme_cache:
                    poster_url = theme_thumb_cache.get(theme_pk)
                    doc_id = get_or_create_theme(db, cafe_id, name, {
                        "poster_url": poster_url,
                        "is_active":  True,
                    })
                    theme_cache[theme_pk] = doc_id
                    print(f"  [UPSERT] 테마: {name} (PK={theme_pk})")
                theme_doc_id = theme_cache[theme_pk]

                for slot in slots:
                    time_str = slot.get("time", "")  # "HH:MM:SS"
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

                    reserved = slot.get("reservation", False)
                    status = "full" if reserved else "available"

                    date_themes.setdefault(date_str, {}).setdefault(
                        theme_doc_id, {"slots": []}
                    )["slots"].append({
                        "time":        f"{hh:02d}:{mm:02d}",
                        "status":      status,
                        "booking_url": booking_url if status == "available" else None,
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

def main(run_schedule: bool = True, days: int = 14):
    print("=" * 60)
    print("이스케이퍼스(escapers.co.kr) → DB 동기화")
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
    parser = argparse.ArgumentParser(description="이스케이퍼스 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
