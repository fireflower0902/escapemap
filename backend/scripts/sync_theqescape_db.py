"""
더큐이스케이프(the-qescapedj.co.kr) 테마 + 스케줄 DB 동기화 스크립트.

지점:
  대전둔산점  cafe_id=1696389756  https://www.the-qescapedj.co.kr/

예약 시스템: sinbiweb 커스텀 (home.php 대신 /reserve/ 경로 사용)

API:
  POST https://www.the-qescapedj.co.kr/reserve/
  파라미터: rdate=YYYY-MM-DD  theme=(공백 = 전체)

HTML 구조:
  <select name="theme">
    <option value="">전체테마</option>
    <option value="CODE">테마명</option>
  </select>

  <a href="javascript:chkBooking('HH:MM', 'CODE');" >        ← 예약가능 (class 없음)
    <span class="time">HH:MM</span>
    <span class="possible">예약가능</span>
    <span class="impossible">예약마감</span>
  </a>

  <a href="javascript:chkBooking('HH:MM', 'CODE');" class="end">  ← 예약마감
    ...
  </a>

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_theqescape_db.py
  uv run python scripts/sync_theqescape_db.py --no-schedule
  uv run python scripts/sync_theqescape_db.py --days 14
"""

import re
import ssl
import sys
import time
import urllib.request
import urllib.parse
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

CAFE_ID   = "1696389756"
NAME      = "더큐이스케이프"
ADDRESS   = "대전 서구 둔산동 1060-3"
AREA      = "daejeon"
SITE_URL  = "https://www.the-qescapedj.co.kr"
RESERVE_URL = SITE_URL + "/reserve/"

REQUEST_DELAY = 0.8

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": SITE_URL + "/reserve/",
}


def _fetch(target_date: date) -> bytes:
    params = urllib.parse.urlencode({
        "rdate": target_date.strftime("%Y-%m-%d"),
        "theme": "",
    }).encode()
    req = urllib.request.Request(RESERVE_URL, data=params, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as r:
            return r.read()
    except Exception as e:
        print(f"  [WARN] POST {RESERVE_URL} 실패: {e}")
        return b""


def _parse_themes(html: str) -> dict[str, str]:
    """select[name=theme] 드롭다운에서 {code: theme_name} 추출."""
    m = re.search(
        r'<select[^>]*name=["\']theme["\'][^>]*>(.*?)</select>',
        html, re.DOTALL
    )
    if not m:
        return {}
    options = re.findall(
        r'<option[^>]*value=["\'](\w+)["\'][^>]*>(.*?)</option>',
        m.group(1)
    )
    return {val: txt.strip() for val, txt in options if val}


def _parse_slots(html: str) -> list[dict]:
    """
    chkBooking 앵커에서 슬롯 추출.
    반환: [{time, theme_code, status}]
    """
    slots = []
    pattern = re.compile(
        r'<a\s+href="javascript:chkBooking\(\'(\d{1,2}:\d{2})\',\s*\'(\w+)\'\);"'
        r'([^>]*)>'
    )
    for m in pattern.finditer(html):
        time_str  = m.group(1)
        theme_code = m.group(2)
        attrs     = m.group(3)
        # class="end" = 마감, 속성 없음 = 가능
        status = "full" if 'class="end"' in attrs else "available"
        try:
            hh, mm = int(time_str.split(":")[0]), int(time_str.split(":")[1])
        except Exception:
            continue
        slots.append({
            "time":       f"{hh:02d}:{mm:02d}",
            "theme_code": theme_code,
            "status":     status,
        })
    return slots


# ── DB 동기화 ──────────────────────────────────────────────────────────────────

def sync(days: int) -> None:
    db = get_db()

    upsert_cafe(db, CAFE_ID, {
        "name":        NAME,
        "branch_name": "대전둔산점",
        "address":     ADDRESS,
        "area":        AREA,
        "website_url": SITE_URL,
        "engine":      "theqescape",
        "crawled":     True,
        "is_active":   True,
    })
    print(f"  [UPSERT] 카페: {NAME} (id={CAFE_ID})")

    today      = date.today()
    crawled_at = datetime.now()

    # 첫 날 HTML에서 테마 코드·이름 추출
    first_html = _fetch(today).decode("utf-8", errors="replace")
    time.sleep(REQUEST_DELAY)
    theme_map = _parse_themes(first_html)  # {code: name}
    if not theme_map:
        print("  [ERROR] 테마 파싱 실패")
        return

    # code → theme_doc_id
    code_to_doc: dict[str, str] = {}
    for code, theme_name in theme_map.items():
        doc_id = get_or_create_theme(db, CAFE_ID, theme_name, {
            "poster_url": None,
            "is_active":  True,
        })
        code_to_doc[code] = doc_id
        print(f"  [UPSERT] 테마: {theme_name} ({code})")

    date_themes: dict[str, dict] = {}

    # 첫 날 슬롯 파싱 (재요청 없이 재활용)
    for day_offset in range(days + 1):
        target_date = today + timedelta(days=day_offset)
        date_str    = target_date.strftime("%Y-%m-%d")

        if day_offset == 0:
            html = first_html
        else:
            raw = _fetch(target_date)
            time.sleep(REQUEST_DELAY)
            if not raw:
                continue
            html = raw.decode("utf-8", errors="replace")

        slots  = _parse_slots(html)
        avail = full = 0

        for slot in slots:
            code   = slot["theme_code"]
            doc_id = code_to_doc.get(code)
            if not doc_id:
                continue

            try:
                hh, mm = int(slot["time"][:2]), int(slot["time"][3:5])
            except Exception:
                continue
            slot_dt = datetime(
                target_date.year, target_date.month, target_date.day, hh, mm
            )
            if slot_dt <= datetime.now():
                continue

            booking_url = RESERVE_URL if slot["status"] == "available" else None
            date_themes.setdefault(date_str, {}).setdefault(
                doc_id, {"slots": []}
            )["slots"].append({
                "time":        slot["time"],
                "status":      slot["status"],
                "booking_url": booking_url,
            })
            if slot["status"] == "available":
                avail += 1
            else:
                full += 1

        print(f"  {date_str}: 가능 {avail} / 마감 {full}")

    # Firestore upsert
    known_hashes = load_cafe_hashes(db, CAFE_ID)
    new_hashes: dict[str, str] = {}
    writes = 0

    for date_str, themes in sorted(date_themes.items()):
        h = upsert_cafe_date_schedules(
            db, date_str, CAFE_ID, themes, crawled_at,
            known_hash=known_hashes.get(date_str),
        )
        if h:
            new_hashes[date_str] = h
            writes += 1

    if new_hashes:
        today_str = today.isoformat()
        save_cafe_hashes(db, CAFE_ID, {
            k: v for k, v in {**known_hashes, **new_hashes}.items()
            if k >= today_str
        })

    print(f"  스케줄 동기화: {writes}개 날짜 작성")


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main(run_schedule: bool = True, days: int = 14) -> None:
    print("=" * 60)
    print("더큐이스케이프(the-qescapedj.co.kr) → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)

    if run_schedule:
        sync(days=days)
    else:
        db = get_db()
        upsert_cafe(db, CAFE_ID, {
            "name":        NAME,
            "branch_name": "대전둔산점",
            "address":     ADDRESS,
            "area":        AREA,
            "website_url": SITE_URL,
            "engine":      "theqescape",
            "crawled":     True,
            "is_active":   True,
        })
        print("  [SKIP] 스케줄 동기화 건너뜀")

    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="더큐이스케이프 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
