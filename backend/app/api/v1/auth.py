"""
사용자 인증 관련 API 엔드포인트.

알림을 받으려면 계정이 필요합니다.
이메일 또는 카카오 로그인을 지원합니다.

⚠️  MVP 단계에서는 단순 이메일 등록만 구현합니다.
    JWT 토큰, OAuth 로그인은 Phase 6 이후에 추가 예정.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User

router = APIRouter()


class RegisterRequest(BaseModel):
    email: EmailStr  # 이메일 형식 자동 검증 (Pydantic이 처리)


@router.post("/auth/register", status_code=201)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    이메일로 회원가입합니다.

    예시 요청:
      { "email": "user@example.com" }
    """
    # 이미 가입된 이메일인지 확인
    result = await db.execute(select(User).where(User.email == request.email))
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=409, detail="이미 가입된 이메일입니다.")

    user = User(email=request.email)
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return {"message": "회원가입이 완료되었습니다.", "user_id": user.id}


@router.post("/auth/login")
async def login(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    이메일로 로그인합니다. (MVP: 이메일 존재 여부만 확인)

    TODO: 추후 이메일 인증 코드 또는 JWT 토큰 방식으로 업그레이드
    """
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="가입되지 않은 이메일입니다.")

    return {"message": "로그인 성공", "user_id": user.id}
