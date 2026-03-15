"""
싸인이스케이프(signescape.com) 테마 + 스케줄 DB 동기화 스크립트.

사이트: http://www.signescape.com
플랫폼: 자체 PHP CMS (JIJEM 코드 기반, 시크릿코드·퍼즐팩토리와 동일 계열)

지점:
  홍대점      R_JIJEM=S5  themes=A,B,C  cafe_id=678802397   area=hongdae
  강남시티점  R_JIJEM=S6  themes=A,B,C  cafe_id=1245109855  area=gangnam

API:
  GET http://www.signescape.com/sub/sub03_1.html
      ?R_JIJEM={code}&chois_date={YYYY-MM-DD}&R_THEMA={A|B|C...}
  응답: EUC-KR HTML
    div#reser3 → 테마 정보 (이미지, 설명)
    div#reser4 ul.list → 슬롯 목록
      a href="sub03_2.html?...&room_time=HH:MM&...&room_name={테마명}&..."
        li.timeOn → 예약가능
      li.timeOff → 예약불가 (링크 없음)

예약 URL: http://www.signescape.com/sub/sub03_2.html
          ?chois_date={DATE}&room_time={HH:MM}&jijem_code={code}&room_code={X}&room_name={name}&room_week={주말/평일}

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_signescape_db.py
  uv run python scripts/sync_signescape_db.py --no-schedule
  uv run python scripts/sync_signescape_db.py --days 14
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

SITE_URL = "http://www.signescape.com"
REV_URL = SITE_URL + "/sub/sub03_1.html"
REQUEST_DELAY = 0.8

BRANCHES = [
    {
        "cafe_id":      "678802397",
        "branch_name":  "홍대점",
        "jijem":        "S5",
        "themes":       ["A", "B", "C"],
        "area":         "hongdae",
        "address":      "서울 마포구 와우산로 65 6층",
    },
    {
        "cafe_id":      "1245109855",
        "branch_name":  "강남시티점",
        "jijem":        "S6",
        "themes":       ["A", "B", "C"],
        "area":         "gangnam",
        "address":      "서울 강남구 강남대로94길 67 도연빌딩 지하1층",
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
    "Referer": SITE_URL + "/sub/sub03_1.html",
}


def _fetch(jijem: str, thema: str, target_date: date) -> str:
    """날짜 + 테마코드별 예약 페이지 HTML 반환."""
    date_str = target_date.strftime("%Y-%m-%d")
    url = f"{REV_URL}?R_JIJEM={jijem}&chois_date={date_str}&R_THEMA={thema}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            raw = resp.read()
    except Exception as e:
        print(f"  [WARN] GET {url} 실패: {e}")
        return ""
    try:
        return raw.decode("euc-kr", errors="replace")
    except Exception:
        return raw.decode("utf-8", errors="replace")


def _parse_page(html: str, jijem: str, thema: str, target_date: date) -> dict | None:
    """
    HTML에서 테마명 + 슬롯 목록 파싱.
    반환: {"name": str, "slots": [{"time", "status", "booking_url"}]} or None
    """
    # 테마명: booking URL의 room_name 파라미터에서 추출
    m_name = re.search(r"room_name=([^&\"'\s]+)", html)
    if not m_name:
        return None
    theme_name = m_name.group(1).strip()
    if not theme_name:
        return None

    # URL 인코딩 제거 (한글 등)
    try:
        from urllib.parse import unquote
        theme_name = unquote(theme_name, encoding="euc-kr")
    except Exception:
        pass

    slots: list[dict] = []
    date_str = target_date.strftime("%Y-%m-%d")

    # 예약가능 슬롯: <a href="sub03_2.html?...room_time=HH:MM..."><li class="timeOn">
    avail_pattern = re.compile(
        r'<a\s+href="(sub03_2\.html\?[^"]+room_time=(\d{2}:\d{2})[^"]+)">.*?<li\s+class="timeOn"',
        re.DOTALL,
    )
    for m in avail_pattern.finditer(html):
        href = m.group(1)
        time_str = m.group(2)
        booking_url = SITE_URL + "/sub/" + href
        slots.append({
            "time":        time_str,
            "status":      "available",
            "booking_url": booking_url,
        })

    # 예약불가 슬롯: <li class="timeOff">★ HH:MM</li> (링크 없음)
    off_times = re.findall(r'<li\s+class="timeOff">[★☆]?\s*(\d{2}:\d{2})</li>', html)
    for time_str in off_times:
        slots.append({
            "time":        time_str,
            "status":      "full",
            "booking_url": None,
        })

    if not slots:
        return None
    return {"name": theme_name, "slots": slots}


# ── DB 동기화 ─────────────────────────────────────────────────────────────────

def sync_cafe_meta(db, branch: dict) -> None:
    upsert_cafe(db, branch["cafe_id"], {
        "name":        "싸인이스케이프",
        "branch_name": branch["branch_name"],
        "address":     branch["address"],
        "area":        branch["area"],
        "website_url": SITE_URL,
        "engine":      "signescape",
        "crawled":     True,
        "is_active":   True,
    })
    print(f"  [UPSERT] 카페: 싸인이스케이프 {branch['branch_name']} (id={branch['cafe_id']})")


def sync_one_branch(branch: dict, days: int) -> int:
    db = get_db()
    cafe_id = branch["cafe_id"]
    jijem = branch["jijem"]
    theme_codes = branch["themes"]
    today = date.today()
    crawled_at = datetime.now()

    cafe_doc = db.collection("cafes").document(cafe_id).get()
    if not cafe_doc.exists:
        print(f"  [WARN] cafe {cafe_id} Firestore 미존재 — 건너뜀")
        return 0

    # 테마 이름 발견: 가장 가까운 날짜 fallback
    theme_name_map: dict[str, str] = {}  # theme_code → theme_name
    for i in range(8):
        target = today + timedelta(days=i)
        found_any = False
        for code in theme_codes:
            if code in theme_name_map:
                continue
            html = _fetch(jijem, code, target)
            time.sleep(REQUEST_DELAY)
            parsed = _parse_page(html, jijem, code, target)
            if parsed:
                theme_name_map[code] = parsed["name"]
                found_any = True
        if len(theme_name_map) == len(theme_codes):
            break
        if found_any:
            continue

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
            html = _fetch(jijem, code, target_date)
            time.sleep(REQUEST_DELAY)
            parsed = _parse_page(html, jijem, code, target_date)
            if not parsed:
                continue

            for slot in parsed["slots"]:
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
    print("싸인이스케이프(signescape.com) → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)
    db = get_db()

    print("\n[ 1단계 ] 카페 메타 동기화")
    for branch in BRANCHES:
        sync_cafe_meta(db, branch)

    if run_schedule:
        for branch in BRANCHES:
            print(f"\n[ 2단계 ] {branch['branch_name']} 스케줄 동기화 (오늘~{days}일 후)")
            sync_one_branch(branch, days=days)

    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="싸인이스케이프 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
