"""
시크릿코드(secret-code.co.kr) 테마 + 스케줄 DB 동기화 스크립트.

사이트: http://www.secret-code.co.kr  (OG: http://www.s-code.co.kr)
플랫폼: 자체 PHP CMS (JIJEM 코드 기반, 퍼즐팩토리/머더파커와 동일 계열)

지점:
  홍대직영점  JIJEM=S3  cafe_id=280887856  (서울 마포구 어울마당로 66)
  테마: A=#11 백마교의최후, B=#12 제페토, C=#13 독립군, D=#14 조난자들, E=#15 미션

API:
  GET http://www.secret-code.co.kr/sub_02/sub02_1.html
      ?JIJEM=S3&chois_date={YYYY-MM-DD}
  응답: EUC-KR HTML
    class="reservTime" 단위 → 테마 블록
      h3 → 테마명
      a href → 슬롯 링크 (자기 닫힘 태그)
        li > span.time → "HH:MM" (available) 또는 "예약불가" (skip)

예약 URL: http://www.secret-code.co.kr/sub_02/sub02_2.html
          ?JIJEM_CODE=S3&CHOIS_DATE={DATE}&ROOM_CODE={X}&ROOM_TIME={HH:MM}&ROOM_WEEK={주말/평일}

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_secretcode_db.py
  uv run python scripts/sync_secretcode_db.py --no-schedule
  uv run python scripts/sync_secretcode_db.py --days 14
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

SITE_URL = "http://www.secret-code.co.kr"
REV_URL = SITE_URL + "/sub_02/sub02_1.html"
REQUEST_DELAY = 0.8

BRANCHES = [
    {
        "cafe_id":     "280887856",
        "branch_name": "홍대직영점",
        "jijem":       "S3",
        "area":        "hongdae",
        "address":     "서울 마포구 어울마당로 66",
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
    "Referer": SITE_URL + "/sub_02/sub02_1.html",
}


def fetch_rev_page(jijem: str, target_date: date) -> list[dict]:
    """
    날짜별 예약 현황 파싱.
    반환: [{name, slots: [{time, status, booking_url}]}]
    """
    date_str = target_date.strftime("%Y-%m-%d")
    url = f"{REV_URL}?JIJEM={jijem}&chois_date={date_str}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            raw = resp.read()
    except Exception as e:
        print(f"  [WARN] GET {url} 실패: {e}")
        return []

    try:
        html = raw.decode("euc-kr", errors="replace")
    except Exception:
        html = raw.decode("utf-8", errors="replace")

    themes: list[dict] = []

    # reservTime 단위로 테마 블록 분리
    sections = re.split(r'class="reservTime"', html)
    for section in sections[1:]:
        # 테마명: h3 텍스트 (예: "#11[홍대점] 백마교의 최후")
        m_name = re.search(r"<h3[^>]*>([^<]+)", section)
        if not m_name:
            continue
        raw_name = m_name.group(1).strip()
        # "#12[홍대점] 제페토" → "제페토" 형식 or 전체 사용
        name = re.sub(r"^#\d+\[[^\]]+\]\s*", "", raw_name).strip() or raw_name
        if not name:
            continue

        slots: list[dict] = []

        # 슬롯: <a href="/sub_02/sub02_2.html?...ROOM_TIME=HH:MM..." />
        #        <li> ... <span class="time">HH:MM</span> ...
        slot_pairs = re.findall(
            r'href="(/sub_02/sub02_2\.html\?[^"]+)"\s*/>\s*'
            r'<li[^>]*>.*?<span class="time"[^>]*>([^<]+)</span>',
            section,
            re.DOTALL,
        )
        for href, time_text in slot_pairs:
            time_text = time_text.strip()
            if time_text == "예약불가":
                continue  # 예약불가 슬롯 건너뜀
            m_time = re.match(r"(\d{1,2}):(\d{2})", time_text)
            if not m_time:
                continue
            hh, mm = int(m_time.group(1)), int(m_time.group(2))
            booking_url = SITE_URL + href
            slots.append({
                "time":        f"{hh:02d}:{mm:02d}",
                "status":      "available",
                "booking_url": booking_url,
            })

        if slots:
            themes.append({"name": name, "slots": slots})

    return themes


# ── DB 동기화 ─────────────────────────────────────────────────────────────────

def sync_cafe_meta(db, branch: dict) -> None:
    upsert_cafe(db, branch["cafe_id"], {
        "name":        "시크릿코드",
        "branch_name": branch["branch_name"],
        "address":     branch["address"],
        "area":        branch["area"],
        "website_url": SITE_URL,
        "engine":      "secretcode",
        "crawled":     True,
        "is_active":   True,
    })
    print(f"  [UPSERT] 카페: 시크릿코드 {branch['branch_name']} (id={branch['cafe_id']})")


def sync_schedules(days: int = 14) -> None:
    db = get_db()
    today = date.today()
    target_dates = [today + timedelta(days=i) for i in range(days + 1)]
    crawled_at = datetime.now()
    total_writes = 0

    for branch in BRANCHES:
        cafe_id = branch["cafe_id"]
        jijem = branch["jijem"]
        print(f"\n  {branch['branch_name']} (JIJEM={jijem}, id={cafe_id})")

        cafe_doc = db.collection("cafes").document(cafe_id).get()
        if not cafe_doc.exists:
            print(f"  [WARN] cafe {cafe_id} Firestore 미존재 — 건너뜀")
            continue

        theme_cache: dict[str, str] = {}
        date_themes: dict[str, dict] = {}

        for target_date in target_dates:
            date_str = target_date.strftime("%Y-%m-%d")
            themes = fetch_rev_page(jijem, target_date)
            time.sleep(REQUEST_DELAY)

            if not themes:
                print(f"    {date_str}: 데이터 없음")
                continue

            avail_cnt = 0

            for t in themes:
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

                    date_themes.setdefault(date_str, {}).setdefault(
                        theme_doc_id, {"slots": []}
                    )["slots"].append({
                        "time":        f"{hh:02d}:{mm:02d}",
                        "status":      slot["status"],
                        "booking_url": slot.get("booking_url"),
                    })
                    avail_cnt += 1

            print(f"    {date_str}: 가능 {avail_cnt}")

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

    print(f"\n  스케줄 동기화 완료: {total_writes}개 날짜 문서 작성")


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main(run_schedule: bool = True, days: int = 14):
    print("=" * 60)
    print("시크릿코드(secret-code.co.kr) → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)
    db = get_db()

    print("\n[ 1단계 ] 카페 메타 동기화")
    for branch in BRANCHES:
        sync_cafe_meta(db, branch)

    if run_schedule:
        print(f"\n[ 2단계 ] 스케줄 동기화 (오늘~{days}일 후)")
        sync_schedules(days=days)

    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="시크릿코드 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
