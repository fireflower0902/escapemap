"""
카카오 로컬 API — 전국 방탈출 카페 수집 스크립트

전략:
  - 대한민국 전체(제주~강원, 서해도서~동해안)를 격자로 분할
  - 격자 간격: 위도 0.09° × 경도 0.11° (≈ 10km)
  - 검색 반경: 6,000m (격자 간격보다 크게 설정해 누락 방지)
  - 키워드: "방탈출", "방탈출카페"
  - place_id 기준 중복 제거
  - 수집 후 각 카페의 카카오 플레이스 페이지에서 공식 홈페이지 URL 추출

실행:
  cd escape-aggregator/backend
  python scripts/crawl_kakao_nationwide.py
"""

import os
import json
import time
import re
import requests
from datetime import datetime
from pathlib import Path

# ── 설정 ───────────────────────────────────────────────────────
KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY", "0cfc92e420851ca182df03ef9a06ec5d")

SEARCH_KEYWORDS = ["방탈출", "방탈출카페"]

# 대한민국 전체 경계
KOREA_LAT_MIN = 33.0   # 제주도 남단
KOREA_LAT_MAX = 38.6   # 강원도 북단 (휴전선 아래)
KOREA_LNG_MIN = 124.5  # 서해 최서단 도서
KOREA_LNG_MAX = 129.7  # 경북 동해안

# 격자 간격
GRID_STEP_LAT = 0.09   # ≈ 10km
GRID_STEP_LNG = 0.11   # ≈ 9.5km (위도 36° 기준)

SEARCH_RADIUS   = 6000  # 검색 반경 (m) — 격자보다 크게 설정해 누락 방지
MAX_PAGE        = 3
SIZE_PER_PAGE   = 15

REQUEST_DELAY   = 0.3   # API 호출 간격 (초)

OUTPUT_DIR  = Path(__file__).parent.parent / "data"
OUTPUT_FILE = OUTPUT_DIR / f"kakao_nationwide_{datetime.now().strftime('%Y%m%d_%H%M')}.json"

KAKAO_HEADERS = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
KAKAO_SEARCH_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"

# 홈페이지 URL 추출용
PLACE_DETAIL_URL = "https://place.map.kakao.com/m/main/v/{place_id}"
HOMEPAGE_PATTERN = re.compile(
    r'"homepage"\s*:\s*"([^"]+)"'      # JSON 형태
    r'|homepageUrl["\s:]+([^\s"<,}]+)' # 다른 형태
    r'|"url"\s*:\s*"(https?://(?!place\.map\.kakao)[^"]+)"',  # url 필드 (카카오 아닌 것)
    re.IGNORECASE,
)

# ── 방탈출 필터 ─────────────────────────────────────────────────
INCLUDE_KEYWORDS = ["방탈출", "이스케이프", "escape", "탈출"]
EXCLUDE_KEYWORDS = ["학원", "교육", "유치원", "어린이집"]


def is_escape_room(place: dict) -> bool:
    name     = place.get("place_name", "").lower()
    category = place.get("category_name", "").lower()
    text     = name + " " + category
    if not any(k in text for k in INCLUDE_KEYWORDS):
        return False
    if any(e in text for e in EXCLUDE_KEYWORDS):
        return False
    return True


