"""
머더파커(murderparker.com) 테마 + 스케줄 DB 동기화 스크립트.

사이트: http://murderparker.com
플랫폼: 자체 PHP (EUC-KR)

API: POST http://murderparker.com/sub_02/sub02_1.html
  Body: JIJEM=S11&H_Date=YYYY-MM-DD  (EUC-KR 인코딩)
  응답: EUC-KR HTML
    div.reservTime → 테마 블록
    h3 → 테마명
    img[src^=/upload_file/room/] → 포스터
    a[href^=/sub_02/sub02_2.html] → 예약가능 (href에 ROOM_TIME 파라미터)
    li[style*="border: 1px solid #222"] → 예약가능 슬롯
    li[style*="border: 1px solid #757575"] → 예약마감 슬롯

지점:
  잠실점  cafe_id=1796437751  JIJEM=S11  (서울 송파구 올림픽로35다길 14 지하 1층)

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_murderparker_db.py
  uv run python scripts/sync_murderparker_db.py --no-schedule
  uv run python scripts/sync_murderparker_db.py --days 14
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

SITE_URL = "http://murderparker.com"
SLOT_API_URL = SITE_URL + "/sub_02/sub02_1.html"
BOOKING_BASE_URL = SITE_URL + "/sub_02/sub02_2.html"
REQUEST_DELAY = 0.7

CAFE_ID = "1796437751"
JIJEM_CODE = "S11"

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Content-Type": "application/x-www-form-urlencoded",
    "Referer": SITE_URL + "/sub_02/sub02_1.html",
}


def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html)


def fetch_slots(target_date: date) -> list[dict]:
    """날짜별 슬롯 조회. 반환: [{name, poster_url, slots: [{time, status, booking_url}]}]"""
    date_str = target_date.strftime("%Y-%m-%d")
    # EUC-KR 인코딩으로 POST body 구성
    body_str = f"JIJEM={JIJEM_CODE}&H_Date={date_str}"
    body = body_str.encode("euc-kr")
    req = urllib.request.Request(SLOT_API_URL, data=body, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            html = resp.read().decode("euc-kr", errors="replace")
    except Exception as e:
        print(f"  [WARN] POST 실패 (date={date_str}): {e}")
        return []

    themes: list[dict] = []

    # 테마 블록 분리 (div.reservTime 기준)
    blocks = re.split(r'<div\s+class=["\']reservTime["\']', html)
    for block in blocks[1:]:
        # 테마명: h3 태그
        m_name = re.search(r'<h3[^>]*>\s*(.*?)\s*</h3>', block, re.DOTALL)
        if not m_name:
            continue
        name = _strip_tags(m_name.group(1)).strip()
        if not name:
            continue

        # 포스터: /upload_file/room/ 경로
        poster_url = None
        m_img = re.search(r'<img[^>]+src=["\'](/upload_file/room/[^"\']+)["\']', block)
        if m_img:
            poster_url = SITE_URL + m_img.group(1)

        slots: list[dict] = []

        # 슬롯 추출: a 태그 + li 태그 쌍으로 파싱
        # 예약가능: a[href=/sub_02/sub02_2.html?...ROOM_TIME=HH:MM...] + li[style*="1px solid #222"]
        # 예약마감: a[href=#] + li[style*="1px solid #757575"]
        # li 블록 단위로 파싱
        li_pattern = re.compile(
            r'<a\s+href=["\']([^"\']*)["\'][^>]*>\s*<li\s+style=["\']([^"\']*)["\'][^>]*>.*?</li>',
            re.DOTALL
        )

        for m_li in li_pattern.finditer(block):
            href = m_li.group(1).strip()
            style = m_li.group(2).strip()
            li_content = m_li.group(0)

            # 시간 추출 - span.time 또는 href의 ROOM_TIME 파라미터
            time_str = None

            # href에서 ROOM_TIME 파라미터 추출 (예약가능 슬롯)
            m_room_time = re.search(r'ROOM_TIME=(\d{2}:\d{2})', href)
            if m_room_time:
                time_str = m_room_time.group(1)
            else:
                # span.time에서 시간 추출
                m_span_time = re.search(
                    r'<span[^>]*class=["\'][^"\']*time[^"\']*["\'][^>]*>([^<]+)</span>',
                    li_content
                )
                if m_span_time:
                    t_raw = _strip_tags(m_span_time.group(1)).strip()
                    m_t = re.match(r"(\d{1,2}):(\d{2})", t_raw)
                    if m_t:
                        time_str = f"{int(m_t.group(1)):02d}:{int(m_t.group(2)):02d}"

            if not time_str:
                continue

            # 상태 판별
            if "1px solid #222" in style and href.startswith("/sub_02/sub02_2.html"):
                status = "available"
                booking_url = SITE_URL + href
            elif "1px solid #757575" in style:
                status = "full"
                booking_url = None
            else:
                continue

            slots.append({"time": time_str, "status": status, "booking_url": booking_url})

        if slots:
            themes.append({"name": name, "poster_url": poster_url, "slots": slots})

    return themes


# ── DB 동기화 ─────────────────────────────────────────────────────────────────

def sync_cafe_meta(db) -> None:
    upsert_cafe(db, CAFE_ID, {
        "name":        "머더파커",
        "branch_name": "잠실점",
        "address":     "서울 송파구 올림픽로35다길 14 지하 1층",
        "area":        "jamsil",
        "website_url": SITE_URL,
        "engine":      "murderparker",
        "crawled":     True,
        "is_active":   True,
    })
    print(f"  [UPSERT] 카페: 머더파커 잠실점 (id={CAFE_ID})")


def sync_schedules(days: int = 14) -> None:
    db = get_db()
    today = date.today()
    target_dates = [today + timedelta(days=i) for i in range(days + 1)]
    crawled_at = datetime.now()
    total_writes = 0

    cafe_doc = db.collection("cafes").document(CAFE_ID).get()
    if not cafe_doc.exists:
        print(f"  [WARN] cafe {CAFE_ID} Firestore 미존재 — 건너뜀")
        return

    theme_cache: dict[str, str] = {}
    date_themes: dict[str, dict] = {}

    for target_date in target_dates:
        date_str = target_date.strftime("%Y-%m-%d")
        raw_themes = fetch_slots(target_date)
        time.sleep(REQUEST_DELAY)

        if not raw_themes:
            print(f"  {date_str}: 데이터 없음")
            continue

        avail_cnt = full_cnt = 0

        for t in raw_themes:
            name = t["name"]
            if name not in theme_cache:
                doc_id = get_or_create_theme(db, CAFE_ID, name, {
                    "poster_url": t.get("poster_url"),
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

    known_hashes = load_cafe_hashes(db, CAFE_ID)
    new_hashes: dict[str, str] = {}
    for date_str, themes_map in date_themes.items():
        h = upsert_cafe_date_schedules(
            db, date_str, CAFE_ID, themes_map, crawled_at,
            known_hash=known_hashes.get(date_str),
        )
        if h:
            new_hashes[date_str] = h
            total_writes += 1

    if new_hashes:
        today_str = today.isoformat()
        save_cafe_hashes(db, CAFE_ID, {
            k: v for k, v in {**known_hashes, **new_hashes}.items()
            if k >= today_str
        })

    print(f"  스케줄 동기화 완료: {total_writes}개 날짜 문서 작성")


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main(run_schedule: bool = True, days: int = 14):
    print("=" * 60)
    print("머더파커(murderparker.com) → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)
    db = get_db()

    print("\n[ 1단계 ] 카페 메타 동기화")
    sync_cafe_meta(db)

    if run_schedule:
        print(f"\n[ 2단계 ] 스케줄 동기화 (오늘~{days}일 후)")
        sync_schedules(days=days)

    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="머더파커 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
