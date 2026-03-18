"""
ESC방탈출카페 테마 + 스케줄 DB 동기화 스크립트.

지점:
  대전둔산점  cafe_id=2024880532  http://djdsesc.co.kr/
  천안점      cafe_id=27559974    http://www.caesc.co.kr/
  평택점      cafe_id=1314964065  http://ptesc.co.kr/

예약 시스템: 자체 PHP 게시판

API:
  POST {base_url}/bbs/board.php?bo_table=reserve
  파라미터: wr_1={지점명} wr_3=YYYY-MM-DD wr_5=2 select_room=(공백)

HTML 구조:
  <select name="select_room">
    <option value="room1">테마명</option>   ← 테마 목록 (날짜 무관)
  </select>
  <tr>
    <td>HH:MM</td>
    <td>테마명</td>
    ...
    <a href="/bbs/write.php?...room_code=room1&wr_4=HH:MM...">
      <span class="reserve_ok">예약</span>   ← 가능
    </a>
    또는
    <span class="reserve_no">마감</span>     ← 불가
  </tr>

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_escbangtalul_db.py
  uv run python scripts/sync_escbangtalul_db.py --no-schedule
  uv run python scripts/sync_escbangtalul_db.py --days 14
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

REQUEST_DELAY = 0.8

BRANCHES = [
    {
        "cafe_id":   "2024880532",
        "name":      "ESC방탈출카페",
        "branch_name": "대전둔산점",
        "area":      "daejeon",
        "address":   "대전 서구 둔산동 1062",
        "base_url":  "http://djdsesc.co.kr",
        "wr_1":      "대전둔산점",
    },
    {
        "cafe_id":   "27559974",
        "name":      "ESC방탈출카페",
        "branch_name": "천안점",
        "area":      "cheonan",
        "address":   "충남 천안시 동남구 신부동 462-1",
        "base_url":  "http://www.caesc.co.kr",
        "wr_1":      "천안점",
    },
    {
        "cafe_id":   "1314964065",
        "name":      "ESC방탈출카페",
        "branch_name": "평택점",
        "area":      "gyeonggi",
        "address":   "경기 평택시",
        "base_url":  "http://ptesc.co.kr",
        "wr_1":      "평택점",
    },
]

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
}


def _fetch(base_url: str, wr_1: str, target_date: date) -> bytes:
    url = f"{base_url}/bbs/board.php"
    params = urllib.parse.urlencode({
        "bo_table": "reserve",
        "wr_1": wr_1,
        "wr_3": target_date.strftime("%Y-%m-%d"),
        "wr_5": "2",
        "select_room": "",
    }).encode()
    req = urllib.request.Request(url, data=params, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as r:
            return r.read()
    except Exception as e:
        print(f"  [WARN] GET {url} 실패: {e}")
        return b""


def _parse_themes(html: str) -> dict[str, str]:
    """
    select_room 드롭다운에서 {room_code: theme_name} 추출.
    """
    m = re.search(r'<select[^>]*name=["\']select_room["\'][^>]*>(.*?)</select>', html, re.DOTALL)
    if not m:
        return {}
    options = re.findall(r'<option[^>]*value=["\'](\w+)["\'][^>]*>(.*?)</option>', m.group(1))
    return {val: txt.strip() for val, txt in options if val}


def _parse_slots(html: str, base_url: str) -> list[dict]:
    """
    테이블 행에서 슬롯 추출.
    반환: [{time, theme_name, status, booking_url}]
    """
    slots = []
    # 각 행: <td>HH:MM</td><td>테마명</td>...<a href="..."><span class="reserve_ok"> 또는 <span class="reserve_no">
    row_pattern = re.compile(
        r'<tr>\s*<td>(\d{1,2}:\d{2})</td>\s*<td>(.*?)</td>.*?'
        r'(?:<a\s+href="([^"]*)"[^>]*>)?\s*<span\s+class="(reserve_\w+)"',
        re.DOTALL
    )
    for m in row_pattern.finditer(html):
        time_str = m.group(1)
        theme_name = re.sub(r'<[^>]+>', '', m.group(2)).strip()
        href = m.group(3) or ""
        css_class = m.group(4)

        if not theme_name:
            continue

        # 시간 파싱
        try:
            hh, mm = int(time_str.split(":")[0]), int(time_str.split(":")[1])
        except Exception:
            continue

        if css_class == "reserve_ok":
            status = "available"
            booking_url = (base_url + href) if href else None
        else:
            status = "full"
            booking_url = None

        slots.append({
            "time":        f"{hh:02d}:{mm:02d}",
            "theme_name":  theme_name,
            "status":      status,
            "booking_url": booking_url,
        })

    return slots


# ── DB 동기화 ──────────────────────────────────────────────────────────────────

def sync_one_branch(branch: dict, days: int) -> None:
    db = get_db()
    cafe_id = branch["cafe_id"]
    base_url = branch["base_url"]
    wr_1 = branch["wr_1"]

    upsert_cafe(db, cafe_id, {
        "name":        branch["name"],
        "branch_name": branch["branch_name"],
        "address":     branch["address"],
        "area":        branch["area"],
        "website_url": base_url,
        "engine":      "escbangtalul",
        "crawled":     True,
        "is_active":   True,
    })
    print(f"  [UPSERT] 카페: {branch['name']} {branch['branch_name']} (id={cafe_id})")

    today = date.today()
    crawled_at = datetime.now()
    theme_doc_map: dict[str, str] = {}
    themes_initialized = False
    date_themes: dict[str, dict] = {}

    for i in range(days + 1):
        target_date = today + timedelta(days=i)
        date_str = target_date.strftime("%Y-%m-%d")

        raw = _fetch(base_url, wr_1, target_date)
        time.sleep(REQUEST_DELAY)
        if not raw:
            continue

        html = raw.decode("utf-8", errors="replace")

        # 첫 번째 날짜에서 테마 목록 초기화
        if not themes_initialized:
            theme_map = _parse_themes(html)
            # reverse: theme_name → doc_id
            name_to_doc: dict[str, str] = {}
            for room_code, theme_name in theme_map.items():
                doc_id = get_or_create_theme(db, cafe_id, theme_name, {
                    "poster_url": None,
                    "is_active":  True,
                })
                name_to_doc[theme_name] = doc_id
                print(f"  [UPSERT] 테마: {theme_name} ({room_code})")
            themes_initialized = True

        slots = _parse_slots(html, base_url)
        avail = full = 0

        for slot in slots:
            theme_name = slot["theme_name"]
            if theme_name not in name_to_doc:
                # 예외: 드롭다운에 없는 테마명 → 즉시 upsert
                doc_id = get_or_create_theme(db, cafe_id, theme_name, {
                    "poster_url": None,
                    "is_active":  True,
                })
                name_to_doc[theme_name] = doc_id

            doc_id = name_to_doc[theme_name]

            try:
                hh, mm = int(slot["time"][:2]), int(slot["time"][3:5])
            except Exception:
                continue
            slot_dt = datetime(target_date.year, target_date.month, target_date.day, hh, mm)
            if slot_dt <= datetime.now():
                continue

            date_themes.setdefault(date_str, {}).setdefault(
                doc_id, {"slots": []}
            )["slots"].append({
                "time":        slot["time"],
                "status":      slot["status"],
                "booking_url": slot.get("booking_url"),
            })
            if slot["status"] == "available":
                avail += 1
            else:
                full += 1

        print(f"  {date_str}: 가능 {avail} / 마감 {full}")

    # Firestore upsert
    known_hashes = load_cafe_hashes(db, cafe_id)
    new_hashes: dict[str, str] = {}
    writes = 0

    for date_str, themes in sorted(date_themes.items()):
        h = upsert_cafe_date_schedules(
            db, date_str, cafe_id, themes, crawled_at,
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


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main(run_schedule: bool = True, days: int = 14) -> None:
    print("=" * 60)
    print("ESC방탈출카페 → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)

    for branch in BRANCHES:
        print(f"\n[ {branch['branch_name']} ] 동기화")
        try:
            sync_one_branch(branch, days=days if run_schedule else 0)
        except Exception as e:
            print(f"  [ERROR] {branch['branch_name']} 실패: {e}")

    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ESC방탈출카페 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
