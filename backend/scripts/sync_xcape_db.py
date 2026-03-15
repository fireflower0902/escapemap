"""
엑스케이프(xcape.co.kr) 테마 + 스케줄 DB 동기화 스크립트.

사이트: https://xcape.co.kr
API: https://api.xcape-apps.com (인증 불필요)

엔드포인트:
  GET /merchants → 전체 지점 목록
  GET /reservations?merchantId={id}&date={YYYY-MM-DD}
    → [{themeId, themeNameKo, runningTime, difficulty, mainImagePath,
         reservationList: [{id, time(HH:MM:SS), isReserved, date}, ...]}]
  isReserved=false → 예약 가능, true → 예약됨(마감)

지점 (merchant_id → 카카오 place_id):
  1: 강남점    (서울 강남구 봉은사로2길 16, 현도빌딩 B1)  → 1551717206
  2: 건대점    (서울 광진구 동일로 112, 금아빌딩 B1)     → 27354377
  3: 건대2호   엑스크라임 (서울 광진구 아차산로29길 38)  → 361428621
  5: 건대3호   (서울 광진구 아차산로 191, 동신빌딩 B1)   → 카카오 미발견, 추후 추가
  4: 수원점    (경기 수원시 팔달구 효원로265번길 40 4층)  → 1599918263

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_xcape_db.py
  uv run python scripts/sync_xcape_db.py --no-schedule
  uv run python scripts/sync_xcape_db.py --days 6
"""

import json
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

API_BASE = "https://api.xcape-apps.com"
SITE_URL = "https://xcape.co.kr"
REQUEST_DELAY = 0.5

# merchant_id → 카카오 place_id (cafe.id)
# 미발견 지점은 주석 처리
MERCHANT_MAP: dict[int, str] = {
    1: "1551717206",  # 강남점 (강남구 봉은사로2길 16)
    2: "27354377",    # 건대점 (광진구 동일로 112 지하1층)
    3: "361428621",   # 건대2호 엑스크라임 (광진구 화양동 9-47 지하1층)
    4: "1599918263",  # 수원점 (경기 수원시 팔달구 효원로265번길 40 4층)
    # 5: "???",       # 건대3호 (광진구 아차산로 191 동신빌딩) — 카카오 미발견
}

# 지점 메타 (API에서도 가져올 수 있으나, area 코드 결정을 위해 사전 정의)
MERCHANT_META: dict[int, dict] = {
    1: {"area": "gangnam"},
    2: {"area": "konkuk"},
    3: {"area": "konkuk"},
    4: {"area": "gyeonggi"},
}

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
    "Origin": SITE_URL,
    "Referer": SITE_URL + "/",
}


# ── API 호출 ──────────────────────────────────────────────────────────────────

def _api_get(path: str, params: dict | None = None) -> dict:
    url = API_BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  [WARN] GET {path} 실패: {e}")
        return {}


def fetch_merchants() -> dict[int, dict]:
    """전체 지점 목록을 가져옵니다. 반환: {merchant_id → shop_info}"""
    data = _api_get("/merchants")
    result = {}
    for shop in data.get("result", []):
        mid = shop.get("id")
        if mid:
            result[mid] = shop
    return result


def fetch_reservations(merchant_id: int, target_date: date) -> list[dict]:
    """날짜별 예약 현황 (테마 + 슬롯) 조회."""
    date_str = target_date.strftime("%Y-%m-%d")
    data = _api_get("/reservations", {"merchantId": merchant_id, "date": date_str})
    return data.get("result", [])


# ── DB 동기화 ─────────────────────────────────────────────────────────────────

def sync_cafe_metas(merchants: dict[int, dict]) -> None:
    """카페 메타데이터를 Firestore에 upsert합니다."""
    db = get_db()
    for mid, cafe_id in MERCHANT_MAP.items():
        shop = merchants.get(mid, {})
        if not shop:
            continue
        area = MERCHANT_META.get(mid, {}).get("area", "etc")
        name_full = shop.get("name", "")
        # "넥스트에디션 건대점" → name + branch_name 분리 유사 처리
        if " " in name_full:
            parts = name_full.rsplit(" ", 1)
            if any(parts[-1].endswith(s) for s in ("점", "호", "관")):
                name = parts[0]
                branch_name = parts[1]
            else:
                name = name_full
                branch_name = None
        else:
            name = name_full
            branch_name = None

        upsert_cafe(db, cafe_id, {
            "name":        name,
            "branch_name": branch_name,
            "address":     shop.get("address", ""),
            "area":        area,
            "phone":       shop.get("telNumber"),
            "website_url": SITE_URL,
            "engine":      "xcape",
            "crawled":     True,
            "lat":         None,
            "lng":         None,
            "is_active":   True,
        })
        print(f"  [UPSERT] 카페: {name_full} (id={cafe_id})")


