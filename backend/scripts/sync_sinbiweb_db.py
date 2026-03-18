"""
sinbiweb PHP CMS 방탈출 카페 통합 동기화 스크립트.

지원 사이트:
  황금열쇠 건대점  http://xn--jj0b998aq3cptw.com  place_id=1271584354
  나의신방 신촌점  https://xn--910bj3tlmfz4e.com  place_id=1521613397
  엑소더스 강남점  https://exodusescape.co.kr      place_id=103606910
  코드헌터 강남점  https://codehunter-escape.com   place_id=1213158520  (rev_subpath=layout/kor)
  해피앤딩 홍대점  https://happyanding.co.kr        place_id=1541961243
  에필로그         https://epilogueescape.com       place_id=458997744
  스피키지         https://speakeasyescape.co.kr    place_id=1825220691
  호텔레토 성수점  http://hotelletoh.co.kr          place_id=1168819420
  탈출브라더스 영등포점 https://escapebro.co.kr    place_id=1045036053
  어클락이스케이프 http://oclock-escape.com         place_id=1425246210
  상상의문 수원점    https://xn--z92b74ha268d.com  place_id=776353707   s_zizum=5
  상상의문 분당서현점 https://xn--z92b74ha268d.com  place_id=505122419   s_zizum=2
  상상의문 수원2호점  https://xn--z92b74ha268d.com  place_id=1121229740  s_zizum=7
  버스티드          http://busted.kr              place_id=1092766492
  골든타임이스케이프 1호점 https://xn--bb0b44mb8pfwi.kr  place_id=1875954710  s_zizum=1
  골든타임이스케이프 2호점 https://xn--bb0b44mb8pfwi.kr  place_id=1591055284  s_zizum=2
  상상의문 부평점          https://xn--z92b74ha268d.com  place_id=1387240933  s_zizum=6
  콜드케이스              http://cold-case.co.kr        place_id=455356224

공통 API 구조:
  GET {base_url}/layout/res/home.php?go=rev.make[&s_zizum={N}]&rev_days=YYYY-MM-DD
  HTML: .theme_box 단위 테마 → li > span.time(시간) + span.possible/impossible(가용성)
  - span.possible   → 예약 가능 (a[href] = 예약 링크)
  - span.impossible → 예약 마감
  - theme_box 없으면 예약 미오픈

실행:
  cd escape-aggregator/backend
  uv run python scripts/sync_sinbiweb_db.py
  uv run python scripts/sync_sinbiweb_db.py --days 14
"""

import ssl
import sys
import time
import urllib.request
import urllib.parse
from datetime import date, datetime, time as dtime, timedelta
from http.cookiejar import CookieJar
from pathlib import Path

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from bs4 import BeautifulSoup

from app.config import settings
from app.firestore_db import (
    init_firestore, get_db, upsert_cafe,
    get_or_create_theme, upsert_cafe_date_schedules,
    load_cafe_hashes, save_cafe_hashes,
)

REQUEST_DELAY = 1.0

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

