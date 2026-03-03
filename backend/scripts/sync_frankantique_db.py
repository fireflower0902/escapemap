"""
프랭크의골동품가게 테마 + 스케줄 DB 동기화 스크립트.

사이트: https://thefrank.co.kr/
플랫폼: 신비웹(sinbiweb) PHP CMS 자체 예약 시스템

API:
  POST https://thefrank.co.kr/core/res/rev.make.ajax.php
  Content-Type: application/x-www-form-urlencoded

  act=theme&zizum_num=1&theme_num=&rev_days=YYYY-MM-DD
    → 전체 테마 목록 (HTML)
    → a[href] 속성에서 theme_num 추출
    → span 텍스트에서 테마명 추출

  act=theme_img&theme_num={N}
    → 테마 포스터 이미지 URL (HTML img 태그)

  act=time&rev_days=YYYY-MM-DD&theme_num={N}
    → 날짜별 시간대 슬롯 (HTML)
    → a.none → 예약완료(full)
    → a[href] (class 없음) → 예약가능(available)
    → span 텍스트 "10시 30분" 형식에서 시간 파싱

테마 목록 (2026-03-02 기준):
  theme_num=5: My Private Heaven
  theme_num=6: Brooklyn My Love
  theme_num=7: Plan to save my dear

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_frankantique_db.py
  uv run python scripts/sync_frankantique_db.py --no-schedule
  uv run python scripts/sync_frankantique_db.py --days 3
"""

import re
import ssl
import sys
import time
import urllib.request
import urllib.parse
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path

# SSL 인증서 체인 불완전으로 인한 오류 우회
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from bs4 import BeautifulSoup

from app.config import settings
from app.firestore_db import init_firestore, get_db, get_or_create_theme, upsert_cafe_date_schedules

CAFE_ID = "874592991"  # 프랭크의골동품가게 카카오 place_id
AJAX_URL = "https://thefrank.co.kr/core/res/rev.make.ajax.php"
BOOKING_URL = "https://thefrank.co.kr/layout/res/home.php?go=rev.make"
REFERER = "https://thefrank.co.kr/layout/res/home.php?go=rev.make"
ZIZUM_NUM = "1"   # 단일 지점
BASE_IMAGE_URL = "https://thefrank.co.kr"
REQUEST_DELAY = 0.8


