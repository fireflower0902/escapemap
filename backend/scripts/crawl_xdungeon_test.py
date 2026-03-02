"""
xdungeon.net (비트포비아 던전 시리즈) 크롤링 테스트 스크립트

대상 지점 (s_zizum ID → 카카오 place_id):
  1: 던전101       → 1772808576
  2: 강남던전       → 27413263
  3: 홍대던전       → 1246652450
  4: 강남던전Ⅱ     → 1769092819
  5: 홍대던전Ⅲ     → 2070160321
  6: 던전루나(강남) → 1478483341
  7: 서면던전(부산) → 1322241204
  9: 던전스텔라(강남)→ 436025860
 10: 서면던전 레드  → 629764977

API 구조:
  [테마 목록]   GET home.php?go=theme.list&s_zizum={ID}
  [테마 상세]   POST core/res/theme.act.php  data: not_html=Y&act=view&num={THEME_ID}
  [스케줄]      GET home.php?go=rev.main&s_zizum={ID}&rev_days={YYYY-MM-DD}

예약 가능 슬롯 판별:
  li.sale (dead 없음) → 예약 가능
  li.dead.sale        → 마감(매진)
  li 기타             → 비운영

실행:
  cd escape-aggregator/backend
  python scripts/crawl_xdungeon_test.py
"""

import sys
import time
from datetime import date, timedelta
from pathlib import Path
import re

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://xdungeon.net/layout/res/home.php"
THEME_ACT_URL = "https://xdungeon.net/core/res/theme.act.php"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://xdungeon.net/layout/res/home.php?go=rev.main",
}

REQUEST_DELAY = 0.5  # 초

# 지점 ID 매핑: s_zizum → (지점명, 카카오 place_id)
BRANCH_MAP = {
    1:  ("던전101",         "1772808576"),
    2:  ("강남던전",         "27413263"),
    3:  ("홍대던전",         "1246652450"),
    4:  ("강남던전Ⅱ",       "1769092819"),
    5:  ("홍대던전Ⅲ",       "2070160321"),
    6:  ("던전루나(강남)",   "1478483341"),
    7:  ("서면던전(부산)",   "1322241204"),
    9:  ("던전스텔라(강남)", "436025860"),
    10: ("서면던전 레드",    "629764977"),
}


# ── 테마 목록 수집 ─────────────────────────────────────────────────────────────

