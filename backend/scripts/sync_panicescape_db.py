"""
패닉이스케이프(panicescape.com) 테마 + 스케줄 DB 동기화 스크립트.

사이트: http://www.panicescape.com
플랫폼: 자체 PHP (서버사이드 렌더링)

지점:
  목동점  cafe_id=27178625  area=etc  (서울 양천구 목동)

API:
  GET http://www.panicescape.com/pre_engage?date={YYYY-MM-DD}
  응답 HTML:
    div.panel.panel-default.col-sm-2.col-md-2 → 테마 패널
    예약가능: <a href="#" onclick="theme_change('pre-engage','HH:MM',price,'테마명')">HH:MM (예약하기)</a>
    예약마감: <td ... style="color:#ddd;">매진</td>
    오픈준비중: <td ... style="color:#ddd;">오픈준비중</td>

예약 URL: http://www.panicescape.com/pre_engage (직접 링크 없음)

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_panicescape_db.py
  uv run python scripts/sync_panicescape_db.py --no-schedule
  uv run python scripts/sync_panicescape_db.py --days 14
"""

import re
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

SITE_URL = "http://www.panicescape.com"
REQUEST_DELAY = 0.8

BRANCHES = [
    {
        "cafe_id":     "27178625",
        "branch_name": "목동점",
        "area":        "etc",
        "address":     "서울 양천구 목동동로 343 3층",
    },
]

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
    url = f"{SITE_URL}/pre_engage?date={date_str}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [WARN] GET {url} 실패: {e}")
        return ""


def parse_page(html: str) -> list[dict]:
    """
    예약 페이지 HTML 파싱.
    반환: [{time, status, theme_name}]
    """
    slots: list[dict] = []

    # 예약가능: onclick="theme_change('pre-engage','HH:MM',price,'테마명')"
    avail_pattern = re.compile(
        r"""theme_change\('pre-engage',\s*'(\d{2}:\d{2})',\s*[^,]+,\s*'([^']+)'\)"""
    )
    for m in avail_pattern.finditer(html):
        time_str = m.group(1)
        theme_name = m.group(2).strip()
        slots.append({"time": time_str, "status": "available", "theme_name": theme_name})

    # 예약마감: style="color:#ddd;">매진</td>
    # 매진 슬롯의 테마명과 시간 추출 — 이전 panel 컨텍스트 기반 파싱
    # panel 단위로 분리: <div class="panel panel-default ...">...</div>
    panel_pattern = re.compile(
        r'<div[^>]+class="[^"]*panel[^"]*panel-default[^"]*"[^>]*>(.*?)</div>\s*</div>',
        re.DOTALL,
    )
    for panel in panel_pattern.finditer(html):
        panel_html = panel.group(1)

        # 테마명: 패널 헤더 텍스트
        m_title = re.search(r'<div[^>]+class="[^"]*panel-heading[^"]*"[^>]*>([^<]+)', panel_html)
        if not m_title:
            continue
        theme_name = m_title.group(1).strip()

        # 매진 슬롯: style="color:#ddd;">매진</td> 앞 시간
        # 일반 패턴: <td ...>HH:MM</td><td ... style="color:#ddd;">매진</td>
        full_pattern = re.compile(
            r'<td[^>]*>\s*(\d{2}:\d{2})\s*</td>\s*<td[^>]+style="[^"]*color:\s*#ddd[^"]*"[^>]*>매진</td>',
            re.DOTALL,
        )
        for mf in full_pattern.finditer(panel_html):
            time_str = mf.group(1)
            # Only add if not already in slots (avoid duplicate available entries)
            slots.append({"time": time_str, "status": "full", "theme_name": theme_name})

    return slots


# ── DB 동기화 ─────────────────────────────────────────────────────────────────

def sync_cafe_meta(db, branch: dict) -> None:
    upsert_cafe(db, branch["cafe_id"], {
        "name":        "패닉이스케이프",
        "branch_name": branch["branch_name"],
        "address":     branch["address"],
        "area":        branch["area"],
        "website_url": SITE_URL,
        "engine":      "panicescape",
        "crawled":     True,
        "is_active":   True,
    })
    print(f"  [UPSERT] 카페: 패닉이스케이프 {branch['branch_name']} (id={branch['cafe_id']})")


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

        raw_slots = parse_page(raw_html)
        if not raw_slots:
            print(f"  {date_str}: 슬롯 없음")
            continue

        avail_cnt = full_cnt = 0

        for slot in raw_slots:
            time_str = slot["time"]
            theme_name = slot["theme_name"]
            status = slot["status"]

            try:
                hh, mm = int(time_str[:2]), int(time_str[3:5])
            except Exception:
                continue

            slot_dt = datetime(
                target_date.year, target_date.month, target_date.day, hh, mm,
            )
            if slot_dt <= datetime.now():
                continue

            if theme_name not in theme_cache:
                doc_id = get_or_create_theme(db, cafe_id, theme_name, {
                    "poster_url": None,
                    "is_active":  True,
                })
                theme_cache[theme_name] = doc_id
                print(f"  [UPSERT] 테마: {theme_name}")
            theme_doc_id = theme_cache[theme_name]

            date_themes.setdefault(date_str, {}).setdefault(
                theme_doc_id, {"slots": []}
            )["slots"].append({
                "time":        f"{hh:02d}:{mm:02d}",
                "status":      status,
                "booking_url": SITE_URL + "/pre_engage" if status == "available" else None,
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
    print("패닉이스케이프(panicescape.com) → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)
    db = get_db()

    print("\n[ 1단계 ] 카페 메타 동기화")
    for branch in BRANCHES:
        sync_cafe_meta(db, branch)

    if run_schedule:
        for branch in BRANCHES:
            print(f"\n[ 2단계 ] {branch['branch_name']} 스케줄 동기화 (오늘~{days}일 후)")
            sync_branch(branch, days=days)

    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="패닉이스케이프 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
