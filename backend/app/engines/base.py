"""
모든 크롤러 엔진의 공통 인터페이스(BaseEngine).

새로운 방탈출 카페 예약 시스템을 지원하려면
이 클래스를 상속(inherit)받아서
fetch_themes()와 fetch_schedules()를 구현하면 됩니다.

비유: 이 파일은 "직원 매뉴얼"입니다.
  매뉴얼에는 "직원은 반드시 테마 목록을 가져올 수 있어야 하고,
  예약 현황을 가져올 수 있어야 한다"고 적혀 있습니다.
  각 카페별 엔진(keyescape.py 등)이 구체적인 방법을 구현합니다.
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import date

logger = logging.getLogger(__name__)


class BaseEngine(ABC):
    """모든 예약 엔진이 반드시 구현해야 하는 공통 인터페이스."""

    def __init__(self, config: dict):
        """
        config: configs/cafes/*.yaml 파일에서 읽어온 설정값.
        예:
          {
            "name": "키이스케이프 강남점",
            "engine": "keyescape",
            "base_url": "https://keyescape.co.kr",
            "branch_id": "gangnam",
            "crawl_interval_minutes": 15
          }
        """
        self.config = config
        self.cafe_name = config.get("name", "알 수 없는 카페")
        self.base_url = config.get("base_url", "")

    @abstractmethod
    async def fetch_themes(self, cafe_id: str) -> list[dict]:
        """
        카페의 테마 목록을 가져옵니다. (정적 데이터 — 자주 바뀌지 않음)

        반환 형식:
          [
            {
              "name": "셜록홈즈의 비밀",
              "difficulty": 4,
              "min_players": 2,
              "max_players": 6,
              "duration_min": 70,
              "poster_url": "https://..."
            },
            ...
          ]
        """
        ...

    @abstractmethod
    async def fetch_schedules(self, theme_id: str, target_date: date) -> list[dict]:
        """
        특정 테마의 날짜별 예약 현황을 가져옵니다. (동적 데이터 — 15분마다 수집)

        반환 형식:
          [
            {
              "time_slot": "14:00",
              "status": "available",   # available / full / closed
              "available_slots": 2,
              "total_slots": 4,
              "booking_url": "https://..."
            },
            ...
          ]
        """
        ...

    async def health_check(self) -> bool:
        """
        이 엔진이 정상적으로 작동하는지 빠르게 확인합니다.
        모니터링 시스템(Uptime Kuma)이 주기적으로 호출합니다.
        """
        try:
            await asyncio.wait_for(
                self.fetch_themes(self.config.get("branch_id", "")),
                timeout=10.0  # 10초 안에 응답 없으면 실패로 처리
            )
            return True
        except Exception as e:
            logger.error(f"[{self.cafe_name}] 헬스체크 실패: {e}")
            return False
