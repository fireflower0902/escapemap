"""
비트포비아(xphobia.net) 테마 + 스케줄 DB 동기화 스크립트.

지점:
  명동점  ji_id=18  place_id=1183396756  area=myeongdong  (서울 중구 명동10길 13)
  대학로점 ji_id=21  place_id=1432484184  area=daehakro   (서울 종로구 대학로10길 12)

API (모두 POST, x-www-form-urlencoded):
  1) GET  https://www.xphobia.net/
     → 세션 쿠키 획득

  2) POST https://www.xphobia.net/reservation/ck_no1.php
     Body: date={yymmdd}&cate=2
     → [{ji_id, ji_name, ji_name2, ...}]  (지점 목록)

  3) POST https://www.xphobia.net/reservation/ck_quest_no1.php
     Body: shop={ji_name}&date={YYYYMMDD}
     → [{ro_id, ro_name, ro_cate, ro_name_vis,
         ro_day1..ro_day50 (평일 시간),
         ro_end1..ro_end50 (주말 시간)}]

  4) POST https://www.xphobia.net/reservation/ck_date_no1.php
     Body: shop={ji_name}&quest={ro_cate}&date={yymmdd}&time={HH:MM}
     → [] → 예약 가능 / [{rel_order_time: ...}] → 예약 불가

  Note: 슬롯별 개별 체크가 필요하므로, 실용적으로 오늘부터 7일치만 per-slot 확인.
        이후 날짜는 template 기반으로 전체 가용으로 처리.

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_xphobia_db.py
  uv run python scripts/sync_xphobia_db.py --no-schedule
  uv run python scripts/sync_xphobia_db.py --days 14
"""

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

BASE_URL = "https://www.xphobia.net"
REQUEST_DELAY = 0.3

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": BASE_URL + "/reservation/reservation_check.php",
}

# ji_name → cafe 정보 매핑
SHOP_MAP: dict[str, dict] = {
    "Phobia 명동": {
        "cafe_id":     "1183396756",
        "cafe_name":   "비트포비아",
        "branch_name": "명동점",
        "address":     "서울 중구 명동10길 13",
        "area":        "myeongdong",
    },
    "Phobia 대학로": {
        "cafe_id":     "1432484184",
        "cafe_name":   "비트포비아",
        "branch_name": "대학로점",
        "address":     "서울 종로구 대학로10길 12",
        "area":        "daehakro",
    },
}

# per-slot 체크는 오늘부터 이 일수까지만 (이후는 template 전체 가용)
PER_SLOT_CHECK_DAYS = 7


# ── HTTP 유틸 ────────────────────────────────────────────────────────────────────

def _make_opener() -> urllib.request.OpenerDirector:
    cj = CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cj),
        urllib.request.HTTPSHandler(context=_SSL_CTX),
    )
    req = urllib.request.Request(BASE_URL + "/", headers={
        "User-Agent": HEADERS["User-Agent"],
        "Accept": "text/html,application/xhtml+xml,*/*",
    })
    try:
        with opener.open(req, timeout=15) as r:
            r.read()
    except Exception as e:
        print(f"  [WARN] 세션 획득 실패: {e}")
    return opener


