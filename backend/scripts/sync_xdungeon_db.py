"""
xdungeon.net 테마 + 스케줄을 DB에 동기화하는 스크립트.

동작:
  1. 9개 지점의 테마 목록 + 상세(플레이타임, 시놉시스)를 theme 테이블에 upsert
  2. 오늘 ~ 6일 후 스케줄을 schedule 테이블에 upsert

실행:
  cd escape-aggregator/backend
  python scripts/sync_xdungeon_db.py
  python scripts/sync_xdungeon_db.py --no-schedule   # 테마만
  python scripts/sync_xdungeon_db.py --days 3        # 스케줄 3일치만
"""

import re
import sys
import time
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import requests
from bs4 import BeautifulSoup

from app.config import settings
from app.firestore_db import init_firestore, get_db, get_or_create_theme, upsert_cafe_date_schedules, load_cafe_hashes, save_cafe_hashes

BASE_URL = "https://xdungeon.net/layout/res/home.php"
THEME_ACT_URL = "https://xdungeon.net/core/res/theme.act.php"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://xdungeon.net/layout/res/home.php?go=rev.main",
}
REQUEST_DELAY = 0.4

# 지점 ID 매핑: s_zizum → 카카오 place_id (cafe.id)
BRANCH_MAP = {
    1:  "1772808576",  # 던전101
    2:  "27413263",    # 강남던전
    3:  "1246652450",  # 홍대던전
    4:  "1769092819",  # 강남던전Ⅱ
    5:  "2070160321",  # 홍대던전Ⅲ
    6:  "1478483341",  # 던전루나(강남)
    7:  "1322241204",  # 서면던전(부산)
    9:  "436025860",   # 던전스텔라(강남)
    10: "629764977",   # 서면던전 레드(부산)
}

DIFFICULTY_MAP = {"EASY": 2, "NORMAL": 3, "HARD": 4}


# ── 웹 크롤링 함수 ─────────────────────────────────────────────────────────────

