"""
카카오 로컬 검색 API로 서울 전체 방탈출 카페 수집 스크립트

전략:
  - 서울 경계를 위도/경도 격자(2km 간격)로 나눠 각 지점에서 반경 2km 검색
  - "방탈출" + "방탈출카페" 두 키워드로 교차 검색
  - place_id 기준으로 중복 제거
  - 결과를 JSON 파일로 저장 (→ 이후 DB에 삽입 예정)

사전 준비:
  1. 카카오 개발자 콘솔(developers.kakao.com)에서 앱 생성
  2. "카카오 로컬" API 활성화
  3. REST API 키 복사 → 아래 KAKAO_REST_API_KEY 에 입력
     또는 환경변수 KAKAO_REST_API_KEY 설정

실행:
  cd escape-aggregator/backend
  python scripts/crawl_kakao_places.py
"""

import os
import json
import time
import math
import requests
from datetime import datetime
from pathlib import Path

# ── 설정 ───────────────────────────────────────────────────────
KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY", "여기에_카카오_REST_API_키_입력")

SEARCH_KEYWORDS = ["방탈출", "방탈출카페"]

# 서울 경계 (위도/경도)
SEOUL_LAT_MIN = 37.42
SEOUL_LAT_MAX = 37.70
SEOUL_LNG_MIN = 126.76
SEOUL_LNG_MAX = 127.19

# 격자 간격 (도 단위, 약 1.8km)
GRID_STEP_LAT = 0.016  # 위도 0.016도 ≈ 1.78km
GRID_STEP_LNG = 0.020  # 경도 0.020도 ≈ 1.78km (서울 기준)

SEARCH_RADIUS = 2000    # 검색 반경 (미터)
MAX_PAGE = 3            # 페이지당 최대 15개 × 3페이지 = 45개
SIZE_PER_PAGE = 15

REQUEST_DELAY = 0.3     # API 호출 간격 (초) — 카카오 제한: 초당 10회

OUTPUT_DIR = Path(__file__).parent.parent / "data"
OUTPUT_FILE = OUTPUT_DIR / f"kakao_places_{datetime.now().strftime('%Y%m%d_%H%M')}.json"

KAKAO_HEADERS = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
KAKAO_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"


