"""
방탈출ESC(roomescape.net) 테마 + 스케줄 DB 동기화 스크립트.

사이트: http://roomescape.net
플랫폼: 자체 PHP (서버사이드 렌더링, jQuery UI Datepicker)

지점:
  신촌점  cafe_id=273855007  (서울 서대문구 신촌)

API:
  GET http://roomescape.net/booking.php?r_date={YYYY-MM-DD}&query=0
  응답 HTML:
    table.booking-table
      tr td[colspan=2] p span[style="color:#90031e"] → 테마명 (ROOM1~5)
      tr td table.time-table
        td.active a[href="./booking_form.php?date=...&time=HH:MM&room_name=..."] → 예약가능
        td (no class) → 예약완료

예약 URL: http://roomescape.net/booking_form.php?date={DATE}&time={HH:MM}&room_name={NAME}

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_roomescape_db.py
  uv run python scripts/sync_roomescape_db.py --no-schedule
  uv run python scripts/sync_roomescape_db.py --days 14
"""

import re
import ssl
import sys
import time
import urllib.parse
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

SITE_URL = "http://roomescape.net"
REQUEST_DELAY = 0.8

BRANCHES = [
    {
        "cafe_id":     "273855007",
        "branch_name": "신촌점",
        "area":        "hongdae",
        "address":     "서울 서대문구 창천동 19-10",
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
    "Accept": "text/html,application/xhtml+xml,*/*",
    "Accept-Language": "ko-KR,ko;q=0.9",
}


def _fetch(target_date: date) -> str:
    date_str = target_date.strftime("%Y-%m-%d")
    url = f"{SITE_URL}/booking.php?r_date={date_str}&query=0"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [WARN] GET {url} 실패: {e}")
        return ""


def parse_booking_page(html: str, target_date: date) -> list[dict]:
    """
    예약 페이지 HTML 파싱.
    반환: [{name: str, slots: [{time, status, booking_url}]}]
    """
    date_str = target_date.strftime("%Y-%m-%d")
    themes: list[dict] = []

    # booking-table의 행들을 순서대로 처리
    # 홀수 행: 테마 헤더 (colspan=2 td > p > span)
    # 짝수 행: 슬롯 테이블

    # 테마 헤더 추출: <p>ROOM{N} : <span style="color:#90031e">테마명</span></p>
    header_pattern = re.compile(
        r'<td[^>]+colspan=["\']?2["\']?[^>]*>.*?'
        r'<span[^>]+style=["\'][^"\']*color:#90031e[^"\']*["\'][^>]*>([^<]+)</span>',
        re.DOTALL,
    )

    # time-table 블록 추출
    timetable_pattern = re.compile(
        r'<table[^>]+class=["\']time-table["\'][^>]*>(.*?)</table>',
        re.DOTALL,
    )

    headers = list(header_pattern.finditer(html))
    timetables = list(timetable_pattern.finditer(html))

    for i, h_match in enumerate(headers):
        theme_name = h_match.group(1).strip()
        if not theme_name:
            continue

        slots: list[dict] = []

        if i < len(timetables):
            tt_html = timetables[i].group(1)

            # 예약가능: <td class='active'><a href='./booking_form.php?date=...&time=HH:MM&...'>
            avail_pattern = re.compile(
                r"<td[^>]+class=['\"]active['\"][^>]*>"
                r"\s*<a\s+href=['\"](\./booking_form\.php\?[^'\"]+)['\"]>",
                re.DOTALL,
            )
            for m in avail_pattern.finditer(tt_html):
                href = m.group(1)
                # time 파라미터 추출
                m_time = re.search(r"[?&]time=(\d{2}:\d{2})", href)
                if not m_time:
                    continue
                time_str = m_time.group(1)
                booking_url = SITE_URL + "/" + href.lstrip("./")
                slots.append({
                    "time":        time_str,
                    "status":      "available",
                    "booking_url": booking_url,
                })

            # 예약완료: <td>HH:MM<br/><span class='time-text'>(예약완료)</span></td>
            full_pattern = re.compile(
                r"<td>(\d{2}:\d{2})<br/>\s*<span[^>]+class=['\"]time-text['\"]>\(예약완료\)</span>",
            )
            for m in full_pattern.finditer(tt_html):
                slots.append({
                    "time":        m.group(1),
                    "status":      "full",
                    "booking_url": None,
                })

        if slots:
            themes.append({"name": theme_name, "slots": slots})

    return themes


# ── DB 동기화 ─────────────────────────────────────────────────────────────────

def sync_cafe_meta(db, branch: dict) -> None:
    upsert_cafe(db, branch["cafe_id"], {
        "name":        "방탈출ESC",
        "branch_name": branch["branch_name"],
        "address":     branch["address"],
        "area":        branch["area"],
        "website_url": SITE_URL,
        "engine":      "roomescape",
        "crawled":     True,
        "is_active":   True,
    })
    print(f"  [UPSERT] 카페: 방탈출ESC {branch['branch_name']} (id={branch['cafe_id']})")


def sync_branch(branch: dict, days: int = 14) -> int:
    db = get_db()
    cafe_id = branch["cafe_id"]
    today = date.today()
    target_dates = [today + timedelta(days=i) for i in range(days + 1)]
    crawled_at = datetime.now()
    total_writes = 0

    cafe_doc = db.collection("cafes").document(cafe_id).get()
    if not cafe_doc.exists:
        print(f"  [WARN] cafe {cafe_id} Firestore 미존재 — 건너뜀")
        return 0

    theme_cache: dict[str, str] = {}
    date_themes: dict[str, dict] = {}

    for target_date in target_dates:
        date_str = target_date.strftime("%Y-%m-%d")
        raw_html = _fetch(target_date)
        time.sleep(REQUEST_DELAY)

        if not raw_html:
            print(f"  {date_str}: 데이터 없음")
            continue

        raw_themes = parse_booking_page(raw_html, target_date)
        if not raw_themes:
            print(f"  {date_str}: 데이터 없음")
            continue

        avail_cnt = full_cnt = 0

        for t in raw_themes:
            name = t["name"]
            if name not in theme_cache:
                doc_id = get_or_create_theme(db, cafe_id, name, {
                    "poster_url": None,
                    "is_active":  True,
                })
                theme_cache[name] = doc_id
                print(f"  [UPSERT] 테마: {name}")
            theme_doc_id = theme_cache[name]

            for slot in t["slots"]:
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

                status = slot["status"]
                date_themes.setdefault(date_str, {}).setdefault(
                    theme_doc_id, {"slots": []}
                )["slots"].append({
                    "time":        f"{hh:02d}:{mm:02d}",
                    "status":      status,
                    "booking_url": slot.get("booking_url"),
                })

                if status == "available":
                    avail_cnt += 1
                else:
                    full_cnt += 1

        print(f"  {date_str}: 가능 {avail_cnt} / 마감 {full_cnt}")

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
        today_str = today.isoformat()
        save_cafe_hashes(db, cafe_id, {
            k: v for k, v in {**known_hashes, **new_hashes}.items()
            if k >= today_str
        })

    print(f"  스케줄 동기화 완료: {total_writes}개 날짜 문서 작성")
    return total_writes


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main(run_schedule: bool = True, days: int = 14):
    print("=" * 60)
    print("방탈출ESC(roomescape.net) → DB 동기화")
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
                sync_branch(branch, days=days)
            except Exception as e:
                print(f"  [ERROR] {branch['branch_name']} 크롤링 실패: {e}")

    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="방탈출ESC DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
