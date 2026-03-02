"""
빈자리 알림 관련 API 엔드포인트.

사용자가 "이 테마 빈자리 나면 알려줘"를 등록/취소합니다.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import date, time
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.alert import Alert

router = APIRouter()


# 알림 등록 요청 데이터 형식 정의
class AlertCreateRequest(BaseModel):
    user_id: int
    theme_id: int
    date: date
    time_slot: time | None = None  # None이면 해당 날짜 전체
    channel: str                    # "email" | "kakao"


@router.post("/alerts", status_code=201)
async def create_alert(
    request: AlertCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    빈자리 알림을 등록합니다.

    예시 요청 본문:
      {
        "user_id": 1,
        "theme_id": 5,
        "date": "2026-03-20",
        "time_slot": "15:00",
        "channel": "email"
      }
    """
    if request.channel not in ("email", "kakao"):
        raise HTTPException(status_code=400, detail="channel은 'email' 또는 'kakao'여야 합니다.")

    alert = Alert(
        user_id=request.user_id,
        theme_id=request.theme_id,
        date=request.date,
        time_slot=request.time_slot,
        channel=request.channel,
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)

    return {"message": "알림이 등록되었습니다.", "alert_id": alert.id}


@router.delete("/alerts/{alert_id}")
async def delete_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
):
    """알림 등록을 취소합니다."""
    from sqlalchemy import select
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(status_code=404, detail="알림을 찾을 수 없습니다.")

    await db.delete(alert)
    await db.commit()

    return {"message": "알림이 취소되었습니다."}