def search_places(keyword: str, lat: float, lng: float, page: int = 1) -> dict:
    """카카오 로컬 키워드 검색 API 호출"""
    params = {
        "query": keyword,
        "y": lat,          # 위도
        "x": lng,          # 경도
        "radius": SEARCH_RADIUS,
        "page": page,
        "size": SIZE_PER_PAGE,
        "sort": "distance",
    }
    resp = requests.get(KAKAO_URL, headers=KAKAO_HEADERS, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def generate_grid_points() -> list[tuple[float, float]]:
    """서울 전체를 커버하는 격자 좌표 생성"""
    points = []
    lat = SEOUL_LAT_MIN
    while lat <= SEOUL_LAT_MAX:
        lng = SEOUL_LNG_MIN
        while lng <= SEOUL_LNG_MAX:
            points.append((round(lat, 4), round(lng, 4)))
            lng += GRID_STEP_LNG
        lat += GRID_STEP_LAT
    return points


def normalize_place(raw: dict) -> dict:
    """카카오 API 응답을 정제된 형태로 변환"""
    return {
        "place_id": raw.get("id"),
        "place_name": raw.get("place_name"),
        "category_name": raw.get("category_name"),
        "category_group_code": raw.get("category_group_code"),
        "address": raw.get("address_name"),
        "road_address": raw.get("road_address_name"),
        "phone": raw.get("phone"),
        "website_url": raw.get("place_url"),    # 카카오 플레이스 URL (공식 홈페이지 아님)
        "lat": float(raw.get("y", 0)),
        "lng": float(raw.get("x", 0)),
        "distance_m": int(raw.get("distance", 0)) if raw.get("distance") else None,
    }


def is_escape_room(place: dict) -> bool:
    """방탈출 카페인지 필터링 (오분류 제거)"""
    name = place.get("place_name", "").lower()
    category = place.get("category_name", "").lower()

    # 방탈출 관련 키워드가 없으면 제외
    keywords = ["방탈출", "이스케이프", "escape", "탈출"]
    if not any(k in name + category for k in keywords):
        return False

    # 명백한 비관련 장소 제외 (예: 방탈출 관련 보드게임 카페가 아닌 일반 카페)
    exclude = ["학원", "교육", "유치원", "어린이집"]
    if any(e in name + category for e in exclude):
        return False

    return True


def crawl() -> list[dict]:
    """메인 크롤링 함수"""
    grid_points = generate_grid_points()
    total_points = len(grid_points)
    print(f"격자 좌표 {total_points}개 생성 완료")
    print(f"예상 API 호출 수: {total_points * len(SEARCH_KEYWORDS) * MAX_PAGE}회")

    all_places: dict[str, dict] = {}  # place_id → place 데이터
    api_calls = 0
    errors = 0

    for idx, (lat, lng) in enumerate(grid_points):
        for keyword in SEARCH_KEYWORDS:
            for page in range(1, MAX_PAGE + 1):
                try:
                    data = search_places(keyword, lat, lng, page)
                    documents = data.get("documents", [])
                    meta = data.get("meta", {})

                    for raw in documents:
                        place = normalize_place(raw)
                        pid = place["place_id"]
                        if pid and pid not in all_places:
                            if is_escape_room(place):
                                all_places[pid] = place

                    api_calls += 1

                    # 마지막 페이지면 더 이상 호출 불필요
                    if meta.get("is_end", True):
                        break

                    time.sleep(REQUEST_DELAY)

                except requests.exceptions.HTTPError as e:
                    errors += 1
                    if e.response.status_code == 401:
                        print("\n❌ 인증 실패 — KAKAO_REST_API_KEY를 확인해주세요!")
                        return list(all_places.values())
                    print(f"  HTTP 오류: {e}")
                    time.sleep(1)

                except Exception as e:
                    errors += 1
                    print(f"  오류 발생: {e}")
                    time.sleep(0.5)

        # 진행 상황 출력 (10개 지점마다)
        if (idx + 1) % 10 == 0 or idx == total_points - 1:
            progress = (idx + 1) / total_points * 100
            print(f"[{progress:5.1f}%] 지점 {idx+1}/{total_points} | "
                  f"수집: {len(all_places)}개 | API: {api_calls}회 | 오류: {errors}개")

    return list(all_places.values())


def main():
    print("=" * 60)
    print("카카오 로컬 API — 서울 방탈출 카페 수집 시작")
    print(f"검색 키워드: {SEARCH_KEYWORDS}")
    print(f"서울 격자 범위: 위도 {SEOUL_LAT_MIN}~{SEOUL_LAT_MAX}, 경도 {SEOUL_LNG_MIN}~{SEOUL_LNG_MAX}")
    print(f"검색 반경: {SEARCH_RADIUS}m | 격자 간격: ~1.8km")
    print("=" * 60)

    if KAKAO_REST_API_KEY == "여기에_카카오_REST_API_키_입력":
        print("\n⚠️  KAKAO_REST_API_KEY가 설정되지 않았습니다.")
        print("   아래 방법 중 하나로 키를 설정하세요:\n")
        print("   방법 1) 환경변수 설정:")
        print("     export KAKAO_REST_API_KEY=your_key_here")
        print("     python scripts/crawl_kakao_places.py\n")
        print("   방법 2) 이 스크립트 상단 KAKAO_REST_API_KEY 변수에 직접 입력\n")
        print("   카카오 REST API 키 발급:")
        print("   1. https://developers.kakao.com 접속 후 로그인")
        print("   2. [내 애플리케이션] → [애플리케이션 추가하기]")
        print("   3. 앱 이름 입력 (예: 이스케이프맵) → 저장")
        print("   4. [앱 키] 탭에서 'REST API 키' 복사")
        print("   5. [카카오 로컬] API 활성화 확인 (기본 활성화됨)")
        return

    start_time = time.time()
    places = crawl()
    elapsed = time.time() - start_time

    print(f"\n{'=' * 60}")
    print(f"✅ 수집 완료!")
    print(f"   총 방탈출 카페: {len(places)}개")
    print(f"   소요 시간: {elapsed:.0f}초 ({elapsed/60:.1f}분)")

    # 지역별 분포 출력
    area_count: dict[str, int] = {}
    for p in places:
        addr = p.get("address", "") or p.get("road_address", "")
        # 주소에서 구 이름 추출
        parts = addr.split()
        gu = next((part for part in parts if part.endswith("구")), "기타")
        area_count[gu] = area_count.get(gu, 0) + 1

    print(f"\n   구별 분포 (상위 10개):")
    for gu, cnt in sorted(area_count.items(), key=lambda x: -x[1])[:10]:
        print(f"     {gu}: {cnt}개")

    # JSON 파일 저장
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = {
        "crawled_at": datetime.now().isoformat(),
        "total": len(places),
        "places": places,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n   결과 저장: {OUTPUT_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    main()
