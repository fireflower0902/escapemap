"""
카카오에서 누락된 비트포비아 지점 10개를 DB에 추가하는 스크립트

누락 원인: 전국 크롤링 시 is_escape_room() 필터가 "방탈출/이스케이프/escape/탈출"
키워드를 요구하는데, 비트포비아 던전 지점명에는 해당 키워드가 없음.

실행:
  cd escape-aggregator/backend
  python scripts/add_missing_bitfobia.py
"""

import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.database import AsyncSessionLocal, engine, Base
from app.models.cafe import Cafe  # noqa: E402
from sqlalchemy import select

# ── 추가할 카페 목록 (카카오 API 기준) ────────────────────────────────────
# xdungeon.net 지점 (던전 시리즈)
XDUNGEON_URL = "https://xdungeon.net/"
# xphobia.net 지점 (구형 비트포비아)
XPHOBIA_URL = "https://www.xphobia.net/"

MISSING_CAFES = [
    # xdungeon.net 던전 시리즈
    {
        "id": "27413263",
        "name": "비트포비아",
        "branch_name": "강남던전점",
        "address": "서울 강남구 강남대로84길 33",
        "phone": "02-555-4360",
        "lat": 37.497583697643,
        "lng": 127.031112213726,
        "website_url": XDUNGEON_URL,
    },
    {
        "id": "1246652450",
        "name": "비트포비아",
        "branch_name": "홍대던전점",
        "address": "서울 마포구 독막로3길 30",
        "phone": "02-322-4997",
        "lat": 37.5495719511011,
        "lng": 126.917362781288,
        "website_url": XDUNGEON_URL,
    },
    {
        "id": "1322241204",
        "name": "비트포비아",
        "branch_name": "서면던전점",
        "address": "부산 부산진구 동천로 66",
        "phone": "051-818-4888",
        "lat": 35.15463893230701,
        "lng": 129.0625884696947,
        "website_url": XDUNGEON_URL,
    },
    {
        "id": "1772808576",
        "name": "비트포비아 던전101",
        "branch_name": None,
        "address": "서울 마포구 와우산로 74",
        "phone": "02-3144-2342",
        "lat": 37.5509978541843,
        "lng": 126.923488046863,
        "website_url": XDUNGEON_URL,
    },
    {
        "id": "2070160321",
        "name": "비트포비아",
        "branch_name": "홍대던전3",
        "address": "서울 마포구 와우산로29길 21",
        "phone": "02-3141-9421",
        "lat": 37.554920382572,
        "lng": 126.928576800907,
        "website_url": XDUNGEON_URL,
    },
    {
        "id": "1769092819",
        "name": "비트포비아",
        "branch_name": "강남던전2",
        "address": "서울 강남구 테헤란로4길 32",
        "phone": "02-501-0323",
        "lat": 37.49628289411766,
        "lng": 127.03014819829872,
        "website_url": XDUNGEON_URL,
    },
    # xphobia.net 지점 (구형 비트포비아)
    {
        "id": "1432484184",
        "name": "비트포비아",
        "branch_name": "대학로점",
        "address": "서울 종로구 대학로10길 12",
        "phone": "02-742-5252",
        "lat": 37.5815897995095,
        "lng": 127.002816737441,
        "website_url": XPHOBIA_URL,
    },
    {
        "id": "1183396756",
        "name": "비트포비아",
        "branch_name": "명동점",
        "address": "서울 중구 명동10길 13",
        "phone": "02-3789-8094",
        "lat": 37.5632518768111,
        "lng": 126.985381004262,
        "website_url": XPHOBIA_URL,
    },
    {
        "id": "1647497159",
        "name": "비트포비아",
        "branch_name": "신림점",
        "address": "서울 관악구 신림로59길 9",
        "phone": "02-878-2139",
        "lat": 37.4829521972144,
        "lng": 126.929131538582,
        "website_url": XPHOBIA_URL,
    },
    {
        "id": "997297045",
        "name": "비트포비아",
        "branch_name": "동성로점",
        "address": "대구 중구 동성로6길 33",
        "phone": "070-5102-4760",
        "lat": 35.8688586362438,
        "lng": 128.597357218815,
        "website_url": XPHOBIA_URL,
    },
]


async def add_missing_cafes():
    added = 0
    skipped = 0

    async with AsyncSessionLocal() as session:
        for data in MISSING_CAFES:
            existing = await session.get(Cafe, data["id"])
            if existing:
                print(f"  [SKIP] {data['name']} {data['branch_name'] or ''} (이미 존재)")
                skipped += 1
                continue

            cafe = Cafe(
                id=data["id"],
                name=data["name"],
                branch_name=data["branch_name"],
                address=data["address"],
                phone=data["phone"],
                lat=data["lat"],
                lng=data["lng"],
                website_url=data["website_url"],
                engine=None,
                is_active=True,
            )
            session.add(cafe)
            print(f"  [ADD ] {data['name']} {data['branch_name'] or ''} | {data['address']}")
            added += 1

        await session.commit()

    return added, skipped


async def main():
    print("=" * 60)
    print("누락된 비트포비아 지점 DB 추가")
    print("=" * 60)

    # 테이블 확인
    from app.models import cafe, theme, schedule, user, alert  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    added, skipped = await add_missing_cafes()

    print(f"\n  추가: {added}개 / 스킵: {skipped}개")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
