"""
크롤러 엔진 테스트.

개발 중 크롤러가 정상 동작하는지 확인하는 테스트입니다.
실행 방법: pytest tests/test_engines.py -v
"""
import pytest
from datetime import date

from app.engines.keyescape import KeyEscapeEngine
from app.engines.bitfobia import BitfobiaEngine


# 테스트용 설정값 (실제 카페 설정을 간단히 복사)
KEYESCAPE_CONFIG = {
    "name": "키이스케이프 강남점",
    "engine": "keyescape",
    "base_url": "https://keyescape.co.kr",
    "branch_id": "gangnam",
}


@pytest.mark.asyncio
async def test_keyescape_fetch_themes():
    """키이스케이프 테마 목록 수집 테스트."""
    engine = KeyEscapeEngine(config=KEYESCAPE_CONFIG)
    themes = await engine.fetch_themes(cafe_id="gangnam")

    # TODO: 실제 API 분석 후 테스트 내용 구체화
    # 지금은 리스트가 반환되는지만 확인
    assert isinstance(themes, list)


@pytest.mark.asyncio
async def test_keyescape_fetch_schedules():
    """키이스케이프 예약 현황 수집 테스트."""
    engine = KeyEscapeEngine(config=KEYESCAPE_CONFIG)
    schedules = await engine.fetch_schedules(
        theme_id="1",
        target_date=date.today(),
    )
    assert isinstance(schedules, list)
