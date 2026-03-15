"""
엑스이스케이프(xescape.com) 테마 + 스케줄 DB 동기화 스크립트.

사이트: https://xescape.com
예약 URL: https://xescape.com/web/home.php?go=rev_make&zzcd={zzcd}&rev_days={YYYY-MM-DD}

HTML 구조:
  ul.rev_list > li.list_Box
    .list_name .name_txt        → 테마명
    .poster_img img[src]        → 포스터 (있을 경우)
    ul.time_list > li > a.possible
      p: "HH:MM" + span.ps "예약가능"  → 예약 가능
    a 없거나 다른 class           → 마감

지점 (zzcd → 카카오 place_id):
  20170221002: 홍대놀이터점  (서울 마포구 와우산로21길 20-5)  → 1772415237
  20170223001: 홍대상상마당점 (서울 마포구 어울마당로 70)     → 1654390566

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_xescape_db.py
  uv run python scripts/sync_xescape_db.py --no-schedule
  uv run python scripts/sync_xescape_db.py --days 6
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

SITE_URL = "https://xescape.com"
REV_URL = SITE_URL + "/web/home.php"
REQUEST_DELAY = 0.7

BRANCHES = [
    {
        "cafe_id":     "1772415237",
        "branch_name": "홍대놀이터점",
        "zzcd":        "20170221002",
        "area":        "hongdae",
        "address":     "서울 마포구 와우산로21길 20-5",
    },
    {
        "cafe_id":     "1654390566",
        "branch_name": "홍대상상마당점",
        "zzcd":        "20170223001",
        "area":        "hongdae",
        "address":     "서울 마포구 어울마당로 70",
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
    "Referer": SITE_URL + "/",
}


# ── HTML 파싱 (regex 기반) ────────────────────────────────────────────────────

def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html)


def parse_rev_page(html: str) -> list[dict]:
    """
    엑스이스케이프 예약 페이지 HTML 파싱.
    반환: [{name, poster_url, slots:[{time, status}]}]

    HTML 구조:
      li.list_Box
        p.name_txt  → 테마명
        ul.time_list > li > a.possible (class="possible") → 예약가능
          p 내부: "HH:MM<span class=ps>예약가능</span>"
        ul.time_list > li > a (class 없거나 possible 아님) → 마감
    """
    themes: list[dict] = []

    # li.list_Box 단위로 분리
    blocks = re.split(r'<li[^>]+class="[^"]*list_Box[^"]*"', html)
    for block in blocks[1:]:  # 첫 번째는 li 이전 내용
        # 테마명: p.name_txt
        m_name = re.search(r'<p[^>]+class="[^"]*name_txt[^"]*"[^>]*>(.*?)</p>', block, re.DOTALL)
        if not m_name:
            continue
        name = _strip_tags(m_name.group(1)).strip()
        if not name:
            continue

        # 포스터: 첫 번째 img[src] (list_Area 내)
        poster_url = None
        m_poster = re.search(r'<img[^>]+src="([^"]+/upload/[^"]+)"', block, re.IGNORECASE)
        if m_poster:
            src = m_poster.group(1)
            poster_url = src if src.startswith("http") else SITE_URL + src

        # time_list 블록
        m_tl = re.search(r'<ul[^>]+class="[^"]*time_list[^"]*">(.*?)</ul>', block, re.DOTALL)
        slots: list[dict] = []
        if m_tl:
            tl_html = m_tl.group(1)
            # 각 li 내 a 태그
            for li_html in re.split(r'<li[^>]*>', tl_html)[1:]:
                m_a = re.search(r'<a[^>]+class="([^"]*)"[^>]*>', li_html)
                if not m_a:
                    continue
                a_cls = m_a.group(1)
                # p 내부 텍스트에서 시간 추출
                m_p = re.search(r'<p[^>]*>(.*?)</p>', li_html, re.DOTALL)
                if not m_p:
                    continue
                p_text = _strip_tags(m_p.group(1)).strip()
                m_time = re.search(r"(\d{2}):(\d{2})", p_text)
                if not m_time:
                    continue
                time_str = f"{m_time.group(1)}:{m_time.group(2)}"
                status = "available" if "possible" in a_cls else "full"
                slots.append({"time": time_str, "status": status})

        themes.append({"name": name, "poster_url": poster_url, "slots": slots})

    return themes


def fetch_rev_page(zzcd: str, target_date: date) -> list[dict]:
    """날짜별 예약 현황 HTML 파싱. 반환: [{name, poster_url, slots:[{time,status}]}]"""
    date_str = target_date.strftime("%Y-%m-%d")
    params = urllib.parse.urlencode({"go": "rev_make", "zzcd": zzcd, "rev_days": date_str})
    url = REV_URL + "?" + params
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [WARN] GET {url} 실패: {e}")
        return []

    return parse_rev_page(html)


# ── DB 동기화 ─────────────────────────────────────────────────────────────────

def sync_cafe_meta(db, branch: dict) -> None:
    upsert_cafe(db, branch["cafe_id"], {
        "name":        "엑스이스케이프",
        "branch_name": branch["branch_name"],
        "address":     branch["address"],
        "area":        branch["area"],
        "website_url": SITE_URL,
        "engine":      "xescape",
        "crawled":     True,
        "is_active":   True,
    })
    print(f"  [UPSERT] 카페: 엑스이스케이프 {branch['branch_name']} (id={branch['cafe_id']})")


def sync_schedules(days: int = 6) -> None:
    db = get_db()
    today = date.today()
    target_dates = [today + timedelta(days=i) for i in range(days + 1)]
    crawled_at = datetime.now()
    total_writes = 0

    for branch in BRANCHES:
        cafe_id = branch["cafe_id"]
        zzcd = branch["zzcd"]
        print(f"\n  {branch['branch_name']} (zzcd={zzcd}, id={cafe_id})")

        cafe_doc = db.collection("cafes").document(cafe_id).get()
        if not cafe_doc.exists:
            print(f"  [WARN] cafe {cafe_id} Firestore 미존재 — 건너뜀")
            continue

        # theme name → doc_id 캐시
        theme_cache: dict[str, str] = {}

        # {date_str: {theme_doc_id: {"slots": [...]}}}
        date_themes: dict[str, dict] = {}

        for target_date in target_dates:
            date_str = target_date.strftime("%Y-%m-%d")
            themes = fetch_rev_page(zzcd, target_date)
            time.sleep(REQUEST_DELAY)

            if not themes:
                continue

            avail_cnt = full_cnt = 0

            for t in themes:
                name = t["name"].strip()
                if not name:
                    continue

                # 테마 upsert (캐시)
                if name not in theme_cache:
                    doc_id = get_or_create_theme(db, cafe_id, name, {
                        "poster_url": t.get("poster_url"),
                        "is_active":  True,
                    })
                    theme_cache[name] = doc_id
                    print(f"  [UPSERT] 테마: {name}")
                theme_doc_id = theme_cache[name]

                for slot in t["slots"]:
                    time_str = slot.get("time")
                    if not time_str:
                        continue
                    try:
                        hh, mm = int(time_str[:2]), int(time_str[3:5])
                    except Exception:
                        continue

                    # 과거 슬롯 건너뜀
                    slot_dt = datetime(
                        target_date.year, target_date.month, target_date.day, hh, mm,
                    )
                    if slot_dt <= datetime.now():
                        continue

                    status = slot["status"]
                    booking_url = (
                        f"{REV_URL}?go=rev_make&zzcd={zzcd}&rev_days={date_str}"
                        if status == "available" else None
                    )

                    date_themes.setdefault(date_str, {}).setdefault(
                        theme_doc_id, {"slots": []}
                    )["slots"].append({
                        "time":        f"{hh:02d}:{mm:02d}",
                        "status":      status,
                        "booking_url": booking_url,
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
    print("엑스이스케이프(xescape.com) → DB 동기화")
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
    parser = argparse.ArgumentParser(description="엑스이스케이프 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 건너뜀")
    parser.add_argument("--days", type=int, default=6, help="오늘부터 며칠치 수집 (기본 6)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
