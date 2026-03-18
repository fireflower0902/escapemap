"""
단편선 방탈출 테마 + 스케줄 DB 동기화 스크립트.

지점:
  강남점  cafe_id=377197835  https://www.dpsnnn.com/reserve_g
  성수점  cafe_id=259983085  https://dpsnnn-s.imweb.me/reserve_ss

플랫폼: imweb + fo-booking-widget (React)

API:
  1) 세션 획득: GET {reserve_page} → IMWEBVSSID 쿠키
  2) 전체 상품 목록: POST {api_url} (파라미터 없음)
     응답: {"total": [{"idx": N, "name": "테마명 / HH:MM", "thumbnail": "..."}, ...]}
  3) 날짜별 가용성: POST {api_url}
     Body: start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
     응답: {"available": [...], "unavailable": [...], "total": []}

상품명 형식: "{테마명} / {HH:MM}" → split(" / ") 로 파싱

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_dpsnnn_db.py
  uv run python scripts/sync_dpsnnn_db.py --no-schedule
  uv run python scripts/sync_dpsnnn_db.py --days 14
"""

import json
import ssl
import sys
import time
import urllib.request
import urllib.parse
from datetime import date, datetime, time as dtime, timedelta
from http.cookiejar import CookieJar
from pathlib import Path

# SSL 검증 비활성화 (사이트 인증서 문제 우회)
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings
from app.firestore_db import (
    init_firestore, get_db, upsert_cafe,
    get_or_create_theme, upsert_cafe_date_schedules,
    load_cafe_hashes, save_cafe_hashes,
)

REQUEST_DELAY = 1.0

BRANCHES = [
    {
        "cafe_id":      "377197835",
        "branch_name":  "강남점",
        "area":         "gangnam",
        "address":      "서울 강남구 봉은사로4길 36",
        "reserve_page": "https://www.dpsnnn.com/reserve_g",
        "api_url":      "https://www.dpsnnn.com/booking/get_prod_list.cm",
        "booking_url":  "https://www.dpsnnn.com/reserve_g",
    },
    {
        "cafe_id":      "259983085",
        "branch_name":  "성수점",
        "area":         "etc",
        "address":      "서울 성동구 아차산로 122",
        "reserve_page": "https://dpsnnn-s.imweb.me/reserve_ss",
        "api_url":      "https://dpsnnn-s.imweb.me/booking/get_prod_list.cm",
        "booking_url":  "https://dpsnnn-s.imweb.me/reserve_ss",
    },
]


# ── HTTP 유틸 ───────────────────────────────────────────────────────────────────

def _make_opener() -> urllib.request.OpenerDirector:
    """쿠키 핸들러 + SSL 우회가 포함된 opener 생성."""
    cj = CookieJar()
    https_handler = urllib.request.HTTPSHandler(context=_SSL_CTX)
    return urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cj),
        https_handler,
    )