# 사이트별 설정
# s_zizum: 지점 번호 (None이면 파라미터 생략)
SITES: list[dict] = [
    {
        "cafe_id":     "1271584354",
        "cafe_name":   "황금열쇠",
        "branch_name": "건대점",
        "address":     "서울 광진구 화양동 9-90 4층",
        "area":        "konkuk",
        "base_url":    "http://xn--jj0b998aq3cptw.com",
        "s_zizum":     7,
        "use_ssl":     False,
        "need_session": False,
    },
    {
        "cafe_id":     "1521613397",
        "cafe_name":   "나의신방",
        "branch_name": "신촌점",
        "address":     "서울 서대문구 창천동 57-3 3층",
        "area":        "sinchon",
        "base_url":    "https://xn--910bj3tlmfz4e.com",
        "s_zizum":     None,
        "use_ssl":     True,
        "need_session": True,
    },
    {
        "cafe_id":     "103606910",
        "cafe_name":   "엑소더스",
        "branch_name": "강남1호점",
        "address":     "서울 강남구 역삼동 619-23 지하 1층",
        "area":        "gangnam",
        "base_url":    "https://exodusescape.co.kr",
        "s_zizum":     None,
        "use_ssl":     True,
        "need_session": True,
    },
    {
        "cafe_id":     "1213158520",
        "cafe_name":   "코드헌터",
        "branch_name": "강남점",
        "address":     "서울 강남구 역삼동 817-17 3층",
        "area":        "gangnam",
        "base_url":    "https://codehunter-escape.com",
        "rev_subpath": "layout/kor",
        "s_zizum":     None,
        "use_ssl":     True,
        "need_session": True,
    },
    {
        "cafe_id":     "1541961243",
        "cafe_name":   "해피앤딩",
        "branch_name": "홍대점",
        "address":     "서울 마포구 와우산로21길 31-11",
        "area":        "hongdae",
        "base_url":    "https://happyanding.co.kr",
        "s_zizum":     None,
        "use_ssl":     True,
        "need_session": True,
    },
    {
        "cafe_id":     "458997744",
        "cafe_name":   "에필로그",
        "branch_name": None,
        "address":     "서울 종로구 대학로8가길 48",
        "area":        "myeongdong",
        "base_url":    "https://epilogueescape.com",
        "s_zizum":     None,
        "use_ssl":     True,
        "need_session": True,
    },
    {
        "cafe_id":     "1825220691",
        "cafe_name":   "스피키지",
        "branch_name": None,
        "address":     "서울 마포구 어울마당로 138 4층",
        "area":        "hongdae",
        "base_url":    "https://speakeasyescape.co.kr",
        "s_zizum":     None,
        "use_ssl":     True,
        "need_session": True,
    },
    {
        "cafe_id":     "1168819420",
        "cafe_name":   "호텔레토",
        "branch_name": "성수점",
        "address":     "서울 성동구 성수이로 78 2층",
        "area":        "seongsu",
        "base_url":    "http://hotelletoh.co.kr",
        "s_zizum":     None,
        "use_ssl":     False,
        "need_session": True,
    },
    {
        "cafe_id":     "1045036053",
        "cafe_name":   "탈출브라더스",
        "branch_name": "영등포점",
        "address":     "서울 영등포구 영등포동4가 433 4층",
        "area":        "etc",
        "base_url":    "https://escapebro.co.kr",
        "s_zizum":     None,
        "use_ssl":     True,
        "need_session": True,
    },
    {
        "cafe_id":     "1425246210",
        "cafe_name":   "어클락이스케이프",
        "branch_name": None,
        "address":     "경기 시흥시 서울대학로278번길 43-13",
        "area":        "etc",
        "base_url":    "http://oclock-escape.com",
        "s_zizum":     None,
        "use_ssl":     False,
        "need_session": True,
    },
    {
        "cafe_id":     "997136500",
        "cafe_name":   "둠이스케이프",
        "branch_name": "1호점",
        "address":     "인천 남동구 성말로13번길 15",
        "area":        "incheon",
        "base_url":    "https://doomescape.com",
        "s_zizum":     1,
        "use_ssl":     True,
        "need_session": True,
    },
    {
        "cafe_id":     "1321479252",
        "cafe_name":   "둠이스케이프",
        "branch_name": "2호점",
        "address":     "인천 남동구 인하로507번길 18",
        "area":        "incheon",
        "base_url":    "https://doomescape.com",
        "s_zizum":     2,
        "use_ssl":     True,
        "need_session": True,
    },
    {
        "cafe_id":     "892126854",
        "cafe_name":   "둠이스케이프",
        "branch_name": "DTH점",
        "address":     "인천 부평구 부평문화로 75",
        "area":        "incheon",
        "base_url":    "https://doomescape.com",
        "s_zizum":     3,
        "use_ssl":     True,
        "need_session": True,
    },
    {
        "cafe_id":     "2055691742",
        "cafe_name":   "디코드이스케이프",
        "branch_name": "전주점",
        "address":     "전북 전주시 완산구 전주객사3길 46-10",
        "area":        "etc",
        "base_url":    "http://dcodeescape.co.kr",
        "s_zizum":     1,
        "use_ssl":     False,
        "need_session": True,
    },
    {
        "cafe_id":     "348406652",
        "cafe_name":   "다이아에그",
        "branch_name": "미스테리인점",
        "address":     "부산 부산진구 중앙대로692번길 37",
        "area":        "busan",
        "base_url":    "https://mysterytown.co.kr",
        "s_zizum":     None,
        "use_ssl":     True,
        "need_session": True,
    },
    {
        "cafe_id":     "636394528",
        "cafe_name":   "레전드이스케이프",
        "branch_name": "이천점",
        "address":     "경기 이천시 서희로 58",
        "area":        "etc",
        "base_url":    "http://legendescape.com",
        "s_zizum":     2,
        "use_ssl":     False,
        "need_session": True,
    },
    {
        "cafe_id":     "1968639091",
        "cafe_name":   "레전드이스케이프",
        "branch_name": "서현점",
        "address":     "경기 성남시 분당구 서현로210번길 20",
        "area":        "etc",
        "base_url":    "http://legendescape.com",
        "s_zizum":     1,
        "use_ssl":     False,
        "need_session": True,
    },
    {
        "cafe_id":     "776353707",
        "cafe_name":   "상상의문",
        "branch_name": "수원점",
        "address":     "경기 수원시 팔달구 인계동 1041-12",
        "area":        "gyeonggi",
        "base_url":    "https://xn--z92b74ha268d.com",
        "s_zizum":     5,
        "use_ssl":     True,
        "need_session": True,
    },
    {
        "cafe_id":     "505122419",
        "cafe_name":   "상상의문",
        "branch_name": "분당서현점",
        "address":     "경기 성남시 분당구 서현동 250-4",
        "area":        "gyeonggi",
        "base_url":    "https://xn--z92b74ha268d.com",
        "s_zizum":     2,
        "use_ssl":     True,
        "need_session": True,
    },
    {
        "cafe_id":     "1121229740",
        "cafe_name":   "상상의문",
        "branch_name": "수원2호점",
        "address":     "경기 수원시 팔달구 효원로249번길 46-18",
        "area":        "gyeonggi",
        "base_url":    "https://xn--z92b74ha268d.com",
        "s_zizum":     7,
        "use_ssl":     True,
        "need_session": True,
    },
    {
        "cafe_id":     "1092766492",
        "cafe_name":   "버스티드",
        "branch_name": None,
        "address":     "경기 부천시 원미구 부일로445번길 22",
        "area":        "gyeonggi",
        "base_url":    "http://busted.kr",
        "s_zizum":     None,
        "use_ssl":     False,
        "need_session": True,
    },
    {
        "cafe_id":     "1875954710",
        "cafe_name":   "골든타임이스케이프",
        "branch_name": "1호점",
        "address":     "경기 수원시 영통구 영통동 998-4",
        "area":        "gyeonggi",
        "base_url":    "https://xn--bb0b44mb8pfwi.kr",
        "s_zizum":     1,
        "use_ssl":     True,
        "need_session": True,
    },
    {
        "cafe_id":     "1591055284",
        "cafe_name":   "골든타임이스케이프",
        "branch_name": "2호점",
        "address":     "경기 수원시 영통구 영통동 1011-6",
        "area":        "gyeonggi",
        "base_url":    "https://xn--bb0b44mb8pfwi.kr",
        "s_zizum":     2,
        "use_ssl":     True,
        "need_session": True,
    },
    {
        "cafe_id":     "1387240933",
        "cafe_name":   "상상의문",
        "branch_name": "부평점",
        "address":     "인천 부평구 부평대로 293 3층",
        "area":        "incheon",
        "base_url":    "https://xn--z92b74ha268d.com",
        "s_zizum":     6,
        "use_ssl":     True,
        "need_session": True,
    },
    {
        "cafe_id":     "455356224",
        "cafe_name":   "콜드케이스",
        "branch_name": "인하대점",
        "address":     "인천 남구 인하로 100",
        "area":        "incheon",
        "base_url":    "http://cold-case.co.kr",
        "s_zizum":     None,
        "use_ssl":     False,
        "need_session": True,
    },
    {
        "cafe_id":     "444802506",
        "cafe_name":   "메타이스케이프",
        "branch_name": None,
        "address":     "경기 수원시 팔달구 인계동 1038-11",
        "area":        "gyeonggi",
        "base_url":    "https://xn--h32b25mu4dba377gzscs2k.com",
        "s_zizum":     None,
        "use_ssl":     True,
        "need_session": True,
    },
    {
        # 큐방탈출카페 일산 웨스턴돔점 — sinbiweb POST variant (/reserve/)
        "cafe_id":     "351145232",
        "cafe_name":   "큐방탈출카페",
        "branch_name": "일산점",
        "address":     "경기 고양시 일산서구 킨텍스로 217-60",
        "area":        "gyeonggi",
        "base_url":    "http://www.qescapeilsan.co.kr",
        "s_zizum":     None,
        "use_ssl":     False,
        "need_session": True,
        "rev_use_post": True,
        "rev_subpath":  "reserve",
    },
    {
        # 제주방탈출 제원점 — sinbiweb (EUC-KR)
        "cafe_id":     "1554942559",
        "cafe_name":   "제주방탈출",
        "branch_name": "제원점",
        "address":     "제주특별자치도 제주시 연동 273-15",
        "area":        "jeju",
        "base_url":    "http://www.xn--vh3bw8qo2aba23i98on1f.com",
        "s_zizum":     None,
        "use_ssl":     False,
        "need_session": True,
    },
]


