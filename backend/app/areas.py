"""전국 지역 분류. 기존 크롤러 지역 코드는 유지하고 주소로 누락 분류를 보완합니다."""
from __future__ import annotations

SEOUL_AREAS = {
    'gangnam', 'hongdae', 'sinchon', 'konkuk', 'jamsil', 'itaewon',
    'myeongdong', 'daehakro', 'sinlim', 'seongsu', 'seoul_other',
}
PROVINCE_PREFIXES = {
    'busan': ('부산',), 'daegu': ('대구',), 'incheon': ('인천',),
    'gwangju': ('광주',), 'daejeon': ('대전',), 'ulsan': ('울산',),
    'sejong': ('세종',), 'gyeonggi': ('경기',), 'gangwon': ('강원',),
    'chungbuk': ('충북', '충청북도'), 'chungnam': ('충남', '충청남도'),
    'jeonbuk': ('전북', '전라북도'), 'jeonnam': ('전남', '전라남도'),
    'gyeongbuk': ('경북', '경상북도'), 'gyeongnam': ('경남', '경상남도'),
    'jeju': ('제주',),
}
SUPPORTED_AREAS = SEOUL_AREAS | set(PROVINCE_PREFIXES) | {'cheonan', 'etc'}
QUERY_AREAS = SUPPORTED_AREAS | {'all', 'seoul'}
SEOUL_DISTRICTS = {
    '강남구': 'gangnam', '서초구': 'gangnam', '마포구': 'hongdae',
    '서대문구': 'sinchon', '광진구': 'konkuk', '송파구': 'jamsil',
    '강동구': 'jamsil', '용산구': 'itaewon', '중구': 'myeongdong',
    '종로구': 'myeongdong', '관악구': 'sinlim', '성동구': 'seongsu',
}


def address_to_area(address: str) -> str:
    address = (address or '').strip()
    if address.startswith('서울'):
        parts = address.split()
        return SEOUL_DISTRICTS.get(parts[1] if len(parts) > 1 else '', 'seoul_other')
    for area, prefixes in PROVINCE_PREFIXES.items():
        if address.startswith(prefixes):
            return area
    return 'etc'


def resolve_cafe_area(area: str | None, address: str | None) -> str:
    """주소가 있으면 도·시를 우선하되 서울 세부 분류와 천안 코드를 보존합니다."""
    area = (area or '').strip().lower()
    inferred = address_to_area(address or '')
    if inferred in SEOUL_AREAS and area == 'daehakro' and '종로구' in (address or ''):
        return area
    if inferred == 'chungnam' and area == 'cheonan' and '천안시' in (address or ''):
        return area
    if inferred != 'etc':
        return inferred
    return area if area in SUPPORTED_AREAS else 'etc'


def area_matches(requested: str, cafe_area: str) -> bool:
    if requested == 'all':
        return True
    if requested == 'seoul':
        return cafe_area in SEOUL_AREAS
    if requested == 'chungnam':
        return cafe_area in {'chungnam', 'cheonan'}
    return requested == cafe_area
