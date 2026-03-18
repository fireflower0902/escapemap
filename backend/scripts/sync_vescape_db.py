"""
방탈출브이(v-escape.co.kr) 테마 + 스케줄 DB 동기화 스크립트.

사이트: http://www.v-escape.co.kr
플랫폼: JIJEM 계열 PHP (EUC-KR) — signescape와 동일 계열

지점:
  삼덕점  R_JIJEM=S1  themes=A~G  cafe_id=858962026   area=daegu  (대구 중구 삼덕동1가 17-16)
  공평점  R_JIJEM=S2  themes=A~E  cafe_id=1254330051  area=daegu  (대구 중구 공평동 62-11)

API:
  GET http://www.v-escape.co.kr/sub/sub03_1.html
      ?R_JIJEM={code}&R_THEMA={A|B|C...}&chois_date={YYYY-MM-DD}
  응답: EUC-KR HTML
    div#reser2 → 테마 정보
      img src="/upload_file/room/NN{테마명}.png" → 테마명 파싱
      div.timeOn → 예약가능 슬롯 (a href 포함)
      div.timeOff → 예약불가 슬롯 (a href 없음)
  예약 URL: sub03_2.html?chois_date={DATE}&room_time={HH:MM [suffix]}&jijem_code={code}&room_code={thema}&room_name=&room_week={주말/평일}

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_vescape_db.py
  uv run python scripts/sync_vescape_db.py --no-schedule
  uv run python scripts/sync_vescape_db.py --days 14
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

SITE_URL = "http://www.v-escape.co.kr"
REV_URL = SITE_URL + "/sub/sub03_1.html"
REQUEST_DELAY = 0.8

BRANCHES = [
    {
        "cafe_id":      "858962026",
        "branch_name":  "삼덕점",
        "jijem":        "S1",
        "themes":       ["A", "B", "C", "D", "E", "F", "G"],
        "area":         "daegu",
        "address":      "대구 중구 삼덕동1가 17-16",
    },
    {
        "cafe_id":      "1254330051",
        "branch_name":  "공평점",
        "jijem":        "S2",
        "themes":       ["A", "B", "C", "D", "E"],
        "area":         "daegu",
        "address":      "대구 중구 공평동 62-11",
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
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": SITE_URL + "/",
}


def _fetch(jijem: str, thema: str, target_date: date) -> bytes:
    """날짜 + 테마코드별 예약 페이지 원시 바이트 반환."""
    date_str = target_date.strftime("%Y-%m-%d")
    url = f"{REV_URL}?R_JIJEM={jijem}&R_THEMA={thema}&chois_date={date_str}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            return resp.read()
    except Exception as e:
        print(f"  [WARN] GET {url} 실패: {e}")
        return b""


def _extract_theme_name(raw: bytes, thema_code: str) -> str | None:
    """
    HTML raw bytes에서 테마명 추출.
    /upload_file/room/NN{테마명}.png 형식 → EUC-KR 디코드 후 leading 숫자 제거.
    """
    # Find img src containing upload_file/room/
    m = re.search(rb'upload_file/room/([^"<>]+?)\.(png|jpg|jpeg)', raw, re.IGNORECASE)
    if not m:
        return None
    filename_bytes = m.group(1)
    try:
        filename = filename_bytes.decode("euc-kr", errors="replace")
    except Exception:
        filename = filename_bytes.decode("utf-8", errors="replace")
    # Strip leading 2-digit number prefix (e.g., "01" from "01퍽댓쉿")
    name = re.sub(r"^\d+\s*-*\s*", "", filename).strip()
    return name if name else f"테마{thema_code}"


def _parse_slots(raw: bytes, jijem: str, thema: str, target_date: date) -> list[dict]:
    """
    HTML raw bytes에서 슬롯 목록 파싱.
    반환: [{time, status, booking_url}]
    """
    try:
        html = raw.decode("euc-kr", errors="replace")
    except Exception:
        html = raw.decode("utf-8", errors="replace")

    slots: list[dict] = []
    date_str = target_date.strftime("%Y-%m-%d")

    # 예약가능: <a href="sub03_2.html?...room_time=HH:MM..."><div class="timeOn">
    avail_pattern = re.compile(
        r'<a\s+href="(sub03_2\.html\?[^"]+)">\s*<div\s+class="timeOn"',
        re.DOTALL,
    )
    for m in avail_pattern.finditer(html):
        href = m.group(1)
        # Extract time from room_time parameter (may include suffix like " (조조)")
        t_match = re.search(r"room_time=(\d{2}:\d{2})", href)
        if not t_match:
            continue
        time_str = t_match.group(1)
        booking_url = SITE_URL + "/sub/" + href
        slots.append({
            "time":        time_str,
            "status":      "available",
            "booking_url": booking_url,
        })

    # 예약불가: div.timeOff without preceding <a>
    # Pattern: timeOff div containing HH:MM
    for m in re.finditer(r'<div\s+class="timeOff"[^>]*>[^<]*(\d{2}:\d{2})', html):
        # Check that this is NOT inside an <a> tag
        before = html[max(0, m.start()-50):m.start()]
        if "<a " in before:
            continue
        time_str = m.group(1)
        slots.append({
            "time":        time_str,
            "status":      "full",
            "booking_url": None,
        })

    return slots


# ── DB 동기화 ─────────────────────────────────────────────────────────────────

def sync_cafe_meta(db, branch: dict) -> None:
    upsert_cafe(db, branch["cafe_id"], {
        "name":        "방탈출브이",
        "branch_name": branch["branch_name"],
        "address":     branch["address"],
        "area":        branch["area"],
        "website_url": SITE_URL,
        "engine":      "vescape",
        "crawled":     True,
        "is_active":   True,
    })
    print(f"  [UPSERT] 카페: 방탈출브이 {branch['branch_name']} (id={branch['cafe_id']})")


def sync_one_branch(branch: dict, days: int) -> int:
    db = get_db()
    cafe_id = branch["cafe_id"]
    jijem = branch["jijem"]
    theme_codes = branch["themes"]
    today = date.today()
    crawled_at = datetime.now()

    # 테마 이름 발견: 가장 가까운 날짜에서 시도
    theme_name_map: dict[str, str] = {}  # theme_code → theme_name
    for i in range(8):
        target = today + timedelta(days=i)
        for code in theme_codes:
            if code in theme_name_map:
                continue
            raw = _fetch(jijem, code, target)
            time.sleep(REQUEST_DELAY)
            if not raw:
                continue
            name = _extract_theme_name(raw, code)
            if name:
                theme_name_map[code] = name
        if len(theme_name_map) == len(theme_codes):
            break

    if not theme_name_map:
        print(f"  [{branch['branch_name']}] 테마 정보를 찾을 수 없음, 건너뜀.")
        return 0

    # 테마 upsert
    name_to_doc: dict[str, str] = {}
    for code, tname in theme_name_map.items():
        doc_id = get_or_create_theme(db, cafe_id, tname, {
            "poster_url": None,
            "is_active":  True,
        })
        name_to_doc[code] = doc_id
        print(f"  [UPSERT] 테마: {tname} (code={code})")

    # 스케줄 upsert
    target_dates = [today + timedelta(days=i) for i in range(days + 1)]
    known_hashes = load_cafe_hashes(db, cafe_id)
    new_hashes: dict[str, str] = {}
    date_themes: dict[str, dict] = {}
    writes = 0

    for target_date in target_dates:
        date_str = target_date.strftime("%Y-%m-%d")
        avail = full = 0

        for code in theme_codes:
            doc_id = name_to_doc.get(code)
            if not doc_id:
                continue
            raw = _fetch(jijem, code, target_date)
            time.sleep(REQUEST_DELAY)
            if not raw:
                continue
            slots = _parse_slots(raw, jijem, code, target_date)

            for slot in slots:
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

                date_themes.setdefault(date_str, {}).setdefault(
                    doc_id, {"slots": []}
                )["slots"].append({
                    "time":        f"{hh:02d}:{mm:02d}",
                    "status":      slot["status"],
                    "booking_url": slot.get("booking_url"),
                })
                if slot["status"] == "available":
                    avail += 1
                else:
                    full += 1

        print(f"  {date_str}: 가능 {avail} / 마감 {full}")

    for date_str, themes_map in date_themes.items():
        h = upsert_cafe_date_schedules(
            db, date_str, cafe_id, themes_map, crawled_at,
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
    print("방탈출브이(v-escape.co.kr) → DB 동기화")
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
                sync_one_branch(branch, days=days)
            except Exception as e:
                print(f"  [ERROR] {branch['branch_name']} 크롤링 실패: {e}")

    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="방탈출브이 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