def fetch_themes_for_branch(zizum_id: int) -> list[dict]:
    resp = requests.get(
        BASE_URL, params={"go": "theme.list", "s_zizum": zizum_id},
        headers=HEADERS, timeout=15,
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
        name_tag  = li.find("p",    class_="thm")
        level_tag = li.find("span", class_="lv")
        genre_tag = li.find("span", class_="gr")
        # 포스터 이미지
        img = li.find("img")
        poster = f"https://xdungeon.net{img['src']}" if img and img.get("src") else None
        themes.append({
            "xdungeon_id": theme_id,
            "name":        name_tag.get_text(strip=True)  if name_tag  else "",
            "difficulty":  level_tag.get_text(strip=True) if level_tag else "",
            "genre":       genre_tag.get_text(strip=True) if genre_tag else "",
            "poster_url":  poster,
        })
    return themes


def fetch_theme_detail(theme_id: str) -> dict:
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
        key_map = {
            "플레이타임": "play_time",
            "시놉시스":   "synopsis",
            "특이사항":   "notes",
        }
        key = dt.get_text(strip=True)
        if key in key_map:
            detail[key_map[key]] = dd.get_text(separator=" ", strip=True)
    return detail


def fetch_schedule(zizum_id: int, target_date: date) -> list[dict]:
    resp = requests.get(
        BASE_URL,
        params={"go": "rev.main", "s_zizum": zizum_id,
                "rev_days": target_date.strftime("%Y-%m-%d")},
        headers=HEADERS, timeout=15,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    container = soup.find("div", class_="thm_box")
    if not container:
        return results
    for box in container.find_all("div", class_="box"):
        img_link = box.find("a", href=lambda h: h and "_fun_theme_view" in str(h))
        if not img_link:
            continue
        m = re.search(r"_fun_theme_view\('(\d+)'\)", img_link["href"])
        xdungeon_id = m.group(1) if m else None
        time_box = box.find("div", class_="time_box")
        slots = []
        if time_box:
            if time_box.find("div", class_="rev_make_text"):
                pass  # 오픈 전
            else:
                for li in time_box.find_all("li"):
                    classes = li.get("class", [])
                    a_tag = li.find("a")
                    if not a_tag:
                        continue
                    for span in a_tag.find_all("span"):
                        span.decompose()
                    t = a_tag.get_text(strip=True)
                    if not t or ":" not in t:
                        continue
                    is_sale = "sale" in classes
                    is_dead = "dead" in classes
                    if is_sale and not is_dead:
                        status = "available"
                        booking_href = a_tag.get("href", "")
                        booking_url = f"https://xdungeon.net/layout/res/{booking_href}" if booking_href else None
                    elif is_sale and is_dead:
                        status = "full"
                        booking_url = None
                    else:
                        status = "closed"
                        booking_url = None
                    slots.append({"time": t, "status": status, "booking_url": booking_url})
        results.append({"xdungeon_id": xdungeon_id, "slots": slots})
    return results


# ── DB 동기화 함수 ─────────────────────────────────────────────────────────────

def sync_themes() -> dict[str, str]:
    """
    xdungeon 테마를 Firestore에 upsert.
    반환: {xdungeon_id → theme_doc_id}
    """
    db = get_db()
    xdungeon_to_doc_id: dict[str, str] = {}

    for zizum_id, cafe_id in BRANCH_MAP.items():
        # cafe 존재 확인
        cafe_doc = db.collection("cafes").document(cafe_id).get()
        if not cafe_doc.exists:
            print(f"  [WARN] cafe {cafe_id} Firestore 미존재 — 건너뜀")
            continue

        raw_themes = fetch_themes_for_branch(zizum_id)
        time.sleep(REQUEST_DELAY)

        for rt in raw_themes:
            # 상세 정보 가져오기
            detail = fetch_theme_detail(rt["xdungeon_id"])
            time.sleep(REQUEST_DELAY)

            # 플레이타임 파싱: "75분" → 75
            play_time_str = detail.get("play_time", "")
            duration = None
            m = re.search(r"(\d+)", play_time_str)
            if m:
                duration = int(m.group(1))

            synopsis = detail.get("synopsis", "")
            notes = detail.get("notes", "")
            description = synopsis + ("\n\n" + notes if notes else "")

            # 포스터 URL: xdungeon 이미지 base URL 저장 (theme_id 포함)
            poster = rt.get("poster_url") or f"https://xdungeon.net/file/theme/{rt['xdungeon_id']}/"

            difficulty_int = DIFFICULTY_MAP.get(rt["difficulty"], 3)

            theme_doc_id = get_or_create_theme(db, cafe_id, rt["name"], {
                "difficulty": difficulty_int,
                "duration_min": duration,
                "description": description,
                "poster_url": poster,
                "is_active": True,
            })
            xdungeon_to_doc_id[rt["xdungeon_id"]] = theme_doc_id
            print(f"  [UPSERT] {rt['name']} (cafe={cafe_id}) — {duration}분")

    print(f"\n  테마 동기화 완료: {len(xdungeon_to_doc_id)}개")
    return xdungeon_to_doc_id


def sync_schedules(xdungeon_to_doc_id: dict[str, str], days: int = 6):
    """xdungeon 스케줄을 Firestore에 upsert (오늘~days일 후)."""
    db = get_db()
    today = date.today()
    dates = [today + timedelta(days=i) for i in range(days + 1)]
    crawled_at = datetime.now()
    writes = 0

    for zizum_id, cafe_id in BRANCH_MAP.items():
        # {date_str: {theme_doc_id: {"slots": [...]}}}
        date_themes: dict[str, dict] = {}

        for d in dates:
            raw = fetch_schedule(zizum_id, d)
            time.sleep(REQUEST_DELAY)

            date_str = d.strftime("%Y-%m-%d")
            branch_url = (
                f"https://xdungeon.net/layout/res/home.php"
                f"?go=rev.main&s_zizum={zizum_id}&rev_days={date_str}"
            )

            for theme_data in raw:
                xid = theme_data["xdungeon_id"]
                theme_doc_id = xdungeon_to_doc_id.get(xid)
                if not theme_doc_id:
                    continue

                for slot in theme_data["slots"]:
                    # 예약 가능 슬롯만 booking_url 설정 (나머지는 None)
                    booking_url = branch_url if slot["status"] == "available" else None

                    date_themes.setdefault(date_str, {}).setdefault(theme_doc_id, {"slots": []})["slots"].append({
                        "time": slot["time"],
                        "status": slot["status"],
                        "booking_url": booking_url,
                    })

            print(f"  {d} s_zizum={zizum_id} 완료")

        known_hashes = load_cafe_hashes(db, cafe_id)
        new_hashes: dict[str, str] = {}
        for date_str, themes in date_themes.items():
            h = upsert_cafe_date_schedules(db, date_str, cafe_id, themes, crawled_at,
                                           known_hash=known_hashes.get(date_str))
            if h:
                new_hashes[date_str] = h
                writes += 1
        if new_hashes:
            today_str = date.today().isoformat()
            save_cafe_hashes(db, cafe_id, {k: v for k, v in {**known_hashes, **new_hashes}.items() if k >= today_str})

    print(f"\n  스케줄 동기화 완료: {writes}개 날짜 문서 작성")


def main(run_schedule: bool = True, days: int = 6):
    print("=" * 60)
    print("xdungeon.net → DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)

    print("\n[ 1단계 ] 테마 동기화")
    xdungeon_to_doc_id = sync_themes()
    print(f"  테마 ID 매핑: {len(xdungeon_to_doc_id)}개")

    if run_schedule:
        print(f"\n[ 2단계 ] 스케줄 동기화 (오늘~{days}일 후)")
        sync_schedules(xdungeon_to_doc_id, days=days)

    print("\n" + "=" * 60)
    print("동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-schedule", action="store_true", help="스케줄 동기화 생략")
    parser.add_argument("--days", type=int, default=6, help="스케줄 조회 일수")
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
