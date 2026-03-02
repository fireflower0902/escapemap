"""
예약 현황 스냅샷 테이블.

크롤러가 15분마다 수집한 "그 시점의 예약 가능 여부"를 저장합니다.
같은 테마·날짜·시간이라도 크롤 시각(crawled_at)이 다르면 별개의 행으로 저장됩니다.
→ 나중에 "언제 빈자리가 났는지" 추적이 가능합니다.
"""
from datetime import date, time, datetime

from sqlalchemy import Integer, Date, Time, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Schedule(Base):
    __tablename__ = "schedule"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    theme_id: Mapped[int] = mapped_column(Integer, ForeignKey("theme.id"), nullable=False)

    date: Mapped[date] = mapped_column(Date, nullable=False)            # 예약 날짜 (예: 2026-03-15)
    time_slot: Mapped[time] = mapped_column(Time, nullable=False)       # 예약 시간대 (예: 14:00)
    available_slots: Mapped[int | None] = mapped_column(Integer)        # 남은 자리 수
    total_slots: Mapped[int | None] = mapped_column(Integer)            # 총 자리 수
    status: Mapped[str] = mapped_column(String, nullable=False)         # available / full / closed
    booking_url: Mapped[str | None] = mapped_column(Text)              # 해당 시간대 직접 예약 링크
    crawled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)  # 크롤링 시각

    # 같은 테마·날짜·시간·크롤 시각 조합은 중복 저장 방지
    __table_args__ = (
        UniqueConstraint("theme_id", "date", "time_slot", "crawled_at"),
    )

    theme: Mapped["Theme"] = relationship("Theme", back_populates="schedules")
