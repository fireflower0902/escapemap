"""
테라스페이스(teraspace.co.kr) 테마 + 스케줄 DB 동기화 스크립트.

사이트: https://teraspace.co.kr
예약 시스템: 마스터키 PHP 자체 설치 (master-key.co.kr과 동일 엔진, 다른 도메인)

API: POST https://teraspace.co.kr/booking/booking_list_new
  Body: date=YYYY-MM-DD&store={bid}&room=
  응답: HTML (div.box2-inner 단위)
    p.col.true   → 예약 가능 (onclick 속성에 room_id 포함)
    p.col.false  → 예약 불가
    img[src]     → /upload/room/{room_id}_img1.gif

지점 (bid → 카카오 place_id):
  3: 홍대점 (서울 마포구 와우산로19길 9 지하1층) → 759455993

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_teraspace_db.py
  uv run python scripts/sync_teraspace_db.py --no-schedule
  uv run python scripts/sync_teraspace_db.py --days 6
"""

import re
import ssl
import sys
import time
import urllib.request
import urllib.parse
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings
from app.firestore_db import (
    init_firestore, get_db, upsert_cafe,
    get_or_create_theme, upsert_cafe_date_schedules,
    load_cafe_hashes, save_cafe_hashes,
)

SITE_URL = "https://teraspace.co.kr"
API_URL = SITE_URL + "/booking/booking_list_new"
BOOKING_URL_TMPL = SITE_URL + "/booking/bk_detail?bid={bid}"
REQUEST_DELAY = 0.5

BRANCHES = [
    {
        "cafe_id":     "759455993",
        "branch_name": "홍대점",
        "bid":         3,
        "area":        "hongdae",
        "address":     "서울 마포구 와우산로19길 9 지하1층",
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
    "Accept": "*/*",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
}


def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html)


def fetch_slots(bid: int, target_date: date) -> list[dict]:
    """
    날짜별 예약 현황 파싱.
    반환: [{room_id, name, poster_url, time, status}]
    """
    date_str = target_date.strftime("%Y-%m-%d")
    body = urllib.parse.urlencode({"date": date_str, "store": str(bid), "room": ""}).encode()
    headers = {
        **HEADERS,
        "Referer": BOOKING_URL_TMPL.format(bid=bid),
    }
    req = urllib.request.Request(API_URL, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            raw = resp.read()
    except Exception as e:
        print(f"  [WARN] API 호출 실패 bid={bid} date={date_str}: {e}")
        return []

    html = raw.decode("utf-8", errors="replace")
    slots: list[dict] = []

    # div.box2-inner 단위로 분리 (각 테마)
    blocks = re.split(r'<div[^>]+class=["\']box2-inner["\']', html)
    for block in blocks[1:]:
        # room_id: img src에서 추출 (/upload/room/{room_id}_img1.gif)
        m_img = re.search(r'/upload/room/(\d+)_img1\.', block)
        room_id = m_img.group(1) if m_img else None

        # 테마명: div.title
        m_title = re.search(r'<div[^>]+class=["\']title["\'][^>]*>(.*?)</div>', block, re.DOTALL)
        if not m_title:
            continue
        name = _strip_tags(m_title.group(1)).strip()
        if not name:
            continue

        # 포스터
        poster_url = None
        if m_img:
            src = m_img.group(0) if m_img.group(0).startswith("http") else SITE_URL + m_img.group(0)
            # img src 전체를 다시 추출
            m_src = re.search(r'<img[^>]+src=["\']([^"\']+/upload/room/[^"\']+)["\']', block, re.IGNORECASE)
            if m_src:
                src2 = m_src.group(1)
                poster_url = src2 if src2.startswith("http") else SITE_URL + src2

        # 슬롯: p.col.true / p.col.false
        for p_match in re.finditer(r'<p\b([^>]*)>(.*?)</p>', block, re.DOTALL):
            attrs = p_match.group(1)
            p_text = _strip_tags(p_match.group(2)).strip()
            if "col" not in attrs:
                continue

            m_time = re.search(r"(\d{2}):(\d{2})", p_text)
            if not m_time:
                continue
            time_str = f"{m_time.group(1)}:{m_time.group(2)}"

            if "true" in attrs:
                status = "available"
            elif "false" in attrs:
                status = "full"
            else:
                continue

            slots.append({
                "room_id":    room_id,
                "name":       name,
                "poster_url": poster_url,
                "time":       time_str,
                "status":     status,
            })

    return slots


# ── DB 동기화 ─────────────────────────────────────────────────────────────────

def sync_cafe_meta(db, branch: dict) -> None:
    upsert_cafe(db, branch["cafe_id"], {
        "name":        "테라스페이스",
        "branch_name": branch["branch_name"],
        "address":     branch["address"],
        "area":        branch["area"],
        "website_url": SITE_URL,
        "engine":      "teraspace",
        "crawled":     True,
        "is_active":   True,
    })
    print(f"  [UPSERT] 카페: 테라스페이스 {branch['branch_name']} (id={branch['cafe_id']})")


def sync_schedules(days: int = 6) -> None:
    db = get_db()
    today = date.today()
    target_dates = [today + timedelta(days=i) for i in range(days + 1)]
    crawled_at = datetime.now()
    total_writes = 0

    for branch in BRANCHES:
        cafe_id = branch["cafe_id"]
        bid = branch["bid"]
        print(f"\n  {branch['branch_name']} (bid={bid}, id={cafe_id})")

        cafe_doc = db.collection("cafes").document(cafe_id).get()
        if not cafe_doc.exists:
            print(f"  [WARN] cafe {cafe_id} Firestore 미존재 — 건너뜀")
            continue

        # room_id → theme_doc_id 캐시
        theme_cache: dict[str, str] = {}
        date_themes: dict[str, dict] = {}
        booking_url = BOOKING_URL_TMPL.format(bid=bid)

        for target_date in target_dates:
            date_str = target_date.strftime("%Y-%m-%d")
            raw_slots = fetch_slots(bid, target_date)
            time.sleep(REQUEST_DELAY)

            if not raw_slots:
                continue

            avail_cnt = full_cnt = 0

            for slot in raw_slots:
                name = slot["name"]
                room_id = slot.get("room_id") or name

                if room_id not in theme_cache:
                    doc_id = get_or_create_theme(db, cafe_id, name, {
                        "poster_url": slot.get("poster_url"),
                        "is_active":  True,
                    })
                    theme_cache[room_id] = doc_id
                    print(f"  [UPSERT] 테마: {name}")
                theme_doc_id = theme_cache[room_id]

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
                    "booking_url": booking_url if status == "available" else None,
                })

                if status == "available":
                    avail_cnt += 1
                else:
                    full_cnt += 1

            print(f"    {date_str}: 가능 {avail_cnt} / 마감 {full_cnt}")

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
            today_str = date.today().isoformat()
            save_cafe_hashes(db, cafe_id, {
                k: v for k, v in {**known_hashes, **new_hashes}.items()
                if k >= today_str
            })

    print(f"\n  스케줄 동기화 완료: {total_writes}개 날짜 문서 작성")


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main(run_schedule: bool = True, days: int = 6):
    print("=" * 60)
    print("테라스페이스(teraspace.co.kr) → DB 동기화")
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
    parser = argparse.ArgumentParser(description="테라스페이스 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=6, help="오늘부터 며칠치 수집 (기본 6)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