# ── HTTP 유틸 ────────────────────────────────────────────────────────────────────

def _make_opener(use_ssl: bool) -> urllib.request.OpenerDirector:
    cj = CookieJar()
    if use_ssl:
        https_handler = urllib.request.HTTPSHandler(context=_SSL_CTX)
        return urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(cj),
            https_handler,
        )
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def _get_session(opener: urllib.request.OpenerDirector, base_url: str) -> bool:
    req = urllib.request.Request(
        base_url + "/",
        headers={**HEADERS, "Accept": "text/html,application/xhtml+xml,*/*"},
    )
    try:
        with opener.open(req, timeout=15) as r:
            r.read()
        return True
    except Exception as e:
        print(f"  [WARN] 세션 획득 실패: {e}")
        return False


def _reserve_url(site: dict, target_date: date) -> str:
    subpath = site.get("rev_subpath", "layout/res")
    base = site["base_url"] + f"/{subpath}/home.php"
    date_str = target_date.strftime("%Y-%m-%d")
    params = f"go=rev.make&rev_days={date_str}"
    if site["s_zizum"] is not None:
        params = f"go=rev.make&s_zizum={site['s_zizum']}&rev_days={date_str}"
    return f"{base}?{params}"


def _fetch_page(opener: urllib.request.OpenerDirector, site: dict, target_date: date) -> str:
    date_str = target_date.strftime("%Y-%m-%d")
    if site.get("rev_use_post"):
        # POST variant: /reserve/ with rdate=YYYY-MM-DD&theme=
        subpath = site.get("rev_subpath", "reserve")
        url = site["base_url"] + f"/{subpath}/"
        post_data = f"rdate={date_str}&theme=".encode()
        req = urllib.request.Request(
            url,
            data=post_data,
            headers={**HEADERS, "Referer": site["base_url"] + "/",
                     "Content-Type": "application/x-www-form-urlencoded"},
        )
    else:
        url = _reserve_url(site, target_date)
        req = urllib.request.Request(
            url,
            headers={**HEADERS, "Referer": site["base_url"] + "/"},
        )
    try:
        with opener.open(req, timeout=15) as r:
            return r.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"  [WARN] 페이지 로드 실패 {target_date}: {e}")
        return ""


