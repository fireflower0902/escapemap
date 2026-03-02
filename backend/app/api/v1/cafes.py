"""
카페 관련 API 엔드포인트.

프론트엔드가 "강남 방탈출 카페 목록을 보여줘"라고 요청하면
이 파일의 함수들이 응답합니다.
"""
from datetime import date as Date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.cafe import Cafe
from app.models.theme import Theme
from app.models.schedule import Schedule

router = APIRouter()

# 지역 코드 → 주소 prefix 매핑
AREA_ADDRESS_MAP: dict[str, list[str]] = {
    "gangnam":    ["서울 강남구", "서울 서초구"],
    "hongdae":    ["서울 마포구"],
    "sinchon":    ["서울 서대문구"],
    "jamsil":     ["서울 송파구", "서울 강동구"],
    "itaewon":    ["서울 용산구"],
    "myeongdong": ["서울 중구", "서울 종로구"],
    "daehakro":   ["서울 종로구"],
    "sinlim":     ["서울 관악구"],
    "busan":      ["부산"],
    "daegu":      ["대구"],
    "gwangju":    ["광주"],
    "daejeon":    ["대전"],
    "incheon":    ["인천"],
    "ulsan":      ["울산"],
    "jeju":       ["제주"],
    "gyeonggi":   ["경기"],
    "gangwon":    ["강원"],
}


def _area_filter(area: str | None):
    """area 코드를 주소 prefix 필터 조건으로 변환."""
    if not area or area not in AREA_ADDRESS_MAP:
        return None
    prefixes = AREA_ADDRESS_MAP[area]
    return or_(*[Cafe.address.like(f"{p}%") for p in prefixes])


@router.get("/cafes")
async def get_cafes(
    area: str | None = Query(None, description="지역 코드 (예: gangnam, hongdae, busan)"),
    db: AsyncSession = Depends(get_db),
):
    """
    지역 기준으로 방탈출 카페 목록을 반환합니다.

    예시 요청:
      GET /api/v1/cafes
      GET /api/v1/cafes?area=gangnam
    """
    query = select(Cafe).where(Cafe.is_active == True)
    f = _area_filter(area)
    if f is not None:
        query = query.where(f)
    query = query.order_by(Cafe.address, Cafe.name)

    result = await db.execute(query)
    cafes = result.scalars().all()

    return {
        "cafes": [
            {
                "id": c.id,
                "name": c.name,
                "branch_name": c.branch_name,
                "address": c.address,
                "phone": c.phone,
                "website_url": c.website_url,
                "lat": c.lat,
                "lng": c.lng,
            }
            for c in cafes
        ],
        "total": len(cafes),
        "area": area,
    }


