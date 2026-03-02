"""
방탈출 카페(지점) 정보 테이블.

카카오맵에서 수집한 카페의 기본 신상정보를 저장합니다.
테마 목록은 theme 테이블에 별도 저장됩니다.
"""
from datetime import datetime

from sqlalchemy import String, Text, Float, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Cafe(Base):
    __tablename__ = "cafe"

    # 카카오맵의 고유 장소 ID를 기본키로 사용
    # 예: "1234567890"
    id: Mapped[str] = mapped_column(String, primary_key=True)

    name: Mapped[str] = mapped_column(String, nullable=False)           # 카페 이름 (예: "키이스케이프")
    branch_name: Mapped[str | None] = mapped_column(String)             # 지점명 (예: "강남점")
    address: Mapped[str | None] = mapped_column(Text)                   # 주소
    phone: Mapped[str | None] = mapped_column(String)                   # 전화번호
    website_url: Mapped[str | None] = mapped_column(Text)               # 웹사이트 URL
    engine: Mapped[str | None] = mapped_column(String)                  # 사용 중인 예약 엔진 (예: "keyescape", "naver")
    lat: Mapped[float | None] = mapped_column(Float)                    # 위도
    lng: Mapped[float | None] = mapped_column(Float)                    # 경도
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)      # 활성 여부 (폐업 시 False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # 이 카페에 속한 테마 목록 (1:N 관계)
    # cafe.themes 로 접근 가능
    themes: Mapped[list["Theme"]] = relationship("Theme", back_populates="cafe")
