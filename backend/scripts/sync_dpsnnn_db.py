"""
단편선 방탈출 강남점 테마 + 스케줄 DB 동기화 스크립트.

사이트: https://www.dpsnnn.com/
예약 페이지: https://www.dpsnnn.com/reserve_g (강남점)
플랫폼: imweb + fo-booking-widget (React)

API:
  1) 세션 획득: GET https://www.dpsnnn.com/reserve_g → IMWEBVSSID 쿠키
  2) 전체 상품 목록: POST https://www.dpsnnn.com/booking/get_prod_list.cm (파라미터 없음)
     응답: {"total": [{"idx": N, "name": "테마명 / HH:MM", "thumbnail": "..."}, ...]}
  3) 날짜별 가용성: POST https://www.dpsnnn.com/booking/get_prod_list.cm
     Body: start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
     응답: {"available": [...], "unavailable": [...], "total": []}

상품명 형식: "{테마명} / {HH:MM}" → split(" / ") 로 파싱

강남점 cafe_id: 377197835

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
from app.firestore_db import init_firestore, get_db, get_or_create_theme, upsert_cafe_date_schedules

CAFE_ID = "377197835"
RESERVE_PAGE = "https://www.dpsnnn.com/reserve_g"
API_URL = "https://www.dpsnnn.com/booking/get_prod_list.cm"
BOOKING_URL = "https://www.dpsnnn.com/reserve_g"
REQUEST_DELAY = 1.0


# ── HTTP 유틸 ───────────────────────────────────────────────────────────────────

def _make_opener() -> urllib.request.OpenerDirector:
    """쿠키 핸들러 + SSL 우회가 포함된 opener 생성."""
    cj = CookieJar()
    https_handler = urllib.request.HTTPSHandler(context=_SSL_CTX)
    return urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cj),
        https_handler,
    )


def _get_session(opener: urllib.request.OpenerDirector) -> bool:
    """reserve_g 페이지 GET → IMWEBVSSID 세션 쿠키 획득."""
    req = urllib.request.Request(
        RESERVE_PAGE,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    try:
        with opener.open(req, timeout=15) as r:
            r.read()
        print(f"  세션 획득 완료 (status={r.status})")
        return True
    except Exception as e:
        print(f"  [ERROR] 세션 획득 실패: {e}")
        return False


def _post_api(opener: urllib.request.OpenerDirector, params: dict | None = None) -> dict:
    """get_prod_list.cm 호출. params=None이면 전체 목록, 날짜 지정 시 가용성 반환."""
    body = urllib.parse.urlencode(params).encode() if params else b""
    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": RESERVE_PAGE,
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
        time_str = parts[1].strip()  # "HH:MM"
        try:
            hh, mm = map(int, time_str.split(":"))
            return theme_name, dtime(hh, mm)
        except Exception:
            pass
    return name.strip(), None


# ── 전체 상품 목록 파싱 ─────────────────────────────────────────────────────────

def _fetch_all_products(opener: urllib.request.OpenerDirector) -> dict[str, dict]:
    """
    전체 상품 목록 조회 → 테마별 슬롯 구조 반환.
    반환: {테마명: {"thumbnail": str, "times": [time, ...]}}
    """
    data = _post_api(opener)
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
        print(f"  테마: {t_name!r} → {len(info['times'])}개 슬롯 {[str(t) for t in info['times']]}")

    return themes


# ── 날짜별 가용성 조회 ─────────────────────────────────────────────────────────

def _fetch_availability(opener: urllib.request.OpenerDirector, target_date: date) -> dict[tuple[str, dtime], str]:
    """
    날짜별 가용성 조회.
    반환: {(테마명, time): "available" | "full"}
    """
    date_str = target_date.strftime("%Y-%m-%d")
    data = _post_api(opener, {"start_date": date_str, "end_date": date_str})

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

def sync_themes(themes_info: dict[str, dict]) -> dict[str, str]:
    """
    단편선 테마를 Firestore에 upsert.
    반환: {테마명 → theme_doc_id}
    """
    db = get_db()
    cafe_doc = db.collection("cafes").document(CAFE_ID).get()
    if not cafe_doc.exists:
        print(f"  [ERROR] cafe {CAFE_ID} Firestore 미존재 — 스크립트를 중단합니다.")
        return {}

    name_to_doc_id: dict[str, str] = {}

    for theme_name, info in themes_info.items():
        poster_url = info.get("thumbnail") or None
        if poster_url and not poster_url.startswith("http"):
            poster_url = None  # 상대 경로 무시

        theme_doc_id = get_or_create_theme(db, CAFE_ID, theme_name, {
            "difficulty": None,
            "duration_min": None,
            "poster_url": poster_url,
            "is_active": True,
        })
        name_to_doc_id[theme_name] = theme_doc_id
        print(f"  [UPSERT] {theme_name} (doc_id={theme_doc_id})")

    print(f"\n  테마 동기화 완료: {len(name_to_doc_id)}개")
    return name_to_doc_id


def sync_schedules(
    opener: urllib.request.OpenerDirector,
    themes_info: dict[str, dict],
    name_to_doc_id: dict[str, str],
    days: int = 14,
):
    """단편선 스케줄을 Firestore에 upsert (오늘~days일 후)."""
    db = get_db()
    today = date.today()
    target_dates = [today + timedelta(days=i) for i in range(days + 1)]
    crawled_at = datetime.now()
    writes = 0

    # {date_str: {theme_doc_id: {"slots": [...]}}}
    date_themes: dict[str, dict] = {}

    for target_date in target_dates:
        avail_map = _fetch_availability(opener, target_date)
        time.sleep(REQUEST_DELAY)

        date_str = target_date.strftime("%Y-%m-%d")

        for theme_name, info in themes_info.items():
            theme_doc_id = name_to_doc_id.get(theme_name)
            if theme_doc_id is None:
                continue

            for time_obj in info["times"]:
                # 과거 시간 건너뜀
                slot_dt = datetime(
                    target_date.year, target_date.month, target_date.day,
                    time_obj.hour, time_obj.minute,
                )
                if slot_dt <= datetime.now():
                    continue

                key = (theme_name, time_obj)
                if key in avail_map:
                    status = avail_map[key]
                else:
                    # 가용성 응답에 없으면 아직 오픈 안 됨 → closed
                    status = "closed"

                booking_url = BOOKING_URL if status == "available" else None

                date_themes.setdefault(date_str, {}).setdefault(theme_doc_id, {"slots": []})["slots"].append({
                    "time": f"{time_obj.hour:02d}:{time_obj.minute:02d}",
                    "status": status,
                    "booking_url": booking_url,
                })

        avail_cnt = sum(1 for v in avail_map.values() if v == "available")
        full_cnt = sum(1 for v in avail_map.values() if v == "full")
        print(f"  {date_str}: 가능 {avail_cnt}개 / 마감 {full_cnt}개")

    for date_str, themes in date_themes.items():
        upsert_cafe_date_schedules(db, date_str, CAFE_ID, themes, crawled_at)
        writes += 1

    print(f"\n  스케줄 동기화 완료: {writes}개 날짜 문서 작성")


# ── 메인 ────────────────────────────────────────────────────────────────────────

def main(run_schedule: bool = True, days: int = 14):
    print("=" * 60)
    print("단편선 방탈출 강남점 → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)

    opener = _make_opener()

    print("\n[ 0단계 ] 세션 획득")
    if not _get_session(opener):
        print("세션 획득 실패, 종료.")
        return
    time.sleep(REQUEST_DELAY)

    print("\n[ 1단계 ] 전체 상품 목록 조회")
    themes_info = _fetch_all_products(opener)
    if not themes_info:
        print("상품 목록 없음, 종료.")
        return
    time.sleep(REQUEST_DELAY)

    print("\n[ 2단계 ] 테마 DB 동기화")
    name_to_doc_id = sync_themes(themes_info)
    if not name_to_doc_id:
        print("테마 동기화 실패, 종료.")
        return

    if run_schedule:
        print(f"\n[ 3단계 ] 스케줄 동기화 (오늘~{days}일 후)")
        sync_schedules(opener, themes_info, name_to_doc_id, days=days)

    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="단편선 강남점 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