def _get_session(opener, reserve_page: str) -> bool:
    """reserve 페이지 GET → IMWEBVSSID 세션 쿠키 획득."""
    req = urllib.request.Request(
        reserve_page,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    try:
        with opener.open(req, timeout=15) as r:
            r.read()
        print(f"  세션 획득 완료")
        return True
    except Exception as e:
        print(f"  [ERROR] 세션 획득 실패: {e}")
        return False


def _post_api(opener, api_url: str, reserve_page: str, params: dict | None = None) -> dict:
    """get_prod_list.cm 호출."""
    body = urllib.parse.urlencode(params).encode() if params else b""
    req = urllib.request.Request(
        api_url,
        data=body,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": reserve_page,
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    try:
        with opener.open(req, timeout=15) as r:
            raw = r.read().decode("utf-8", errors="ignore")
        return json.loads(raw)
    except Exception as e:
        print(f"  [WARN] API 호출 실패 params={params}: {e}")
        return {}


def _parse_product_name(name: str) -> tuple[str, dtime | None]:
    """
    "상자 / 10:00" → ("상자", time(10, 0))
    파싱 불가 시 → (name, None)
    """
    if " / " in name:
        parts = name.split(" / ", 1)
        theme_name = parts[0].strip()
        time_str = parts[1].strip()
        try:
            hh, mm = map(int, time_str.split(":"))
            return theme_name, dtime(hh, mm)
        except Exception:
            pass
    return name.strip(), None


# ── 전체 상품 목록 파싱 ─────────────────────────────────────────────────────────

def _fetch_all_products(opener, api_url: str, reserve_page: str) -> dict[str, dict]:
    """전체 상품 목록 조회 → 테마별 슬롯 구조 반환."""
    data = _post_api(opener, api_url, reserve_page)
    items = data.get("total", [])
    if not items:
        print("  [WARN] 전체 상품 목록 비어있음")
        return {}

    themes: dict[str, dict] = {}
    for item in items:
        name = item.get("name", "")
        thumbnail = item.get("thumbnail", "")
        theme_name, time_obj = _parse_product_name(name)
        if time_obj is None:
            print(f"  [WARN] 파싱 불가 상품명: {name!r}")
            continue
        if theme_name not in themes:
            themes[theme_name] = {"thumbnail": thumbnail, "times": []}
        if time_obj not in themes[theme_name]["times"]:
            themes[theme_name]["times"].append(time_obj)

    for t_name, info in themes.items():
        info["times"].sort()
        print(f"  테마: {t_name!r} → {len(info['times'])}개 슬롯")

    return themes


# ── 날짜별 가용성 조회 ─────────────────────────────────────────────────────────

def _fetch_availability(opener, api_url: str, reserve_page: str, target_date: date) -> dict[tuple[str, dtime], str]:
    date_str = target_date.strftime("%Y-%m-%d")
    data = _post_api(opener, api_url, reserve_page, {"start_date": date_str, "end_date": date_str})

    result: dict[tuple[str, dtime], str] = {}
    for item in data.get("available", []):
        name = item.get("name", "")
        theme_name, time_obj = _parse_product_name(name)
        if time_obj is not None:
            result[(theme_name, time_obj)] = "available"
    for item in data.get("unavailable", []):
        name = item.get("name", "")
        theme_name, time_obj = _parse_product_name(name)
        if time_obj is not None:
            result[(theme_name, time_obj)] = "full"
    return result


# ── DB 동기화 ───────────────────────────────────────────────────────────────────

def sync_branch(branch: dict, run_schedule: bool = True, days: int = 14):
    """단일 지점 동기화."""
    db = get_db()
    cafe_id = branch["cafe_id"]

    upsert_cafe(db, cafe_id, {
        "name":        "단편선 방탈출",
        "branch_name": branch["branch_name"],
        "address":     branch["address"],
        "area":        branch["area"],
        "website_url": branch["reserve_page"],
        "engine":      "dpsnnn",
        "crawled":     True,
        "is_active":   True,
    })

    opener = _make_opener()
    if not _get_session(opener, branch["reserve_page"]):
        print(f"  세션 획득 실패, {branch['branch_name']} 건너뜀.")
        return
    time.sleep(REQUEST_DELAY)

    themes_info = _fetch_all_products(opener, branch["api_url"], branch["reserve_page"])
    if not themes_info:
        print(f"  상품 목록 없음, {branch['branch_name']} 건너뜀.")
        return
    time.sleep(REQUEST_DELAY)

    cafe_doc = db.collection("cafes").document(cafe_id).get()
    if not cafe_doc.exists:
        print(f"  [ERROR] cafe {cafe_id} Firestore 미존재")
        return

    name_to_doc_id: dict[str, str] = {}
    for theme_name, info in themes_info.items():
        poster_url = info.get("thumbnail") or None
        if poster_url and not poster_url.startswith("http"):
            poster_url = None
        doc_id = get_or_create_theme(db, cafe_id, theme_name, {
            "poster_url": poster_url,
            "is_active":  True,
        })
        name_to_doc_id[theme_name] = doc_id
        print(f"  [UPSERT] 테마: {theme_name}")

    if not run_schedule:
        return

    today = date.today()
    target_dates = [today + timedelta(days=i) for i in range(days + 1)]
    crawled_at = datetime.now()
    date_themes: dict[str, dict] = {}

    for target_date in target_dates:
        avail_map = _fetch_availability(opener, branch["api_url"], branch["reserve_page"], target_date)
        time.sleep(REQUEST_DELAY)
        date_str = target_date.strftime("%Y-%m-%d")

        for theme_name, info in themes_info.items():
            theme_doc_id = name_to_doc_id.get(theme_name)
            if theme_doc_id is None:
                continue
            for time_obj in info["times"]:
                slot_dt = datetime(
                    target_date.year, target_date.month, target_date.day,
                    time_obj.hour, time_obj.minute,
                )
                if slot_dt <= datetime.now():
                    continue
                key = (theme_name, time_obj)
                status = avail_map.get(key, "closed")
                booking_url = branch["booking_url"] if status == "available" else None
                date_themes.setdefault(date_str, {}).setdefault(theme_doc_id, {"slots": []})["slots"].append({
                    "time":        f"{time_obj.hour:02d}:{time_obj.minute:02d}",
                    "status":      status,
                    "booking_url": booking_url,
                })

        avail_cnt = sum(1 for v in avail_map.values() if v == "available")
        full_cnt = sum(1 for v in avail_map.values() if v == "full")
        print(f"  {date_str}: 가능 {avail_cnt}개 / 마감 {full_cnt}개")

    known_hashes = load_cafe_hashes(db, cafe_id)
    new_hashes: dict[str, str] = {}
    for date_str, themes in date_themes.items():
        h = upsert_cafe_date_schedules(
            db, date_str, cafe_id, themes, crawled_at,
            known_hash=known_hashes.get(date_str),
        )
        if h:
            new_hashes[date_str] = h
    if new_hashes:
        today_str = date.today().isoformat()
        save_cafe_hashes(db, cafe_id, {
            k: v for k, v in {**known_hashes, **new_hashes}.items()
            if k >= today_str
        })
    print(f"  스케줄 동기화 완료: {len(new_hashes)}개 날짜 문서 작성")


# ── 메인 ────────────────────────────────────────────────────────────────────────

def main(run_schedule: bool = True, days: int = 14):
    print("=" * 60)
    print("단편선 방탈출 → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)

    for branch in BRANCHES:
        print(f"\n── {branch['branch_name']} ──")
        try:
            sync_branch(branch, run_schedule=run_schedule, days=days)
        except Exception as e:
            print(f"  [ERROR] {branch['branch_name']} 크롤링 실패: {e}")

    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="단편선 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