@router.get("/search")
async def search(
    date: Date = Query(..., description="조회 날짜 (YYYY-MM-DD)"),
    area: str | None = Query(None, description="지역 코드"),
    db: AsyncSession = Depends(get_db),
):
    """
    날짜 + 지역으로 카페·테마·예약 가능 시간대를 한 번에 반환합니다.
    프론트 검색 페이지가 이 엔드포인트를 호출합니다.

    예시:
      GET /api/v1/search?date=2026-03-02&area=gangnam
    """
    # 1) 카페 목록 (지역 필터)
    cafe_query = select(Cafe).where(Cafe.is_active == True)
    f = _area_filter(area)
    if f is not None:
        cafe_query = cafe_query.where(f)
    cafe_query = cafe_query.order_by(Cafe.address, Cafe.name)
    cafe_result = await db.execute(cafe_query)
    cafes = cafe_result.scalars().all()

    cafe_ids = [c.id for c in cafes]
    if not cafe_ids:
        return {"date": str(date), "area": area, "cafes": [], "total": 0}

    # 2) 해당 카페들의 테마 목록
    theme_result = await db.execute(
        select(Theme).where(
            Theme.cafe_id.in_(cafe_ids),
            Theme.is_active == True,
        )
    )
    themes = theme_result.scalars().all()
    theme_ids = [t.id for t in themes]

    # 3) 해당 날짜의 스케줄 (테마별·시간대별 최신 레코드만)
    schedule_result = await db.execute(
        select(Schedule).where(
            Schedule.theme_id.in_(theme_ids),
            Schedule.date == date,
        ).order_by(Schedule.theme_id, Schedule.time_slot, Schedule.crawled_at.desc())
    )
    all_schedules = schedule_result.scalars().all()

    # theme_id + time_slot 기준 최신 레코드만 유지
    seen: set[tuple] = set()
    latest_schedules: list[Schedule] = []
    for s in all_schedules:
        key = (s.theme_id, str(s.time_slot))
        if key not in seen:
            seen.add(key)
            latest_schedules.append(s)

    # 4) 구조 조립: cafe → themes → slots
    theme_map: dict[str, list[Theme]] = {}
    for t in themes:
        theme_map.setdefault(t.cafe_id, []).append(t)

    schedule_map: dict[int, list[Schedule]] = {}
    for s in latest_schedules:
        schedule_map.setdefault(s.theme_id, []).append(s)

    cafes_out = []
    for cafe in cafes:
        cafe_themes = theme_map.get(cafe.id, [])
        if cafe_themes:
            themes_out = []
            for theme in cafe_themes:
                slots = schedule_map.get(theme.id, [])
                slots_out = sorted(
                    [
                        {
                            "time":        str(s.time_slot)[:5],
                            "status":      s.status,
                            "booking_url": s.booking_url,
                        }
                        for s in slots
                    ],
                    key=lambda x: x["time"],
                )
                themes_out.append({
                    "id":           theme.id,
                    "name":         theme.name,
                    "difficulty":   theme.difficulty,
                    "duration_min": theme.duration_min,
                    "poster_url":   theme.poster_url,
                    "slots":        slots_out,
                })
            cafes_out.append({
                "id":          cafe.id,
                "name":        cafe.name,
                "branch_name": cafe.branch_name,
                "address":     cafe.address,
                "website_url": cafe.website_url,
                "crawled":     True,
                "themes":      themes_out,
            })
        elif cafe.website_url:
            # 아직 크롤링 안 된 카페 — 공식 사이트가 있는 경우만 포함
            cafes_out.append({
                "id":          cafe.id,
                "name":        cafe.name,
                "branch_name": cafe.branch_name,
                "address":     cafe.address,
                "website_url": cafe.website_url,
                "crawled":     False,
                "themes":      [],
            })

    return {
        "date":  str(date),
        "area":  area,
        "cafes": cafes_out,
        "total": len(cafes_out),
    }


@router.get("/cafes/{cafe_id}")
async def get_cafe_detail(
    cafe_id: str,
    db: AsyncSession = Depends(get_db),
):
    """특정 카페의 상세 정보를 반환합니다."""
    result = await db.execute(select(Cafe).where(Cafe.id == cafe_id))
    cafe = result.scalar_one_or_none()

    if not cafe:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="카페를 찾을 수 없습니다.")

    return {
        "id": cafe.id,
        "name": cafe.name,
        "branch_name": cafe.branch_name,
        "address": cafe.address,
        "phone": cafe.phone,
        "website_url": cafe.website_url,
        "lat": cafe.lat,
        "lng": cafe.lng,
    }


@router.get("/cafes/{cafe_id}/themes")
async def get_cafe_themes(
    cafe_id: str,
    db: AsyncSession = Depends(get_db),
):
    """특정 카페의 테마 목록을 반환합니다."""
    result = await db.execute(
        select(Theme).where(Theme.cafe_id == cafe_id, Theme.is_active == True)
    )
    themes = result.scalars().all()

    return {
        "cafe_id": cafe_id,
        "themes": [
            {
                "id": t.id,
                "name": t.name,
                "difficulty": t.difficulty,
                "min_players": t.min_players,
                "max_players": t.max_players,
                "duration_min": t.duration_min,
                "poster_url": t.poster_url,
            }
            for t in themes
        ],
    }