# ── HTML 파싱 ────────────────────────────────────────────────────────────────────

def _parse_page(html: str, site: dict, target_date: date) -> list[dict]:
    """
    반환: [{"theme_name", "poster_url", "slots": [{"time", "status", "booking_url"}]}]
    """
    soup = BeautifulSoup(html, "html.parser")
    boxes = soup.select(".theme_box")
    if not boxes:
        return []

    date_str = target_date.strftime("%Y-%m-%d")
    base_url = site["base_url"]
    results = []

    for box in boxes:
        # 테마명
        h3 = box.select_one("h3, h3.h3_theme, .h3_theme")
        if not h3:
            continue
        theme_name = h3.get_text(strip=True)
        # "(부제목)" 제거 — 예: "fl[ae]sh  (공포,스릴러)" → "fl[ae]sh"
        if "(" in theme_name:
            theme_name = theme_name[:theme_name.index("(")].strip()
        if not theme_name:
            continue

        # 포스터 이미지
        img = box.select_one(".theme_pic img")
        poster_url = None
        if img and img.get("src"):
            src = img["src"].split("?")[0]
            if src.startswith("../../"):
                poster_url = base_url + "/" + src[6:]
            elif src.startswith("http"):
                poster_url = src
            elif src.startswith("/"):
                poster_url = base_url + src

        slots = []
        for li in box.select("ul.reserve_Time li, ul li"):
            time_span = li.select_one("span.time")
            if not time_span:
                continue
            time_str = time_span.get_text(strip=True)
            try:
                hh, mm = map(int, time_str.split(":"))
                time_obj = dtime(hh, mm)
            except Exception:
                continue

            possible = li.select_one("span.possible")
            impossible = li.select_one("span.impossible")
            a_tag = li.select_one("a")

            if possible:
                status = "available"
                href = a_tag.get("href", "") if a_tag else ""
                if href:
                    if href.startswith("http"):
                        booking_url = href
                    elif href.startswith("/"):
                        booking_url = base_url + href
                    else:
                        booking_url = base_url + "/layout/res/" + href
                else:
                    booking_url = _reserve_url(site, target_date)
            elif impossible:
                status = "full"
                booking_url = None
            else:
                continue

            slots.append({
                "time":        time_obj,
                "status":      status,
                "booking_url": booking_url,
            })

        if slots:
            results.append({
                "theme_name": theme_name,
                "poster_url": poster_url,
                "slots":      slots,
            })

    return results


