"""예약 상태 누락/실패를 빈자리로 해석하지 않는 공통 검증."""
def reservation_status(value, field='reservation'):
    if not isinstance(value, bool):
        raise ValueError(f'{field}: 예약 여부가 명시된 JSON boolean이 아닙니다.')
    return 'full' if value else 'available'


def require_reservation_feed(raw):
    if not isinstance(raw, dict) or not isinstance(raw.get('theme_data'), list) or not isinstance(raw.get('reserv_data'), list):
        raise ValueError('테마/예약완료 목록 응답을 모두 확인하지 못했습니다.')
    required={'reserv_date','reserv_time','theme_name'}
    if any(not isinstance(row,dict) or not required.issubset(row) for row in raw['reserv_data']):
        raise ValueError('예약완료 목록 형식이 변경되었습니다.')
    return raw['theme_data'], raw['reserv_data']


def service_slot_datetime(day, clock):
    """영업일의 24~29시를 다음 날 시각으로 비교하되 저장 표기는 유지한다."""
    from datetime import datetime, timedelta
    import re
    if not isinstance(clock, str) or not re.fullmatch(r'(?:[01]\d|2\d):[0-5]\d', clock):
        raise ValueError(f'잘못된 영업 시간: {clock!r}')
    hh, mm = map(int, clock.split(':'))
    return datetime.combine(day, datetime.min.time()) + timedelta(hours=hh, minutes=mm)
