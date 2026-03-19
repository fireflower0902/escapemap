"""
레다스퀘어(ledasquare.com) 테마 + 스케줄 DB 동기화 스크립트.

사이트: https://ledasquare.com
플랫폼: sinbiweb 기반 커스텀 AJAX (GET rev.make는 JS shell만 반환 — AJAX 직접 호출 필요)

지점:
  홍대점  cafe_id=28201117  area=hongdae  (서울 마포구 독막로9길 23)

API:
  POST https://ledasquare.com/core/res/rev.make.sel.php
  Body:
    Step 1 (테마 목록): act=theme_list&zizum_num=1&rev_days={YYYY-MM-DD}&theme_num=
      응답 HTML: <a href="javascript:fun_theme_select('{theme_num}','{i}')"> → theme_num 추출
    Step 2 (슬롯): act=theme_time_list&zizum_num=1&rev_days={YYYY-MM-DD}&theme_num={N}
      응답 HTML:
        <a href="javascript:fun_theme_time_select(...)"><span>HH:MM</span></a> → 예약가능
        <a class="none"><span>HH:MM</span></a> → 예약마감

예약 URL: https://ledasquare.com/layout/res/home.php?go=rev.make

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_ledasquare_db.py
  uv run python scripts/sync_ledasquare_db.py --no-schedule
  uv run python scripts/sync_ledasquare_db.py --days 14
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

SITE_URL = "https://ledasquare.com"
API_URL = SITE_URL + "/core/res/rev.make.sel.php"
REQUEST_DELAY = 0.8

BRANCHES = [
    {
        "cafe_id":   "28201117",
        "branch_name": "홍대점",
        "area":      "hongdae",
        "address":   "서울 마포구 독막로9길 23",
        "zizum_num": "1",
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
    "Content-Type": "application/x-www-form-urlencoded",
    "Referer": SITE_URL + "/layout/res/home.php?go=rev.make",
    "X-Requested-With": "XMLHttpRequest",
}


def _post(body: dict) -> str:
    data = urllib.parse.urlencode(body).encode()
    req = urllib.request.Request(API_URL, data=data, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [WARN] POST 실패: {e}")
        return ""


def get_theme_nums(zizum_num: str, target_date: date) -> list[str]:
    """테마 번호 목록 조회."""
    date_str = target_date.strftime("%Y-%m-%d")
    html = _post({
        "act": "theme_list",
        "zizum_num": zizum_num,
        "rev_days": date_str,
        "theme_num": "",
    })
    return re.findall(r"fun_theme_select\('(\d+)'", html)


def get_slots(zizum_num: str, theme_num: str, target_date: date) -> list[dict]:
    """슬롯 목록 조회. 반환: [{time, status}]"""
    date_str = target_date.strftime("%Y-%m-%d")
    html = _post({
        "act": "theme_time_list",
        "zizum_num": zizum_num,
        "rev_days": date_str,
        "theme_num": theme_num,
    })
    slots = []

    # 가용: <a href="javascript:fun_theme_time_select(...)"><span>HH:MM</span></a>
    avail_pattern = re.compile(
        r'<a\s+href="javascript:fun_theme_time_select[^"]*"[^>]*>.*?<span[^>]*>(\d{2}:\d{2})</span>',
        re.DOTALL,
    )
    for m in avail_pattern.finditer(html):
        slots.append({"time": m.group(1), "status": "available"})

    # 마감: <a class="none"...><span>HH:MM</span></a>
    full_pattern = re.compile(
        r'<a[^>]+class="[^"]*none[^"]*"[^>]*>.*?<span[^>]*>(\d{2}:\d{2})</span>',
        re.DOTALL,
    )
    for m in full_pattern.finditer(html):
        slots.append({"time": m.group(1), "status": "full"})

    return slots


def get_theme_name_from_list(zizum_num: str, theme_num: str, target_date: date) -> str | None:
    """테마 목록 HTML에서 특정 theme_num의 이름 추출."""
    date_str = target_date.strftime("%Y-%m-%d")
    html = _post({
        "act": "theme_list",
        "zizum_num": zizum_num,
        "rev_days": date_str,
        "theme_num": "",
    })
    # <a href="javascript:fun_theme_select('{theme_num}','{i}')">테마명</a>
    m = re.search(
        rf"fun_theme_select\('{re.escape(theme_num)}'[^)]*\)[^>]*>([^<]+)</a>",
        html,
    )
    if m:
        return m.group(1).strip()
    return None


# ── DB 동기화 ─────────────────────────────────────────────────────────────────

def sync_cafe_meta(db, branch: dict) -> None:
    upsert_cafe(db, branch["cafe_id"], {
        "name":        "레다스퀘어",
        "branch_name": branch["branch_name"],
        "address":     branch["address"],
        "area":        branch["area"],
        "website_url": SITE_URL,
        "engine":      "ledasquare",
        "crawled":     True,
        "is_active":   True,
    })
    print(f"  [UPSERT] 카페: 레다스퀘어 {branch['branch_name']} (id={branch['cafe_id']})")


def sync_branch(branch: dict, days: int = 14) -> int:
    db = get_db()
    cafe_id = branch["cafe_id"]
    zizum_num = branch["zizum_num"]
    today = date.today()
    target_dates = [today + timedelta(days=i) for i in range(days + 1)]
    crawled_at = datetime.now()
    total_writes = 0

    cafe_doc = db.collection("cafes").document(cafe_id).get()
    if not cafe_doc.exists:
        print(f"  [WARN] cafe {cafe_id} Firestore 미존재 — 건너뜀")
        return 0

    # 테마 목록 및 이름 수집 (가장 가까운 날짜 사용)
    theme_num_to_name: dict[str, str] = {}
    for i in range(8):
        target = today + timedelta(days=i)
        theme_nums = get_theme_nums(zizum_num, target)
        time.sleep(REQUEST_DELAY)
        if theme_nums:
            html = _post({
                "act": "theme_list",
                "zizum_num": zizum_num,
                "rev_days": target.strftime("%Y-%m-%d"),
                "theme_num": "",
            })
            # 테마명 추출: fun_theme_select 뒤 텍스트
            for tn in theme_nums:
                if tn not in theme_num_to_name:
                    m = re.search(
                        rf"fun_theme_select\('{re.escape(tn)}'[^)]*\)[^>]*>([^<]+)</a>",
                        html,
                    )
                    if m:
                        theme_num_to_name[tn] = m.group(1).strip()
            if theme_num_to_name:
                break

    if not theme_num_to_name:
        print(f"  [{branch['branch_name']}] 테마 정보를 찾을 수 없음, 건너뜀.")
        return 0

    # 테마 upsert
    theme_doc_map: dict[str, str] = {}
    for tn, tname in theme_num_to_name.items():
        doc_id = get_or_create_theme(db, cafe_id, tname, {
            "poster_url": None,
            "is_active":  True,
        })
        theme_doc_map[tn] = doc_id
        print(f"  [UPSERT] 테마: {tname} (theme_num={tn})")

    # 스케줄 upsert
    known_hashes = load_cafe_hashes(db, cafe_id)
    new_hashes: dict[str, str] = {}
    date_themes: dict[str, dict] = {}

    for target_date in target_dates:
        date_str = target_date.strftime("%Y-%m-%d")
        avail_cnt = full_cnt = 0

        for tn, doc_id in theme_doc_map.items():
            slots = get_slots(zizum_num, tn, target_date)
            time.sleep(REQUEST_DELAY)

            for slot in slots:
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
                    doc_id, {"slots": []}
                )["slots"].append({
                    "time":        f"{hh:02d}:{mm:02d}",
                    "status":      status,
                    "booking_url": SITE_URL + "/layout/res/home.php?go=rev.make" if status == "available" else None,
                })
                if status == "available":
                    avail_cnt += 1
                else:
                    full_cnt += 1

        print(f"  {date_str}: 가능 {avail_cnt} / 마감 {full_cnt}")

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
    print("레다스퀘어(ledasquare.com) → DB 동기화")
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
    parser = argparse.ArgumentParser(description="레다스퀘어 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=14, help="오늘부터 며칠치 수집 (기본 14)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