# ── Kakao 로컬 검색 ─────────────────────────────────────────────
def search_places(keyword: str, lat: float, lng: float, page: int = 1) -> dict:
    params = {
        "query":  keyword,
        "y":      lat,
        "x":      lng,
        "radius": SEARCH_RADIUS,
        "page":   page,
        "size":   SIZE_PER_PAGE,
        "sort":   "distance",
    }
    resp = requests.get(KAKAO_SEARCH_URL, headers=KAKAO_HEADERS, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def normalize_place(raw: dict) -> dict:
    return {
        "place_id":      raw.get("id"),
        "place_name":    raw.get("place_name"),
        "category_name": raw.get("category_name"),
        "address":       raw.get("address_name"),
        "road_address":  raw.get("road_address_name"),
        "phone":         raw.get("phone"),
        "kakao_url":     raw.get("place_url"),  # 카카오 플레이스 URL
        "homepage_url":  None,                  # 공식 홈페이지 (2단계에서 추가)
        "lat":           float(raw.get("y", 0)),
        "lng":           float(raw.get("x", 0)),
    }


def generate_grid_points() -> list[tuple[float, float]]:
    points = []
    lat = KOREA_LAT_MIN
    while lat <= KOREA_LAT_MAX:
        lng = KOREA_LNG_MIN
        while lng <= KOREA_LNG_MAX:
            points.append((round(lat, 4), round(lng, 4)))
            lng += GRID_STEP_LNG
        lat += GRID_STEP_LAT
    return points


# ── 1단계: 전국 격자 검색 ───────────────────────────────────────
def crawl_places() -> dict[str, dict]:
    grid_points = generate_grid_points()
    total_pts   = len(grid_points)
    est_calls   = total_pts * len(SEARCH_KEYWORDS) * MAX_PAGE
    est_min     = est_calls * REQUEST_DELAY / 60

    print(f"\n[1단계] 전국 격자 검색")
    print(f"  격자: {total_pts:,}개 | 최대 API 호출: {est_calls:,}회 | 예상 최대: {est_min:.0f}분")
    print(f"  (실제로는 빈 격자에서 조기 종료 → 약 {est_min*0.45:.0f}분 예상)\n")

    all_places: dict[str, dict] = {}
    api_calls = 0
    errors    = 0

    for idx, (lat, lng) in enumerate(grid_points):
        for keyword in SEARCH_KEYWORDS:
            for page in range(1, MAX_PAGE + 1):
                try:
                    data      = search_places(keyword, lat, lng, page)
                    documents = data.get("documents", [])
                    meta      = data.get("meta", {})

                    for raw in documents:
                        place = normalize_place(raw)
                        pid   = place["place_id"]
                        if pid and pid not in all_places and is_escape_room(place):
                            all_places[pid] = place

                    api_calls += 1

                    if meta.get("is_end", True):
                        break

                    time.sleep(REQUEST_DELAY)

                except requests.exceptions.HTTPError as e:
                    errors += 1
                    if e.response.status_code == 401:
                        print("\n❌ 인증 실패 — API 키를 확인하세요!")
                        return all_places
                    print(f"  HTTP 오류: {e}")
                    time.sleep(1)

                except Exception as e:
                    errors += 1
                    print(f"  오류: {e}")
                    time.sleep(0.5)

        if (idx + 1) % 50 == 0 or idx == total_pts - 1:
            pct = (idx + 1) / total_pts * 100
            print(f"  [{pct:5.1f}%] 격자 {idx+1:,}/{total_pts:,} | "
                  f"수집: {len(all_places):,}개 | API: {api_calls:,}회 | 오류: {errors}개")

    return all_places


# ── 2단계: 공식 홈페이지 URL 추출 ──────────────────────────────
def fetch_homepage(place_id: str, session: requests.Session) -> str | None:
    """카카오 플레이스 API로 공식 홈페이지 URL 조회"""
    try:
        # 카카오 플레이스 상세 API (모바일 엔드포인트)
        url = f"https://place.map.kakao.com/m/main/v/{place_id}"
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                          "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
            "Referer": "https://map.kakao.com/",
        }
        resp = session.get(url, headers=headers, timeout=8)
        if resp.status_code != 200:
            return None

        text = resp.text

        # JSON 내 homepage 필드 추출
        m = re.search(r'"homepage"\s*:\s*"([^"]+)"', text)
        if m:
            hp = m.group(1).strip()
            if hp and not hp.startswith("http://place.map.kakao.com"):
                return hp

        # og:url 메타 태그 (fallback)
        m2 = re.search(r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)["\']', text)
        if m2:
            og = m2.group(1).strip()
            if og and "kakao.com" not in og:
                return og

        return None

    except Exception:
        return None


def enrich_homepages(places: dict[str, dict]) -> None:
    total = len(places)
    print(f"\n[2단계] 공식 홈페이지 URL 조회 ({total:,}개)")
    print("  (카카오 플레이스 페이지에서 홈페이지 링크 추출)\n")

    found   = 0
    session = requests.Session()
    session.headers.update({"Accept-Language": "ko-KR,ko;q=0.9"})

    ids = list(places.keys())
    for i, pid in enumerate(ids, 1):
        hp = fetch_homepage(pid, session)
        if hp:
            places[pid]["homepage_url"] = hp
            found += 1

        if i % 20 == 0 or i == total:
            print(f"  [{i:3d}/{total}] 홈페이지 발견: {found}개")

        time.sleep(0.2)  # 과부하 방지

    print(f"\n  홈페이지 URL 확보: {found}/{total}개 ({found/total*100:.1f}%)")


# ── 메인 ─────────────────────────────────────────────────────────
def main():
    print("=" * 65)
    print("카카오 로컬 API — 전국 방탈출 카페 수집")
    print(f"  범위: 위도 {KOREA_LAT_MIN}~{KOREA_LAT_MAX}, 경도 {KOREA_LNG_MIN}~{KOREA_LNG_MAX}")
    print(f"  격자 간격: {GRID_STEP_LAT}°×{GRID_STEP_LNG}° (≈10km) | 반경: {SEARCH_RADIUS//1000}km")
    print("=" * 65)

    start = time.time()

    # 1단계: 격자 검색
    places = crawl_places()
    elapsed1 = time.time() - start
    print(f"\n  1단계 완료: {len(places):,}개 수집 ({elapsed1:.0f}초)")

    # 2단계: 홈페이지 URL 보강
    enrich_homepages(places)
    elapsed_total = time.time() - start

    # 지역별 분포
    area_count: dict[str, int] = {}
    for p in places.values():
        addr  = p.get("road_address") or p.get("address") or ""
        parts = addr.split()
        # 시/도 추출
        si_do = parts[0] if parts else "기타"
        area_count[si_do] = area_count.get(si_do, 0) + 1

    print(f"\n{'=' * 65}")
    print(f"  총 수집: {len(places):,}개 | 소요: {elapsed_total:.0f}초 ({elapsed_total/60:.1f}분)")
    print(f"\n  지역별 분포 (상위 15개):")
    for area, cnt in sorted(area_count.items(), key=lambda x: -x[1])[:15]:
        bar = "█" * min(cnt // 2, 40)
        print(f"    {area:6s} {cnt:4d}개  {bar}")

    # JSON 저장
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = {
        "crawled_at": datetime.now().isoformat(),
        "total":      len(places),
        "places":     list(places.values()),
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n  저장: {OUTPUT_FILE}")
    print("=" * 65)


if __name__ == "__main__":
    main()
