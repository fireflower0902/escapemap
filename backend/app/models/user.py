"""
서비스 사용자 테이블.

빈자리 알림을 받으려면 계정이 필요합니다.
이메일 또는 카카오 로그인 중 하나로 가입 가능합니다.
"""
from datetime import datetime

from sqlalchemy import Integer, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str | None] = mapped_column(String, unique=True)      # 이메일 (이메일 가입 시)
    kakao_id: Mapped[str | None] = mapped_column(String, unique=True)   # 카카오 고유 ID (카카오 로그인 시)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # 이 사용자가 등록한 알림 목록
    alerts: Mapped[list["Alert"]] = relationship("Alert", back_populates="user")