def fetch_themes_for_branch(zizum_id: int) -> list[dict]:
    """지점의 테마 목록 반환.

    Returns:
        [{"theme_id": "49", "name": "3일", "branch": "던전루나(강남)",
          "difficulty": "NORMAL", "genre": "추리"}, ...]
    """
    resp = requests.get(
        BASE_URL,
        params={"go": "theme.list", "s_zizum": zizum_id},
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    themes = []
    for li in soup.find_all("li"):
        link = li.find("a", href=lambda h: h and "_fun_theme_view" in str(h))
        if not link:
            continue
        m = re.search(r"_fun_theme_view\('(\d+)'\)", link["href"])
        if not m:
            continue
        theme_id = m.group(1)
        name = li.find("p", class_="thm")
        branch = li.find("span", class_="str")
        level = li.find("span", class_="lv")
        genre = li.find("span", class_="gr")

        themes.append({
            "theme_id": theme_id,
            "name": name.get_text(strip=True) if name else "",
            "branch": branch.get_text(strip=True) if branch else "",
            "difficulty": level.get_text(strip=True) if level else "",
            "genre": genre.get_text(strip=True) if genre else "",
        })
    return themes


def fetch_theme_detail(theme_id: str) -> dict:
    """테마 상세 정보 반환 (플레이타임, 시놉시스 등).

    Returns:
        {"play_time": "75분", "difficulty": "NORMAL", "genre": "추리",
         "branch": "던전루나(강남)", "synopsis": "...", "notes": "..."}
    """
    resp = requests.post(
        THEME_ACT_URL,
        data=f"not_html=Y&act=view&num={theme_id}&ck_rev_but=N",
        headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    detail = {}
    for dl in soup.find_all("dl"):
        dt = dl.find("dt")
        dd = dl.find("dd")
        if not dt or not dd:
            continue
        key = dt.get_text(strip=True)
        val = dd.get_text(separator=" ", strip=True)
        key_map = {
            "지점명": "branch",
            "플레이타임": "play_time",
            "난이도": "difficulty",
            "장르": "genre",
            "테마명": "theme_name",
            "시놉시스": "synopsis",
            "특이사항": "notes",
        }
        if key in key_map:
            detail[key_map[key]] = val
    return detail


# ── 스케줄(예약 가능 시간) 수집 ───────────────────────────────────────────────

def fetch_schedule(zizum_id: int, target_date: date) -> list[dict]:
    """특정 날짜의 스케줄 반환.

    Returns:
        [{"theme_id": "49", "theme_name": "3일",
          "slots": [{"time": "22:35", "available": True}, ...]}, ...]
    """
    resp = requests.get(
        BASE_URL,
        params={
            "go": "rev.main",
            "s_zizum": zizum_id,
            "rev_days": target_date.strftime("%Y-%m-%d"),
        },
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    results = []
    container = soup.find("div", class_="thm_box")
    if not container:
        return results

    for box in container.find_all("div", class_="box"):
        # 테마명
        tit = box.find("p", class_="tit")
        theme_name = tit.get_text(strip=True) if tit else ""

        # 테마 ID
        img_link = box.find("a", href=lambda h: h and "_fun_theme_view" in str(h))
        theme_id = None
        if img_link:
            m = re.search(r"_fun_theme_view\('(\d+)'\)", img_link["href"])
            theme_id = m.group(1) if m else None

        # 시간 슬롯 파싱
        time_box = box.find("div", class_="time_box")
        slots = []
        if time_box:
            # 예약 오픈 전 메시지 확인
            msg = time_box.find("div", class_="rev_make_text")
            if msg:
                # 예약 오픈 전 or 날짜 범위 초과
                slots = []
            else:
                for li in time_box.find_all("li"):
                    classes = li.get("class", [])
                    is_sale = "sale" in classes
                    is_dead = "dead" in classes

                    # 시간 추출: <span>SALE</span>09:30 구조에서 HH:MM만 추출
                    a_tag = li.find("a")
                    if not a_tag:
                        continue
                    # span 제거 후 텍스트 추출 (HH:MM 형식)
                    for span in a_tag.find_all("span"):
                        span.decompose()
                    t = a_tag.get_text(strip=True)
                    if not t or ":" not in t:
                        continue

                    if is_sale and not is_dead:
                        status = "available"
                    elif is_sale and is_dead:
                        status = "sold_out"
                    else:
                        status = "closed"

                    # 예약 링크 (available일 때만 존재)
                    booking_href = a_tag.get("href", "")

                    slots.append({"time": t, "status": status, "booking_url": booking_href})

        results.append({
            "theme_id": theme_id,
            "theme_name": theme_name,
            "slots": slots,
        })

    return results


# ── 메인 테스트 ────────────────────────────────────────────────────────────────

def test_themes():
    """모든 지점의 테마 목록 + 상세 정보 출력"""
    print("=" * 70)
    print("[ 1단계 ] 전 지점 테마 목록 수집")
    print("=" * 70)

    all_themes = {}  # theme_id → detail
    for zizum_id, (branch_name, place_id) in BRANCH_MAP.items():
        print(f"\n  ▷ {branch_name} (s_zizum={zizum_id})")
        try:
            themes = fetch_themes_for_branch(zizum_id)
            for t in themes:
                print(f"    · [{t['theme_id']}] {t['name']} | {t['difficulty']} | {t['genre']}")
                all_themes[t["theme_id"]] = t
        except Exception as e:
            print(f"    ✗ 오류: {e}")
        time.sleep(REQUEST_DELAY)

    print(f"\n  총 테마 수: {len(all_themes)}개")
    return all_themes


def test_theme_details(all_themes: dict):
    """테마 상세 정보(플레이타임 등) 수집"""
    print("\n" + "=" * 70)
    print("[ 2단계 ] 테마 상세 정보 수집 (플레이타임 포함)")
    print("=" * 70)

    for theme_id, theme in all_themes.items():
        try:
            detail = fetch_theme_detail(theme_id)
            play_time = detail.get("play_time", "?")
            synopsis_short = detail.get("synopsis", "")[:50]
            print(f"  [{theme_id}] {theme['name']} ({theme['branch']}) — {play_time} / {synopsis_short}...")
        except Exception as e:
            print(f"  [{theme_id}] ✗ 오류: {e}")
        time.sleep(REQUEST_DELAY)


def test_schedule(target_branches: list[int] | None = None, days_ahead: int = 3):
    """지점별 스케줄 수집 (오늘 기준 days_ahead일까지)"""
    print("\n" + "=" * 70)
    print(f"[ 3단계 ] 스케줄 수집 (오늘~{days_ahead}일 후)")
    print("=" * 70)

    branches = target_branches or list(BRANCH_MAP.keys())
    today = date.today()
    dates = [today + timedelta(days=i) for i in range(days_ahead + 1)]

    available_summary = []

    for zizum_id in branches:
        branch_name, place_id = BRANCH_MAP[zizum_id]
        print(f"\n  ▷ {branch_name} (s_zizum={zizum_id})")

        for d in dates:
            try:
                schedule = fetch_schedule(zizum_id, d)
                if not schedule:
                    print(f"    {d} — 데이터 없음")
                    continue

                for theme_sched in schedule:
                    available = [s for s in theme_sched["slots"] if s["status"] == "available"]
                    sold_out = [s for s in theme_sched["slots"] if s["status"] == "sold_out"]
                    total = len(theme_sched["slots"])

                    if not theme_sched["slots"]:
                        status_str = "예약 오픈 전"
                    else:
                        avail_times = [s["time"] for s in available]
                        status_str = f"가능 {len(available)}/{total} {avail_times}"

                    print(f"    {d} [{theme_sched['theme_name']}] {status_str}")

                    if available:
                        available_summary.append({
                            "branch": branch_name,
                            "date": str(d),
                            "theme": theme_sched["theme_name"],
                            "available_slots": [s["time"] for s in available],
                        })

            except Exception as e:
                print(f"    {d} — ✗ 오류: {e}")
            time.sleep(REQUEST_DELAY)

    print("\n" + "=" * 70)
    print("[ 예약 가능 슬롯 요약 ]")
    print("=" * 70)
    if not available_summary:
        print("  예약 가능한 슬롯 없음")
    for item in available_summary:
        print(f"  {item['date']} | {item['branch']} | {item['theme']} → {', '.join(item['available_slots'])}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="xdungeon.net 크롤링 테스트")
    parser.add_argument("--mode", choices=["themes", "schedule", "all"], default="all",
                        help="실행 모드: themes(테마만), schedule(스케줄만), all(전체)")
    parser.add_argument("--branch", type=int, nargs="*",
                        help=f"대상 지점 ID (기본: 전체). 예: --branch 6 9")
    parser.add_argument("--days", type=int, default=3,
                        help="스케줄 조회 일수 (기본: 3일)")
    args = parser.parse_args()

    if args.mode in ("themes", "all"):
        all_themes = test_themes()
        if args.mode == "all":
            test_theme_details(all_themes)

    if args.mode in ("schedule", "all"):
        test_schedule(target_branches=args.branch, days_ahead=args.days)
