"""예약 사이트의 영업일 기준 시간(24:00 등)을 비교 가능한 시각으로 변환."""
from datetime import date, datetime, time, timedelta


def business_slot_datetime(day: date, hour: int, minute: int) -> datetime:
    # 24:30은 해당 영업일의 다음 날 00:30. 저장/예약 URL에는 원문 시간을 유지.
    if not 0 <= hour <= 29 or not 0 <= minute <= 59:
        raise ValueError(f'잘못된 영업 시간: {hour:02d}:{minute:02d}')
    return datetime.combine(day, time.min) + timedelta(hours=hour, minutes=minute)
