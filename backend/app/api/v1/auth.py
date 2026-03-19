"""
사용자 인증 관련 API 엔드포인트.
Firebase Authentication ID 토큰을 검증하고 Firestore에 유저 정보를 저장합니다.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from firebase_admin import auth as firebase_auth
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.firestore_db import get_db as get_firestore
from app.models.user import User

router = APIRouter()


# ── Firebase 토큰 검증 helper ─────────────────────────────────────────────────

def _verify_token(request: Request) -> dict:
    """Authorization: Bearer <idToken> 헤더에서 Firebase ID 토큰을 검증합니다."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="인증 토큰이 없습니다.")
    token = auth_header.removeprefix("Bearer ").strip()
    try:
        return firebase_auth.verify_id_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.")


# ── Firebase 소셜 로그인 엔드포인트 ──────────────────────────────────────────

@router.post("/auth/me", status_code=200)
async def upsert_me(request: Request):
    """
    Firebase ID 토큰을 검증하고 Firestore users/{uid} 문서를 생성(또는 갱신)합니다.
    소셜 로그인 후 프론트엔드가 최초 1회 호출합니다.
    """
    decoded = _verify_token(request)
    uid = decoded["uid"]
    now = datetime.now(timezone.utc).isoformat()

    db = get_firestore()
    user_ref = db.collection("users").document(uid)
    doc = user_ref.get()

    if doc.exists:
        # 기존 유저: last_login_at 만 갱신
        user_ref.update({"last_login_at": now})
        return {"uid": uid, "is_new": False}
    else:
        # 신규 유저: 문서 생성
        user_ref.set({
            "uid":               uid,
            "provider":          decoded.get("firebase", {}).get("sign_in_provider", "unknown"),
            "email":             decoded.get("email", ""),
            "nickname":          decoded.get("name", ""),
            "profile_image_url": decoded.get("picture", ""),
            "created_at":        now,
            "last_login_at":     now,
        })
        return {"uid": uid, "is_new": True}


@router.get("/auth/me", status_code=200)
async def get_me(request: Request):
    """현재 로그인한 유저 정보를 Firestore에서 반환합니다."""
    decoded = _verify_token(request)
    uid = decoded["uid"]

    db = get_firestore()
    doc = get_firestore().collection("users").document(uid).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="유저를 찾을 수 없습니다.")
    return doc.to_dict()


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