# ── DB 동기화 ────────────────────────────────────────────────────────────────────

def sync_one_site(site: dict, run_schedule: bool, days: int) -> None:
    print(f"\n{'='*50}")
    print(f"[ {site['cafe_name']} {site['branch_name']} ]")
    print(f"{'='*50}")

    db = get_db()
    cafe_id = site["cafe_id"]

    # 1. 카페 메타
    upsert_cafe(db, cafe_id, {
        "name":        site["cafe_name"],
        "branch_name": site["branch_name"],
        "address":     site["address"],
        "area":        site["area"],
        "phone":       None,
        "website_url": site["base_url"] + "/",
        "engine":      "sinbiweb",
        "crawled":     True,
        "lat":         None,
        "lng":         None,
        "is_active":   True,
    })
    print(f"  [UPSERT] 카페 (id={cafe_id})")

    opener = _make_opener(site["use_ssl"])

    if site.get("need_session"):
        _get_session(opener, site["base_url"])
        time.sleep(REQUEST_DELAY)

    # 2. 테마 추출 (오늘 + fallback)
    today = date.today()
    parsed_today = []
    for i in range(8):
        target = today + timedelta(days=i)
        html = _fetch_page(opener, site, target)
        time.sleep(REQUEST_DELAY)
        parsed_today = _parse_page(html, site, target)
        if parsed_today:
            print(f"  기준 날짜: {target} (테마 {len(parsed_today)}개)")
            break

    if not parsed_today:
        print("  테마 정보를 찾을 수 없음, 건너뜀.")
        return

    # 3. 테마 upsert
    cafe_doc = db.collection("cafes").document(cafe_id).get()
    if not cafe_doc.exists:
        print(f"  [ERROR] cafe {cafe_id} Firestore 미존재")
        return

    name_to_doc: dict[str, str] = {}
    for t in parsed_today:
        doc_id = get_or_create_theme(db, cafe_id, t["theme_name"], {
            "difficulty":   None,
            "duration_min": None,
            "poster_url":   t.get("poster_url"),
            "is_active":    True,
        })
        name_to_doc[t["theme_name"]] = doc_id
        print(f"  [UPSERT] 테마: {t['theme_name']} (doc={doc_id})")

    if not run_schedule:
        return

    # 4. 스케줄 upsert
    target_dates = [today + timedelta(days=i) for i in range(days + 1)]
    crawled_at = datetime.now()
    writes = 0
    known_hashes = load_cafe_hashes(db, cafe_id)
    new_hashes: dict[str, str] = {}

    for target_date in target_dates:
        html = _fetch_page(opener, site, target_date)
        time.sleep(REQUEST_DELAY)
        parsed = _parse_page(html, site, target_date)
        date_str = target_date.strftime("%Y-%m-%d")

        if not parsed:
            print(f"  {date_str}: 미오픈")
            continue

        themes_data: dict[str, dict] = {}
        avail = full = 0

        for t in parsed:
            doc_id = name_to_doc.get(t["theme_name"])
            if not doc_id:
                print(f"  [WARN] 알 수 없는 테마: {t['theme_name']!r}")
                continue
            for slot in t["slots"]:
                time_obj = slot["time"]
                slot_dt = datetime(
                    target_date.year, target_date.month, target_date.day,
                    time_obj.hour, time_obj.minute,
                )
                if slot_dt <= datetime.now():
                    continue
                themes_data.setdefault(doc_id, {"slots": []})["slots"].append({
                    "time":        f"{time_obj.hour:02d}:{time_obj.minute:02d}",
                    "status":      slot["status"],
                    "booking_url": slot["booking_url"],
                })
                if slot["status"] == "available":
                    avail += 1
                else:
                    full += 1

        if themes_data:
            h = upsert_cafe_date_schedules(
                db, date_str, cafe_id, themes_data, crawled_at,
                known_hash=known_hashes.get(date_str),
            )
            if h:
                new_hashes[date_str] = h
                writes += 1

        print(f"  {date_str}: 가능 {avail}개 / 마감 {full}개")

    if new_hashes:
        today_str = today.isoformat()
        save_cafe_hashes(db, cafe_id, {
            k: v for k, v in {**known_hashes, **new_hashes}.items()
            if k >= today_str
        })

    print(f"  스케줄 동기화: {writes}개 날짜 작성")


# ── 메인 ─────────────────────────────────────────────────────────────────────────

def main(run_schedule: bool = True, days: int = 14):
    print("=" * 60)
    print("sinbiweb 방탈출 카페 통합 DB 동기화")
    print("=" * 60)

    init_firestore(settings.firebase_credentials_path)

    for site in SITES:
        try:
            sync_one_site(site, run_schedule, days)
        except Exception as e:
            print(f"  [ERROR] {site['cafe_name']} {site['branch_name']} 크롤링 실패: {e}")

    print("\n" + "=" * 60)
    print("모든 사이트 동기화 완료!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="sinbiweb 방탈출 카페 DB 동기화")
    parser.add_argument("--no-schedule", action="store_true")
    parser.add_argument("--days", type=int, default=14)
    args = parser.parse_args()
    main(run_schedule=not args.no_schedule, days=args.days)
