"""
제로월드 (zerohongdae.com / zerogangnam.com / zerolotteworld.com) 테마 + 스케줄 DB 동기화.

지점:
  1. 홍대점   https://www.zerohongdae.com  place_id=1732671994  area=hongdae
  2. 강남점   https://zerogangnam.com      place_id=1345840219  area=gangnam
  3. 롯데월드점 https://zerolotteworld.com  place_id=890251040   area=jamsil

플랫폼: Laravel (CSRF 기반 자체 예약 시스템)

API:
  1) 세션 획득:
     GET {base_url}/reservation
     → XSRF-TOKEN 쿠키 + <meta name="csrf-token" content="..."> 추출

  2) 테마 + 슬롯 조회:
     POST {base_url}/reservation/theme
     Form: reservationDate=YYYY-MM-DD
     헤더: X-CSRF-TOKEN, X-Requested-With: XMLHttpRequest
     응답 JSON:
       data  → [{PK, title, thumb, ...}]  (테마 목록)
       times → {theme_pk: [{themePK, time: "HH:MM:SS", reservation: bool}]}
         reservation=False → available
         reservation=True  → full

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_zeroworld_db.py
  uv run python scripts/sync_zeroworld_db.py --no-schedule
  uv run python scripts/sync_zeroworld_db.py --days 14
"""

import re
import ssl
import sys
import time
import json
import urllib.request
import urllib.parse
from datetime import date, datetime, time as dtime, timedelta
from http.cookiejar import CookieJar
from pathlib import Path

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
        "cafe_id":     "1732671994",
        "cafe_name":   "제로월드",
        "branch_name": "홍대점",
        "address":     "서울 마포구 동교동 203-13 5층",
        "area":        "hongdae",
        "base_url":    "https://www.zerohongdae.com",
    },
    {
        "cafe_id":     "1345840219",
        "cafe_name":   "제로월드",
        "branch_name": "강남점",
        "address":     "서울 서초구 서초동 1308 강남오피스텔 지하1층",
        "area":        "gangnam",
        "base_url":    "https://zerogangnam.com",
    },
    {
        "cafe_id":     "890251040",
        "cafe_name":   "제로월드",
        "branch_name": "롯데월드점",
        "address":     "서울 송파구 잠실동 40-1 3층",
        "area":        "jamsil",
        "base_url":    "https://zerolotteworld.com",
    },
]

HEADERS_BASE = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
}


# ── 세션/CSRF ─────────────────────────────────────────────────────────────────

def _make_opener():
    jar = CookieJar()
    return urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=_SSL_CTX),
        urllib.request.HTTPCookieProcessor(jar),
    )


def _get_csrf(opener, base_url: str) -> str:
    """예약 페이지 GET → CSRF 토큰 반환."""
    req = urllib.request.Request(f"{base_url}/reservation", headers={
        **HEADERS_BASE,
        "Accept": "text/html,application/xhtml+xml",
    })
    try:
        with opener.open(req, timeout=15) as r:
            html = r.read().decode("utf-8", errors="ignore")
        m = re.search(
            r'<meta[^>]*name=["\']csrf-token["\'][^>]*content=["\']([^"\']+)["\']',
            html, re.IGNORECASE,
        )
        return m.group(1) if m else ""
    except Exception as e:
        print(f"  [WARN] CSRF 획득 실패 {base_url}: {e}")
        return ""


# ── API 호출 ──────────────────────────────────────────────────────────────────

