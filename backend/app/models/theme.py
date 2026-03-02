"""
방탈출 테마 정보 테이블.

하나의 카페(Cafe)는 여러 테마를 운영합니다.
테마별 예약 현황은 schedule 테이블에 저장됩니다.
"""
from sqlalchemy import String, Text, Integer, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Theme(Base):
    __tablename__ = "theme"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cafe_id: Mapped[str] = mapped_column(String, ForeignKey("cafe.id"), nullable=False)

    name: Mapped[str] = mapped_column(String, nullable=False)          # 테마명 (예: "셜록홈즈")
    description: Mapped[str | None] = mapped_column(Text)              # 테마 설명
    difficulty: Mapped[int | None] = mapped_column(Integer)            # 난이도 1~5
    min_players: Mapped[int | None] = mapped_column(Integer)           # 최소 인원
    max_players: Mapped[int | None] = mapped_column(Integer)           # 최대 인원
    duration_min: Mapped[int | None] = mapped_column(Integer)          # 소요 시간 (분 단위, 예: 70)
    poster_url: Mapped[str | None] = mapped_column(Text)               # 테마 포스터 이미지 URL
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)     # 운영 여부

    # 관계 설정
    cafe: Mapped["Cafe"] = relationship("Cafe", back_populates="themes")
    schedules: Mapped[list["Schedule"]] = relationship("Schedule", back_populates="theme")
    alerts: Mapped[list["Alert"]] = relationship("Alert", back_populates="theme")
