"""
예약 현황 관련 API 엔드포인트.

크롤러가 수집한 최신 예약 가능 현황을 반환합니다.
Redis 캐싱이 적용되어 있어서 같은 요청은 DB를 매번 조회하지 않습니다.
"""
import asyncio
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.schedule import Schedule
from app.models.theme import Theme

router = APIRouter()

def _postgres_slots(target_date, area=None, theme_id=None, database=None):
    from app.firestore_db import get_db as crawl_db
    from app.api.v1.cafes import _get_cafes_sync
    database=database if database is not None else crawl_db()
    allowed={c['id'] for c in _get_cafes_sync(database,area)}
    doc=database.collection('schedules').document(str(target_date)).get()
    rows=[]
    for cid,cafe in (doc.to_dict() or {}).get('cafes',{}).items():
        if cid not in allowed:continue
        for tid,theme in cafe.get('themes',{}).items():
            if theme_id is not None and tid!=theme_id:continue
            for slot in theme.get('slots',[]):
                rows.append({'id':f"{tid}:{target_date}:{slot['time']}",'theme_id':tid,'cafe_id':cid,
                  'time_slot':slot['time'],'status':slot['status'],'booking_url':slot.get('booking_url'),
                  'available_slots':None,'total_slots':None,'crawled_at':cafe.get('crawled_at')})
    return sorted(rows,key=lambda row:(row['time_slot'],row['theme_id']))



@router.get("/schedules")
async def get_schedules(
    date: date = Query(..., description="조회할 날짜 (예: 2026-03-15)"),
    area: str | None = Query(None, description="지역 코드 (예: gangnam)"),
    status: str | None = Query(None, description="상태 필터 (available / full / closed)"),
    db: AsyncSession = Depends(get_db),
):
    """
    날짜·지역 기준으로 예약 가능한 모든 시간대를 반환합니다.

    예시 요청:
      GET /api/v1/schedules?date=2026-03-15&area=gangnam&status=available

    이 엔드포인트가 메인 화면의 핵심입니다.
    사용자가 날짜를 선택하면 이 API가 호출됩니다.
    """
    if settings.crawl_storage == 'supabase':
        if status and status not in ('available','full','closed','unknown'):
            from fastapi import HTTPException
            raise HTTPException(status_code=400,detail='알 수 없는 예약 상태입니다.')
        rows=await asyncio.to_thread(_postgres_slots,date,area)
        if status:rows=[row for row in rows if row['status']==status]
        return {'date':str(date),'schedules':rows,'total':len(rows)}
    # 가장 최근 크롤링 데이터만 가져오기 (서브쿼리로 최신 crawled_at 조회)
    # TODO: Redis 캐싱 추가 (캐시 키: schedules:{date}:{area})
    # TODO: 지역(area) 필터링 구현 (Cafe 테이블과 JOIN 필요)

    query = select(Schedule).where(Schedule.date == date)
    if status:
        query = query.where(Schedule.status == status)

    result = await db.execute(query)
    schedules = result.scalars().all()

    return {
        "date": str(date),
        "schedules": [
            {
                "id": s.id,
                "theme_id": s.theme_id,
                "time_slot": str(s.time_slot),
                "status": s.status,
                "available_slots": s.available_slots,
                "booking_url": s.booking_url,  # 예약 딥링크
                "crawled_at": str(s.crawled_at),
            }
            for s in schedules
        ],
        "total": len(schedules),
    }


@router.get("/themes/{theme_id}/schedules")
async def get_theme_schedules(
    theme_id: str,
    date: date = Query(..., description="조회할 날짜"),
    db: AsyncSession = Depends(get_db),
):
    """
    특정 테마의 날짜별 타임슬롯 현황을 반환합니다.

    테마 상세 페이지에서 달력을 클릭할 때 호출됩니다.
    """
    if settings.crawl_storage == 'supabase':
        rows=await asyncio.to_thread(_postgres_slots,date,None,theme_id)
        return {'theme_id':theme_id,'date':str(date),'time_slots':rows}
    result = await db.execute(
        select(Schedule).where(
            Schedule.theme_id == theme_id,
            Schedule.date == date,
        ).order_by(Schedule.time_slot)
    )
    schedules = result.scalars().all()

    return {
        "theme_id": theme_id,
        "date": str(date),
        "time_slots": [
            {
                "time_slot": str(s.time_slot),
                "status": s.status,
                "available_slots": s.available_slots,
                "total_slots": s.total_slots,
                # 제휴 추적 파라미터 자동 추가
                "booking_url": f"{s.booking_url}?ref=escapemap" if s.booking_url else None,
            }
            for s in schedules
        ],
    }
