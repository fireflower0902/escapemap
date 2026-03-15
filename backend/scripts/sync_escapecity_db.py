"""
이스케이프시티(escapecity.kr) 테마 + 스케줄 DB 동기화 스크립트.

사이트: http://escapecity.kr
플랫폼: 자체 PHP CMS (JIJEM 코드 기반, puzzlefactory/signescape 동일 계열)

지점:
  영등포본점    R_JIJEM=S1  cafe_id=1444854771  area=etc       테마 A-F(6개)
  성신여대점    R_JIJEM=s2  cafe_id=926754766   area=etc       테마 A-F
  그랜드시티신촌점 R_JIJEM=S4 cafe_id=1834149457 area=hongdae   테마 A-F

API:
  GET http://escapecity.kr/sub/sub03_1.html
      ?R_JIJEM={code}&chois_date={YYYY-MM-DD}&R_THEMA={A|B|C...}
  응답: EUC-KR HTML
    li.timeOn a[href="sub03_2.html?...room_time=HH:MM..."] → 예약가능
    li.timeOff → 예약불가
    테마명: a[href^="sub03_1.html"] + li.thema1 텍스트

예약 URL: http://escapecity.kr/sub/sub03_2.html?chois_date={DATE}&room_time={HH:MM}&jijem_code={code}&room_code={THEMA}

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_escapecity_db.py
  uv run python scripts/sync_escapecity_db.py --no-schedule
  uv run python scripts/sync_escapecity_db.py --days 14
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

SITE_URL = "http://escapecity.kr"
REV_URL = SITE_URL + "/sub/sub03_1.html"
REQUEST_DELAY = 0.8

# 테마코드: A~F 시도 (실제 없는 테마는 빈 응답)
THEME_CODES = ["A", "B", "C", "D", "E", "F"]

BRANCHES = [
    {
        "cafe_id":     "1444854771",
        "branch_name": "영등포본점",
        "jijem":       "S1",
        "area":        "etc",
        "address":     "서울 영등포구 영중로8길 6",
    },
    {
        "cafe_id":     "926754766",
        "branch_name": "성신여대점",
        "jijem":       "s2",
        "area":        "etc",
        "address":     "서울 성북구 보문로34길 43",
    },
    {
        "cafe_id":     "1834149457",
        "branch_name": "그랜드시티신촌점",
        "jijem":       "S4",
        "area":        "hongdae",
        "address":     "서울 서대문구 연세로11길 39",
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
    date_str = target_date.strftime("%Y-%m-%d")
    url = f"{REV_URL}?R_JIJEM={jijem}&chois_date={date_str}&R_THEMA={thema}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            raw = resp.read()
        try:
            return raw.decode("euc-kr", errors="replace")
        except Exception:
            return raw.decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [WARN] GET {url} 실패: {e}")
        return ""


def _parse_page(html: str, jijem: str, thema: str, target_date: date) -> dict | None:
    """
    HTML에서 테마명 + 슬롯 목록 파싱.
    반환: {name: str, slots: [{time, status, booking_url}]} or None
    """
    # 테마명: li.thema1 텍스트 (또는 room_name URL 파라미터)
    m_name = re.search(r'<li[^>]+class="[^"]*thema1[^"]*"[^>]*>([^<]+)</li>', html)
    if m_name:
        theme_name = m_name.group(1).strip()
    else:
        # URL room_name 파라미터에서 추출
        m_rn = re.search(r'room_name=([^&"\'\\s]+)', html)
        if not m_rn:
            return None
        theme_name = m_rn.group(1).strip()
        try:
            from urllib.parse import unquote
            theme_name = unquote(theme_name, encoding="euc-kr")
        except Exception:
            pass

    if not theme_name:
        return None

    date_str = target_date.strftime("%Y-%m-%d")
    slots: list[dict] = []

    # 예약가능: li.timeOn > a[href="sub03_2.html?...room_time=HH:MM..."]
    avail_pattern = re.compile(
        r'<li[^>]+class="[^"]*timeOn[^"]*"[^>]*>.*?'
        r'<a\s+href="(sub03_2\.html\?[^"]+room_time=(\d{2}:\d{2})[^"]*)"',
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

    # 예약불가: li.timeOff 내 시간 텍스트
    off_pattern = re.compile(
        r'<li[^>]+class="[^"]*timeOff[^"]*"[^>]*>.*?(\d{2}:\d{2})',
        re.DOTALL,
    )
    for m in off_pattern.finditer(html):
        slots.append({
            "time":        m.group(1),
            "status":      "full",
            "booking_url": None,
        })

    if not slots:
        return None

    return {"name": theme_name, "slots": slots}


# ── DB 동기화 ─────────────────────────────────────────────────────────────────

def sync_cafe_meta(db, branch: dict) -> None:
    upsert_cafe(db, branch["cafe_id"], {
        "name":        "이스케이프시티",
        "branch_name": branch["branch_name"],
        "address":     branch["address"],
        "area":        branch["area"],
        "website_url": SITE_URL,
        "engine":      "escapecity",
        "crawled":     True,
        "is_active":   True,
    })
    print(f"  [UPSERT] 카페: 이스케이프시티 {branch['branch_name']} (id={branch['cafe_id']})")


def sync_one_branch(branch: dict, days: int) -> int:
    db = get_db()
    cafe_id = branch["cafe_id"]
    jijem = branch["jijem"]
    today = date.today()
    crawled_at = datetime.now()

    cafe_doc = db.collection("cafes").document(cafe_id).get()
    if not cafe_doc.exists:
        print(f"  [WARN] cafe {cafe_id} Firestore 미존재 — 건너뜀")
        return 0

    # 테마 이름 발견: 가장 가까운 날짜 fallback
    theme_name_map: dict[str, str] = {}  # thema_code → theme_name
    for i in range(8):
        target = today + timedelta(days=i)
        for code in THEME_CODES:
            if code in theme_name_map:
                continue
            html = _fetch(jijem, code, target)
            time.sleep(REQUEST_DELAY)
            parsed = _parse_page(html, jijem, code, target)
            if parsed:
                theme_name_map[code] = parsed["name"]
        if len(theme_name_map) >= 2:
            break

    if not theme_name_map:
        print(f"  [{branch['branch_name']}] 테마 정보를 찾을 수 없음, 건너뜀.")
        return 0

    # 테마 upsert
    code_to_doc: dict[str, str] = {}
    for code, tname in theme_name_map.items():
        doc_id = get_or_create_theme(db, cafe_id, tname, {
            "poster_url": None,
            "is_active":  True,
        })
        code_to_doc[code] = doc_id
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

        for code, doc_id in code_to_doc.items():
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
    print("이스케이프시티(escapecity.kr) → DB 동기화")
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
    parser = argparse.ArgumentParser(description="이스케이프시티 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