def _fetch_day(opener, base_url: str, csrf: str, target_date: date) -> dict | None:
    """
    POST /reservation/theme → 테마 + 슬롯 반환.
    {data: [{PK, title}], times: {pk: [{themePK, time, reservation}]}}
    """
    date_str = target_date.strftime("%Y-%m-%d")
    body = urllib.parse.urlencode({"reservationDate": date_str}).encode()
    req = urllib.request.Request(f"{base_url}/reservation/theme", data=body, headers={
        **HEADERS_BASE,
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": f"{base_url}/reservation",
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-CSRF-TOKEN": csrf,
    })
    try:
        with opener.open(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8", errors="ignore"))
    except Exception as e:
        print(f"  [WARN] 슬롯 조회 실패 {base_url} {date_str}: {e}")
        return None


# ── DB 동기화 ─────────────────────────────────────────────────────────────────

def sync_cafe_meta(branch: dict) -> None:
    db = get_db()
    upsert_cafe(db, branch["cafe_id"], {
        "name":        branch["cafe_name"],
        "branch_name": branch["branch_name"],
        "address":     branch["address"],
        "area":        branch["area"],
        "phone":       None,
        "website_url": branch["base_url"] + "/",
        "engine":      "zeroworld",
        "crawled":     True,
        "lat":         None,
        "lng":         None,
        "is_active":   True,
    })
    print(f"  [UPSERT] 카페: {branch['cafe_name']} {branch['branch_name']} (id={branch['cafe_id']})")


def sync_themes(branch: dict, theme_data: list[dict]) -> dict[int, str]:
    """테마를 Firestore에 upsert. 반환: {theme_pk → theme_doc_id}"""
    db = get_db()
    cafe_id = branch["cafe_id"]
    cafe_doc = db.collection("cafes").document(cafe_id).get()
    if not cafe_doc.exists:
        print(f"  [ERROR] cafe {cafe_id} Firestore 미존재")
        return {}

    pk_to_doc: dict[int, str] = {}
    for t in theme_data:
        name = t["title"].strip()
        # "[홍대] ALIVE" → "ALIVE" 정제
        name = re.sub(r"^\[\S+\]\s*", "", name).strip() or name
        doc_id = get_or_create_theme(db, cafe_id, name, {
            "difficulty":   None,
            "duration_min": None,
            "poster_url":   f"{branch['base_url']}/storage/{t.get('thumb','')}" if t.get("thumb") else None,
            "is_active":    True,
        })
        pk_to_doc[t["PK"]] = doc_id
        print(f"  [UPSERT] 테마: {name} (PK={t['PK']}, doc={doc_id})")

    return pk_to_doc


def sync_schedules(
    branch: dict, pk_to_doc: dict[int, str], days: int = 14
) -> None:
    """날짜별 슬롯을 Firestore에 upsert."""
    cafe_id = branch["cafe_id"]
    base_url = branch["base_url"]
    db = get_db()
    today = date.today()
    crawled_at = datetime.now()
    writes = 0

    known_hashes = load_cafe_hashes(db, cafe_id)
    new_hashes: dict[str, str] = {}

    opener = _make_opener()
    csrf = _get_csrf(opener, base_url)
    if not csrf:
        print(f"  [WARN] CSRF 없음, 진행 시도")

    for i in range(days + 1):
        target_date = today + timedelta(days=i)
        date_str = target_date.strftime("%Y-%m-%d")

        day_data = _fetch_day(opener, base_url, csrf, target_date)
        time.sleep(REQUEST_DELAY)
        if day_data is None:
            print(f"  {date_str}: 조회 실패")
            continue

        times_map: dict = day_data.get("times", {})  # {str(pk): [...]}
        avail = full = 0
        themes_slots: dict[str, dict] = {}

        for pk_str, slots in times_map.items():
            try:
                pk = int(pk_str)
            except ValueError:
                continue
            theme_doc_id = pk_to_doc.get(pk)
            if not theme_doc_id:
                continue

            for slot in slots:
                time_raw = slot.get("time", "")  # "HH:MM:SS"
                parts = time_raw.split(":")
                if len(parts) < 2:
                    continue
                try:
                    hh, mm = int(parts[0]), int(parts[1])
                    time_obj = dtime(hh, mm)
                except Exception:
                    continue

                slot_dt = datetime(
                    target_date.year, target_date.month, target_date.day, hh, mm
                )
                if slot_dt <= datetime.now():
                    continue

                is_full = slot.get("reservation", False)
                status = "full" if is_full else "available"
                booking_url = f"{base_url}/reservation" if status == "available" else None

                themes_slots.setdefault(theme_doc_id, {"slots": []})["slots"].append({
                    "time":        f"{hh:02d}:{mm:02d}",
                    "status":      status,
                    "booking_url": booking_url,
                })
                if status == "available":
                    avail += 1
                else:
                    full += 1

        if themes_slots:
            h = upsert_cafe_date_schedules(
                db, date_str, cafe_id, themes_slots, crawled_at,
                known_hash=known_hashes.get(date_str),
            )
            if h:
                new_hashes[date_str] = h
                writes += 1

        print(f"  {date_str}: 가능 {avail}개 / 마감 {full}개")

    if new_hashes:
        today_str = today.isoformat()
        save_cafe_hashes(db, cafe_id, {
            k: v for k, v in {**known_hashes, **new_hashes}.items()
            if k >= today_str
        })

    print(f"\n  스케줄 동기화 완료: {writes}개 날짜 문서 작성")


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main(run_schedule: bool = True, days: int = 14) -> None:
    print("=" * 60)
    print("제로월드 (zeroworld) → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)

    for branch in BRANCHES:
        print(f"\n{'=' * 40}")
        print(f"[ {branch['cafe_name']} {branch['branch_name']} ]")
        print(f"{'=' * 40}")

        # 테마 목록 먼저 조회 (오늘 기준)
        opener = _make_opener()
        csrf = _get_csrf(opener, branch["base_url"])
        today_data = _fetch_day(opener, branch["base_url"], csrf, date.today())
        if today_data is None:
            print("  테마 조회 실패, 건너뜀.")
            continue

        theme_data = today_data.get("data", [])
        if not theme_data:
            print("  테마 없음, 건너뜀.")
            continue

        print("\n[ 1단계 ] 카페 메타 동기화")
        sync_cafe_meta(branch)

        print("\n[ 2단계 ] 테마 동기화")
        pk_to_doc = sync_themes(branch, theme_data)
        if not pk_to_doc:
            print("  테마 동기화 실패, 건너뜀.")
            continue

        if run_schedule:
            print(f"\n[ 3단계 ] 스케줄 동기화 (오늘~{days}일 후)")
            sync_schedules(branch, pk_to_doc, days=days)

    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="제로월드 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