def _post(opener: urllib.request.OpenerDirector, path: str, params: dict) -> object:
    url = BASE_URL + path
    body = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=body, headers={
        **HEADERS,
        "Content-Type": "application/x-www-form-urlencoded",
    })
    import json
    try:
        with opener.open(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8", errors="ignore"))
    except Exception as e:
        print(f"  [WARN] POST {path} 실패: {e}")
        return []


def _is_weekend(d: date) -> bool:
    return d.weekday() >= 5  # 5=토, 6=일


def _get_template_times(quest: dict, d: date) -> list[str]:
    """ro_day/ro_end 필드에서 시간 슬롯 추출."""
    prefix = "ro_end" if _is_weekend(d) else "ro_day"
    slots = []
    for i in range(1, 51):
        val = quest.get(f"{prefix}{i}", "")
        if not val or val == "00:00:00":
            break
        # 형식: "HH:MM" 또는 "HH:MM:SS" 또는 "HH:MM:SS_Y_Y"
        t = val.split("_")[0].strip()
        if ":" in t:
            parts = t.split(":")
            try:
                hh, mm = int(parts[0]), int(parts[1])
                slots.append(f"{hh:02d}:{mm:02d}")
            except Exception:
                pass
    return slots


def _check_slot(opener: urllib.request.OpenerDirector, shop: str, quest_name: str, target_date: date, time_str: str) -> bool:
    """예약 가능 여부 반환. [] → True (가능), non-empty → False (불가)."""
    date_str = target_date.strftime("%y%m%d")  # 6자리 yymmdd
    data = _post(opener, "/reservation/ck_date_no1.php", {
        "qr_id": "",
        "shop":  shop,
        "quest": quest_name,
        "date":  date_str,
        "time":  time_str,
    })
    return isinstance(data, list) and len(data) == 0


# ── DB 동기화 ────────────────────────────────────────────────────────────────────

def fetch_shops(opener: urllib.request.OpenerDirector) -> list[dict]:
    """활성 지점 목록 반환."""
    today = date.today()
    date_str = today.strftime("%y%m%d")
    data = _post(opener, "/reservation/ck_no1.php", {"date": date_str, "cate": "2"})
    if not isinstance(data, list):
        return []
    return data


def fetch_quests(opener: urllib.request.OpenerDirector, shop_name: str) -> list[dict]:
    """지점별 퀘스트(테마) 목록 반환."""
    today = date.today()
    date_str = today.strftime("%Y%m%d")  # 8자리 YYYYMMDD
    data = _post(opener, "/reservation/ck_quest_no1.php", {
        "shop": shop_name,
        "date": date_str,
    })
    if not isinstance(data, list):
        return []
    return data


def sync_one_shop(
    opener: urllib.request.OpenerDirector,
    shop_name: str,
    quests: list[dict],
    run_schedule: bool,
    days: int,
) -> None:
    shop_info = SHOP_MAP.get(shop_name)
    if not shop_info:
        print(f"  [SKIP] 알 수 없는 지점: {shop_name!r}")
        return

    db = get_db()
    cafe_id = shop_info["cafe_id"]

    # 1. 카페 메타
    upsert_cafe(db, cafe_id, {
        "name":        shop_info["cafe_name"],
        "branch_name": shop_info["branch_name"],
        "address":     shop_info["address"],
        "area":        shop_info["area"],
        "phone":       None,
        "website_url": BASE_URL + "/reservation/reservation_check.php",
        "engine":      "xphobia",
        "crawled":     True,
        "lat":         None,
        "lng":         None,
        "is_active":   True,
    })
    print(f"  [UPSERT] 카페: {shop_info['cafe_name']} {shop_info['branch_name']} (id={cafe_id})")

    if not quests:
        print("  퀘스트 없음, 건너뜀.")
        return

    # 2. 테마 upsert
    cafe_doc = db.collection("cafes").document(cafe_id).get()
    if not cafe_doc.exists:
        print(f"  [ERROR] cafe {cafe_id} Firestore 미존재")
        return

    name_to_doc: dict[str, str] = {}
    for q in quests:
        theme_name = q.get("ro_name_vis") or q.get("ro_name", "")
        if not theme_name:
            continue
        doc_id = get_or_create_theme(db, cafe_id, theme_name, {
            "difficulty":   None,
            "duration_min": None,
            "poster_url":   None,
            "is_active":    True,
        })
        name_to_doc[q.get("ro_cate", q.get("ro_name", ""))] = doc_id
        print(f"  [UPSERT] 테마: {theme_name} (doc={doc_id})")

    if not run_schedule:
        return

    # 3. 스케줄 upsert
    today = date.today()
    target_dates = [today + timedelta(days=i) for i in range(days + 1)]
    crawled_at = datetime.now()
    writes = 0
    known_hashes = load_cafe_hashes(db, cafe_id)
    new_hashes: dict[str, str] = {}

    for target_date in target_dates:
        date_str = target_date.strftime("%Y-%m-%d")
        themes_data: dict[str, dict] = {}
        avail = full = 0
        do_per_slot = (target_date - today).days < PER_SLOT_CHECK_DAYS

        for q in quests:
            ro_cate = q.get("ro_cate", q.get("ro_name", ""))
            doc_id = name_to_doc.get(ro_cate)
            if not doc_id:
                continue

            times = _get_template_times(q, target_date)
            for time_str in times:
                try:
                    hh, mm = map(int, time_str.split(":"))
                    slot_dt = datetime(target_date.year, target_date.month, target_date.day, hh, mm)
                except Exception:
                    continue
                if slot_dt <= datetime.now():
                    continue

                if do_per_slot:
                    is_avail = _check_slot(opener, shop_name, ro_cate, target_date, time_str)
                    time.sleep(REQUEST_DELAY)
                else:
                    is_avail = True  # 원거리 날짜는 전체 가용으로 처리

                status = "available" if is_avail else "full"
                booking_url = BASE_URL + "/reservation/reservation_check.php" if is_avail else None

                themes_data.setdefault(doc_id, {"slots": []})["slots"].append({
                    "time":        time_str,
                    "status":      status,
                    "booking_url": booking_url,
                })
                if is_avail:
                    avail += 1
                else:
                    full += 1

        if themes_data:
            h = upsert_cafe_date_schedules(
                db, date_str, cafe_id, themes_data, crawled_at,
                known_hash=known_hashes.get(date_str),
            )
            if h:
                new_hashes[date_str] = h
                writes += 1

        if themes_data:
            print(f"  {date_str}: 가능 {avail}개 / 마감 {full}개")
        else:
            print(f"  {date_str}: 미오픈")

    if new_hashes:
        today_str = today.isoformat()
        save_cafe_hashes(db, cafe_id, {
            k: v for k, v in {**known_hashes, **new_hashes}.items()
            if k >= today_str
        })

    print(f"  스케줄 동기화: {writes}개 날짜 작성")


# ── 메인 ─────────────────────────────────────────────────────────────────────────

def main(run_schedule: bool = True, days: int = 14) -> None:
    print("=" * 60)
    print("비트포비아(xphobia.net) → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)

    opener = _make_opener()
    time.sleep(REQUEST_DELAY)

    # 지점 목록
    shops = fetch_shops(opener)
    time.sleep(REQUEST_DELAY)
    if not shops:
        print("  [ERROR] 지점 목록 조회 실패")
        return

    print(f"  지점 {len(shops)}개 발견")

    for shop in shops:
        shop_name = shop.get("ji_name", "")
        if shop_name not in SHOP_MAP:
            print(f"  [SKIP] 서울 외 지점: {shop_name!r}")
            continue

        print(f"\n{'=' * 50}")
        print(f"[ {shop_name} ]")
        print(f"{'=' * 50}")

        quests = fetch_quests(opener, shop_name)
        time.sleep(REQUEST_DELAY)
        print(f"  퀘스트 {len(quests)}개")

        sync_one_shop(opener, shop_name, quests, run_schedule, days)

    print("\n" + "=" * 60)
    print("비트포비아 동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="비트포비아(xphobia.net) DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