def sync_themes_for_merchant(
    merchant_id: int,
    cafe_id: str,
    themes_data: list[dict],
) -> dict[int, str]:
    """
    테마를 Firestore에 upsert합니다.
    반환: {api_theme_id → theme_doc_id}
    """
    db = get_db()
    cafe_doc = db.collection("cafes").document(cafe_id).get()
    if not cafe_doc.exists:
        print(f"  [ERROR] cafe {cafe_id} 미존재")
        return {}

    tid_to_doc: dict[int, str] = {}
    for t in themes_data:
        api_id = t["themeId"]
        name = t.get("themeNameKo") or t.get("themeNameEn") or f"Theme{api_id}"
        duration = t.get("runningTime")
        difficulty = t.get("difficulty")
        poster_url = t.get("mainImagePath") or None

        doc_id = get_or_create_theme(db, cafe_id, name, {
            "difficulty":   difficulty,
            "duration_min": duration,
            "poster_url":   poster_url,
            "is_active":    True,
        })
        tid_to_doc[api_id] = doc_id
        print(f"  [UPSERT] 테마: {name} (merchant={merchant_id})")

    return tid_to_doc


def sync_schedules(days: int = 6) -> None:
    """엑스케이프 스케줄을 Firestore에 upsert (오늘~days일 후)."""
    db = get_db()
    today = date.today()
    target_dates = [today + timedelta(days=i) for i in range(days + 1)]
    crawled_at = datetime.now()
    total_writes = 0

    for merchant_id, cafe_id in MERCHANT_MAP.items():
        print(f"\n  merchant_id={merchant_id} ({cafe_id})")

        # 테마 + 슬롯 모두 첫 날짜로 수집 (테마 목록이 날짜마다 같음)
        cafe_doc = db.collection("cafes").document(cafe_id).get()
        if not cafe_doc.exists:
            print(f"  [WARN] cafe {cafe_id} Firestore 미존재 — 건너뜀")
            continue

        # {date_str: {theme_doc_id: {"slots": [...]}}}
        date_themes: dict[str, dict] = {}

        # theme_doc_id 캐시
        tid_to_doc: dict[int, str] = {}
        themes_loaded = False

        for target_date in target_dates:
            date_str = target_date.strftime("%Y-%m-%d")
            res_data = fetch_reservations(merchant_id, target_date)
            time.sleep(REQUEST_DELAY)

            if not res_data:
                continue

            # 최초 1회만 테마 upsert
            if not themes_loaded:
                tid_to_doc = sync_themes_for_merchant(merchant_id, cafe_id, res_data)
                themes_loaded = True

            avail_cnt = full_cnt = 0

            for theme in res_data:
                api_id = theme["themeId"]
                theme_doc_id = tid_to_doc.get(api_id)
                if theme_doc_id is None:
                    continue

                for slot in theme.get("reservationList", []):
                    if slot.get("date") != date_str:
                        continue

                    time_str = slot.get("time", "")  # "HH:MM:SS" 형식
                    if not time_str or ":" not in time_str:
                        continue

                    try:
                        hh, mm = int(time_str[:2]), int(time_str[3:5])
                        time_obj = dtime(hh, mm)
                    except Exception:
                        continue

                    # 과거 슬롯 건너뜀
                    slot_dt = datetime(
                        target_date.year, target_date.month, target_date.day,
                        hh, mm,
                    )
                    if slot_dt <= datetime.now():
                        continue

                    is_reserved = slot.get("isReserved", True)
                    status = "full" if is_reserved else "available"
                    booking_url = SITE_URL if status == "available" else None

                    date_themes.setdefault(date_str, {}).setdefault(theme_doc_id, {"slots": []})["slots"].append({
                        "time":        f"{hh:02d}:{mm:02d}",
                        "status":      status,
                        "booking_url": booking_url,
                    })

                    if status == "available":
                        avail_cnt += 1
                    else:
                        full_cnt += 1

            print(f"    {date_str}: 가능 {avail_cnt} / 마감 {full_cnt}")

        known_hashes = load_cafe_hashes(db, cafe_id)
        new_hashes: dict[str, str] = {}
        for date_str, themes in date_themes.items():
            h = upsert_cafe_date_schedules(
                db, date_str, cafe_id, themes, crawled_at,
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
    print("엑스케이프(xcape.co.kr) → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)
    db = get_db()

    print("\n[ 1단계 ] 지점 목록 조회")
    merchants = fetch_merchants()
    print(f"  전체 지점: {len(merchants)}개")
    for mid, shop in merchants.items():
        if mid in MERCHANT_MAP:
            print(f"  [대상] id={mid} {shop.get('name')} — {shop.get('address')}")

    print("\n[ 2단계 ] 카페 메타 동기화")
    sync_cafe_metas(merchants)

    if run_schedule:
        print(f"\n[ 3단계 ] 스케줄 동기화 (오늘~{days}일 후)")
        sync_schedules(days=days)

    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="엑스케이프 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=6, help="오늘부터 며칠치 수집 (기본 6)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
