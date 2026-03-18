"""
오렌지티비 방탈출(orangetb.com) 테마 + 스케줄 DB 동기화 스크립트.

지점:
  대구동성로점  cafe_id=363716272   o_id=1  area=daegu
  대전은행점    cafe_id=1908328454  o_id=5  area=daejeon

예약 시스템: GRYARD 자체 PHP CMS

API:
  GET http://orangetb.com/reservation?o_id={O_ID}&selected_date={YYYY-MM-DD}
  파라미터:
    o_id          = 지점 ID (1=대구, 5=대전)
    selected_date = 날짜 (YYYY-MM-DD)
  (theme_code 미지정 시 모든 테마 한번에 반환)

HTML 구조:
  <!-- 테마 탭 버튼에서 t_id 추출 -->
  <button onclick="setTheme(N)">테마명</button>

  <!-- 슬롯 블록 (테마 순서와 1:1) -->
  <ul class="resevation-time">
    <li class="">
      <a href="reservation_form?time_id=NNN?&selected_date=YYYY-MM-DD">
        <h3>HH:MM</h3>
        <p>예약가능</p>
      </a>
    </li>
    <li class="over">
      <a>
        <h3>HH:MM</h3>
        <p>예약마감</p>
      </a>
    </li>
  </ul>

참고:
  - 예약가능: li.class == "" (또는 class 없음)
  - 예약마감: li.class == "over"
  - 날짜 조회 범위: 오늘 ~ +6일 (사이트 maxDate 제한)

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_orangetb_db.py
  uv run python scripts/sync_orangetb_db.py --no-schedule
  uv run python scripts/sync_orangetb_db.py --days 6
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

SITE_URL    = "http://orangetb.com"
RESERVE_URL = SITE_URL + "/reservation"

REQUEST_DELAY = 0.8

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode    = ssl.CERT_NONE

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": SITE_URL,
}

BRANCHES = [
    {
        "cafe_id":     "363716272",
        "o_id":        1,
        "name":        "오렌지티비",
        "branch_name": "대구동성로점",
        "area":        "daegu",
        "address":     "대구 중구 동성로5길 62 4층",
    },
    {
        "cafe_id":     "1908328454",
        "o_id":        5,
        "name":        "오렌지티비",
        "branch_name": "대전은행점",
        "area":        "daejeon",
        "address":     "대전 중구 중앙로156번길24 3층",
    },
]


def _fetch(o_id: int, target_date: date) -> bytes:
    url = RESERVE_URL + "?" + urllib.parse.urlencode({
        "o_id": o_id,
        "selected_date": target_date.strftime("%Y-%m-%d"),
    })
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as r:
            return r.read()
    except Exception as e:
        print(f"  [WARN] GET {url} 실패: {e}")
        return b""


def _parse_themes(html: str) -> list[dict]:
    """
    테마 탭 버튼에서 {t_id, name} 추출 (순서 중요: 슬롯 블록과 1:1 매핑).
    <button onclick="setTheme(N)">테마명</button>
    """
    themes = []
    for m in re.finditer(
        r'onclick=["\']setTheme\((\d+)\)["\'][^>]*>(.*?)</button>',
        html, re.DOTALL
    ):
        t_id = int(m.group(1))
        name = re.sub(r'<[^>]+>', '', m.group(2)).strip()
        if name:
            themes.append({"t_id": t_id, "name": name})
    return themes


def _parse_slots(html: str) -> list[list[dict]]:
    """
    resevation-time ul 블록 목록 추출 (테마 순서와 1:1).
    반환: [[{time, status, time_id}, ...], ...]
    """
    result = []
    ul_pattern = re.compile(
        r'<ul[^>]*class=["\']resevation-time["\'][^>]*>(.*?)</ul>',
        re.DOTALL
    )
    li_pattern = re.compile(
        r'<li([^>]*)>(.*?)</li>',
        re.DOTALL
    )
    time_pattern = re.compile(r'<h3>(\d{1,2}:\d{2})</h3>')
    href_pattern  = re.compile(r'time_id=(\d+)')

    for ul_m in ul_pattern.finditer(html):
        block_slots = []
        for li_m in li_pattern.finditer(ul_m.group(1)):
            li_attrs = li_m.group(1)
            li_body  = li_m.group(2)

            t_m = time_pattern.search(li_body)
            if not t_m:
                continue
            time_str = t_m.group(1)

            # class="over" → 마감
            is_over = 'class="over"' in li_attrs or "class='over'" in li_attrs
            status  = "full" if is_over else "available"

            time_id = None
            if not is_over:
                h_m = href_pattern.search(li_body)
                if h_m:
                    time_id = h_m.group(1)

            block_slots.append({
                "time":    time_str,
                "status":  status,
                "time_id": time_id,
            })
        result.append(block_slots)

    return result


# ── DB 동기화 ──────────────────────────────────────────────────────────────────

def sync_one_branch(branch: dict, days: int) -> None:
    db = get_db()
    cafe_id = branch["cafe_id"]
    o_id    = branch["o_id"]

    upsert_cafe(db, cafe_id, {
        "name":        branch["name"],
        "branch_name": branch["branch_name"],
        "address":     branch["address"],
        "area":        branch["area"],
        "website_url": SITE_URL,
        "engine":      "orangetb",
        "crawled":     True,
        "is_active":   True,
    })
    print(f"  [UPSERT] 카페: {branch['name']} {branch['branch_name']} (id={cafe_id})")

    today      = date.today()
    crawled_at = datetime.now()

    # 첫 날로 테마 목록 초기화
    first_raw = _fetch(o_id, today)
    time.sleep(REQUEST_DELAY)
    if not first_raw:
        print(f"  [ERROR] {branch['branch_name']} 데이터 수집 실패")
        return

    first_html = first_raw.decode("utf-8", errors="replace")
    themes     = _parse_themes(first_html)
    if not themes:
        print(f"  [ERROR] 테마 파싱 실패")
        return

    # t_id → theme_doc_id
    tid_to_doc: dict[int, str] = {}
    for t in themes:
        doc_id = get_or_create_theme(db, cafe_id, t["name"], {
            "poster_url": None,
            "is_active":  True,
        })
        tid_to_doc[t["t_id"]] = doc_id
        print(f"  [UPSERT] 테마: {t['name']} (t_id={t['t_id']})")

    date_themes: dict[str, dict] = {}

    for day_offset in range(min(days, 6) + 1):  # 사이트 maxDate +6d
        target_date = today + timedelta(days=day_offset)
        date_str    = target_date.strftime("%Y-%m-%d")

        if day_offset == 0:
            html = first_html
        else:
            raw = _fetch(o_id, target_date)
            time.sleep(REQUEST_DELAY)
            if not raw:
                continue
            html = raw.decode("utf-8", errors="replace")

        slot_blocks = _parse_slots(html)
        avail = full = 0

        for idx, t in enumerate(themes):
            if idx >= len(slot_blocks):
                break
            doc_id = tid_to_doc[t["t_id"]]
            for slot in slot_blocks[idx]:
                try:
                    hh, mm = int(slot["time"].split(":")[0]), int(slot["time"].split(":")[1])
                except Exception:
                    continue
                slot_dt = datetime(
                    target_date.year, target_date.month, target_date.day, hh, mm
                )
                if slot_dt <= datetime.now():
                    continue

                booking_url = None
                if slot["status"] == "available" and slot["time_id"]:
                    booking_url = (
                        f"{SITE_URL}/reservation_form?"
                        f"time_id={slot['time_id']}&selected_date={date_str}"
                    )

                date_themes.setdefault(date_str, {}).setdefault(
                    doc_id, {"slots": []}
                )["slots"].append({
                    "time":        f"{hh:02d}:{mm:02d}",
                    "status":      slot["status"],
                    "booking_url": booking_url,
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

    for date_str, themes_data in sorted(date_themes.items()):
        h = upsert_cafe_date_schedules(
            db, date_str, cafe_id, themes_data, crawled_at,
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

def main(run_schedule: bool = True, days: int = 6) -> None:
    print("=" * 60)
    print("오렌지티비(orangetb.com) → DB 동기화")
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
    parser = argparse.ArgumentParser(description="오렌지티비 방탈출 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=6, help="오늘부터 며칠치 수집 (기본 6, 최대 6)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
