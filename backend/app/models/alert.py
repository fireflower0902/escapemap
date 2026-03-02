"""
빈자리 알림 신청 테이블.

사용자가 특정 테마·날짜·시간대에 알림을 신청하면 이 테이블에 저장됩니다.
크롤러가 해당 시간대가 'available'로 바뀌면 알림을 발송하고,
is_sent를 True로 업데이트하여 중복 발송을 방지합니다.
"""
from datetime import date, time, datetime

from sqlalchemy import Integer, String, Date, Time, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Alert(Base):
    __tablename__ = "alert"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)
    theme_id: Mapped[int] = mapped_column(Integer, ForeignKey("theme.id"), nullable=False)

    date: Mapped[date] = mapped_column(Date, nullable=False)            # 알림 받을 날짜
    time_slot: Mapped[time | None] = mapped_column(Time)               # 특정 시간대 (NULL이면 해당 날짜 전체)
    channel: Mapped[str] = mapped_column(String, nullable=False)        # 알림 수단: "email" | "kakao"
    is_sent: Mapped[bool] = mapped_column(Boolean, default=False)       # 발송 완료 여부
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)          # 실제 발송 시각

    user: Mapped["User"] = relationship("User", back_populates="alerts")
    theme: Mapped["Theme"] = relationship("Theme", back_populates="alerts")
