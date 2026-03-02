"""
카카오 수집 JSON → SQLite DB 임포트 스크립트

실행:
  cd escape-aggregator/backend
  python scripts/import_kakao_to_db.py [JSON_파일_경로]

  파일 경로를 생략하면 data/ 폴더에서 가장 최신 파일을 자동으로 선택합니다.

동작:
  - 서울 주소만 필터링 (경기도·인천 등 제외)
  - place_name → name + branch_name 자동 분리
  - 이미 존재하는 카페(place_id 중복)는 업데이트 (upsert)
  - 테이블이 없으면 자동 생성
"""

import asyncio
import json
import sys
from pathlib import Path

# backend/ 폴더를 sys.path에 추가 (app 패키지 import 용)
BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select
from app.database import AsyncSessionLocal, engine, Base
from app.models.cafe import Cafe  # noqa: E402


# ── 유틸 ────────────────────────────────────────────────────────────


def parse_name(place_name: str) -> tuple[str, str | None]:
    """
    카카오 place_name에서 카페 이름과 지점명을 분리합니다.

    예:
      "키이스케이프 강남점"     → ("키이스케이프", "강남점")
      "비트포비아 강남 던전점"   → ("비트포비아", "강남 던전점")
      "탈출공작소"             → ("탈출공작소", None)
    """
    BRANCH_SUFFIXES = ("점", "지점", "본점")

    # 뒤에서부터 공백으로 나눠가며 지점명 suffix 확인
    parts = place_name.split(" ")
    for i in range(len(parts) - 1, 0, -1):
        if any(parts[-1].endswith(s) for s in BRANCH_SUFFIXES):
            # 마지막 단어가 지점명 suffix로 끝나면
            # → 마지막 단어 또는 마지막 두 단어(+지역어 포함)를 branch로 분리
            # "강남 던전점" 같은 경우 마지막 단어만 체크
            branch = " ".join(parts[i:])
            name = " ".join(parts[:i])
            return name, branch
        break

    return place_name, None


def is_seoul(place: dict) -> bool:
    """서울 주소인지 확인"""
    addr = place.get("address", "") or place.get("road_address", "") or ""
    return addr.startswith("서울")


def find_latest_json() -> Path:
    """data/ 폴더에서 가장 최신 kakao_places_*.json 파일 반환"""
    data_dir = BACKEND_DIR / "data"
    files = sorted(data_dir.glob("kakao_places_*.json"), reverse=True)
    if not files:
        raise FileNotFoundError(f"data/ 폴더에 kakao_places_*.json 파일이 없습니다.")
    return files[0]


# ── DB 작업 ──────────────────────────────────────────────────────────


async def create_tables():
    """모든 모델 테이블 생성 (없을 경우)"""
    from app.models import cafe, theme, schedule, user, alert  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("  테이블 생성 완료 (또는 이미 존재)")


async def upsert_cafes(places: list[dict]) -> tuple[int, int]:
    """
    카페 목록을 DB에 삽입/업데이트합니다.
    Returns: (inserted, updated) 개수
    """
    inserted = 0
    updated = 0

    async with AsyncSessionLocal() as session:
        for p in places:
            place_id = p["place_id"]
            name, branch = parse_name(p["place_name"])

            existing = await session.get(Cafe, place_id)

            if existing is None:
                cafe = Cafe(
                    id=place_id,
                    name=name,
                    branch_name=branch,
                    address=p.get("road_address") or p.get("address"),
                    phone=p.get("phone"),
                    website_url=p.get("website_url"),
                    lat=p.get("lat"),
                    lng=p.get("lng"),
                    is_active=True,
                )
                session.add(cafe)
                inserted += 1
            else:
                # 주소·전화번호 등 정보 업데이트
                existing.name = name
                existing.branch_name = branch
                existing.address = p.get("road_address") or p.get("address")
                existing.phone = p.get("phone")
                existing.lat = p.get("lat")
                existing.lng = p.get("lng")
                updated += 1

        await session.commit()

    return inserted, updated


# ── 메인 ─────────────────────────────────────────────────────────────


async def main():
    print("=" * 60)
    print("카카오 수집 데이터 → DB 임포트")
    print("=" * 60)

    # JSON 파일 결정
    if len(sys.argv) > 1:
        json_path = Path(sys.argv[1])
    else:
        json_path = find_latest_json()

    print(f"\n  입력 파일: {json_path.name}")

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    all_places = data["places"]
    total = len(all_places)
    print(f"  전체 장소: {total}개")

    # 서울만 필터
    seoul_places = [p for p in all_places if is_seoul(p)]
    excluded = total - len(seoul_places)
    print(f"  서울 필터: {len(seoul_places)}개 (경기도 등 {excluded}개 제외)")

    # 테이블 생성
    print("\n  DB 테이블 확인 중...")
    await create_tables()

    # 삽입
    print("\n  카페 데이터 삽입 중...")
    inserted, updated = await upsert_cafes(seoul_places)

    print(f"\n{'=' * 60}")
    print(f"  완료!")
    print(f"   신규 삽입: {inserted}개")
    print(f"   업데이트 : {updated}개")
    print(f"   합계     : {inserted + updated}개")

    # 구별 통계 출력
    area_count: dict[str, int] = {}
    for p in seoul_places:
        addr = p.get("address", "") or p.get("road_address", "") or ""
        parts = addr.split()
        gu = next((w for w in parts if w.endswith("구")), "기타")
        area_count[gu] = area_count.get(gu, 0) + 1

    print(f"\n  구별 분포 (상위 10개):")
    for gu, cnt in sorted(area_count.items(), key=lambda x: -x[1])[:10]:
        bar = "█" * cnt
        print(f"    {gu:8s} {cnt:3d}개  {bar}")

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