def _post(data: dict) -> str:
    """AJAX 엔드포인트에 POST 요청."""
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(
        AJAX_URL,
        data=body,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": REFERER,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as r:
            raw = r.read()
            # 사이트가 EUC-KR 혼용 가능성 있어 UTF-8 우선, 실패 시 euc-kr
            try:
                return raw.decode("utf-8")
            except UnicodeDecodeError:
                return raw.decode("euc-kr", errors="ignore")
    except Exception as e:
        print(f"  [WARN] POST 실패 data={data}: {e}")
        return ""


def _fetch_themes(target_date: date) -> list[dict]:
    """테마 목록 조회.

    반환: [{"theme_num": "5", "name": "My Private Heaven"}, ...]
    """
    html = _post({
        "act": "theme",
        "zizum_num": ZIZUM_NUM,
        "theme_num": "",
        "rev_days": target_date.strftime("%Y-%m-%d"),
    })
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    themes = []
    for a in soup.find_all("a"):
        href = a.get("href", "")
        m = re.search(r"fun_theme_select\('(\d+)'", href)
        if not m:
            continue
        theme_num = m.group(1)
        span = a.find("span")
        name = span.get_text(strip=True) if span else ""
        if theme_num and name:
            themes.append({"theme_num": theme_num, "name": name})
    return themes


def _fetch_poster(theme_num: str) -> str | None:
    """테마 포스터 이미지 URL 조회."""
    html = _post({"act": "theme_img", "theme_num": theme_num})
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    img = soup.find("img")
    if img and img.get("src"):
        src = img["src"]
        if src.startswith("http"):
            return src
        return BASE_IMAGE_URL + src
    return None


def _fetch_slots(theme_num: str, target_date: date) -> list[dict]:
    """날짜별 시간대 슬롯 조회.

    반환: [{"time": dtime(10, 30), "status": "available"}, ...]
    """
    html = _post({
        "act": "time",
        "rev_days": target_date.strftime("%Y-%m-%d"),
        "theme_num": theme_num,
    })
    if not html or "잘못된 접근" in html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    slots = []
    for a in soup.find_all("a"):
        span = a.find("span")
        if not span:
            continue
        # "10시 30분" 또는 "10시 00분" 형식 파싱
        time_text = span.get_text(strip=True)
        m = re.search(r"(\d+)시\s*(\d+)분", time_text)
        if not m:
            continue
        hh, mm = int(m.group(1)), int(m.group(2))

        # 예약 가능 여부: class="none" → full, href 있음 → available
        classes = a.get("class", [])
        href = a.get("href", "")
        if "none" in classes:
            status = "full"
        elif "fun_theme_time_select" in href:
            status = "available"
        else:
            status = "full"  # 예상치 못한 경우 full로 처리

        slots.append({"time": dtime(hh, mm), "status": status})
    return slots


# ── DB 동기화 ──────────────────────────────────────────────────────────────────

def sync_themes() -> dict[str, str]:
    """프랭크의골동품가게 테마를 Firestore에 upsert.

    반환: {theme_num → theme_doc_id}
    """
    db = get_db()

    # 오늘 or 내일 날짜로 테마 목록 조회 (오늘이 지난 경우 대비)
    today = date.today()
    themes_raw = _fetch_themes(today)
    if not themes_raw:
        tomorrow = today + timedelta(days=1)
        themes_raw = _fetch_themes(tomorrow)
    time.sleep(REQUEST_DELAY)

    if not themes_raw:
        print("  [ERROR] 테마 목록 조회 실패")
        return {}

    # 포스터 이미지 수집
    theme_data = []
    for t in themes_raw:
        poster = _fetch_poster(t["theme_num"])
        time.sleep(REQUEST_DELAY)
        theme_data.append({**t, "poster_url": poster})
        print(f"  테마 발견: [{t['theme_num']}] {t['name']} poster={poster}")

    # Firestore upsert
    cafe_doc = db.collection("cafes").document(CAFE_ID).get()
    if not cafe_doc.exists:
        print(f"  [ERROR] cafe {CAFE_ID} Firestore 미존재")
        return {}

    theme_map: dict[str, str] = {}

    for t in theme_data:
        theme_num = t["theme_num"]
        name = t["name"]
        poster_url = t["poster_url"]

        theme_doc_id = get_or_create_theme(db, CAFE_ID, name, {
            "difficulty": None,
            "duration_min": None,
            "poster_url": poster_url,
            "is_active": True,
        })
        theme_map[theme_num] = theme_doc_id
        print(f"  [UPSERT] {name} (theme_num={theme_num})")

    print(f"\n  테마 동기화 완료: {len(theme_map)}개")
    return theme_map


def sync_schedules(theme_map: dict[str, str], days: int = 6):
    """프랭크의골동품가게 스케줄을 Firestore에 upsert (오늘~days일 후)."""
    db = get_db()
    today = date.today()
    target_dates = [today + timedelta(days=i) for i in range(days + 1)]
    crawled_at = datetime.now()
    writes = 0

    # {date_str: {theme_doc_id: {"slots": [...]}}}
    date_themes: dict[str, dict] = {}

    for theme_num, theme_doc_id in theme_map.items():
        for target_date in target_dates:
            slots = _fetch_slots(theme_num, target_date)
            time.sleep(REQUEST_DELAY)

            date_str = target_date.strftime("%Y-%m-%d")
            for slot in slots:
                time_obj = slot["time"]
                status = slot["status"]

                slot_dt = datetime(
                    target_date.year, target_date.month, target_date.day,
                    time_obj.hour, time_obj.minute,
                )
                if slot_dt <= datetime.now():
                    continue

                booking_url = BOOKING_URL if status == "available" else None

                date_themes.setdefault(date_str, {}).setdefault(theme_doc_id, {"slots": []})["slots"].append({
                    "time": f"{time_obj.hour:02d}:{time_obj.minute:02d}",
                    "status": status,
                    "booking_url": booking_url,
                })

        print(f"  theme_num={theme_num} 완료")

    for date_str, themes in date_themes.items():
        upsert_cafe_date_schedules(db, date_str, CAFE_ID, themes, crawled_at)
        writes += 1

    print(f"\n  스케줄 동기화 완료: {writes}개 날짜 문서 작성")


def main(run_schedule: bool = True, days: int = 6):
    print("=" * 60)
    print("프랭크의골동품가게 → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)

    print("\n[ 1단계 ] 테마 동기화")
    theme_map = sync_themes()
    print(f"  theme_num 매핑: {theme_map}")

    if run_schedule and theme_map:
        print(f"\n[ 2단계 ] 스케줄 동기화 (오늘~{days}일 후)")
        sync_schedules(theme_map, days=days)

    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="프랭크의골동품가게 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true", help="테마만 동기화, 스케줄 생략")
    parser.add_argument("--days", type=int, default=6, help="오늘 포함 몇 일치 스케줄 수집 (기본 6)")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
