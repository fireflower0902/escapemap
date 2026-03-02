"""
네이버 예약 시스템 공통 크롤러.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 이 엔진의 핵심 가치:
   여러 방탈출 카페가 네이버 예약 시스템을 사용합니다.
   이 엔진 하나로 그 모든 카페를 지원할 수 있습니다.
   새 카페 추가 시 YAML 설정 파일만 작성하면 됩니다.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️  이 파일은 현재 스켈레톤(뼈대)입니다.
   네이버 예약 API 분석 후 구현해야 합니다.

분석 결과 문서: docs/engines/naver_booking.md (분석 후 작성)
"""
import asyncio
import logging
from datetime import date

import aiohttp

from app.engines.base import BaseEngine

logger = logging.getLogger(__name__)

REQUEST_DELAY_SECONDS = 2

# 네이버 예약 시스템의 기본 API 주소
# 분석 후 실제 엔드포인트로 교체 필요
NAVER_BOOKING_API_BASE = "https://booking.naver.com/booking/6/bizes"


class NaverBookingEngine(BaseEngine):
    """
    네이버 예약 시스템을 사용하는 모든 방탈출 카페에 재사용 가능한 엔진.

    YAML 설정에서 naver_biz_id를 읽어서 해당 카페의 API를 호출합니다.
    카페마다 코드를 새로 짤 필요 없이 설정 파일만 추가하면 됩니다.
    """

    def __init__(self, config: dict):
        super().__init__(config)
        # 네이버 예약에서 각 카페를 구분하는 고유 ID
        self.naver_biz_id = config.get("naver_biz_id", "")

    async def fetch_themes(self, cafe_id: str) -> list[dict]:
        """네이버 예약 API에서 테마(서비스) 목록 수집."""
        await asyncio.sleep(REQUEST_DELAY_SECONDS)

        async with aiohttp.ClientSession() as session:
            # TODO: 실제 네이버 예약 API 엔드포인트로 교체 필요
            url = f"{NAVER_BOOKING_API_BASE}/{self.naver_biz_id}/services"
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://booking.naver.com",
            }

            try:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                    return data.get("items", [])
            except aiohttp.ClientError as e:
                logger.error(f"[네이버 예약 - {self.cafe_name}] 테마 수집 실패: {e}")
                return []

    async def fetch_schedules(self, theme_id: str, target_date: date) -> list[dict]:
        """네이버 예약 API에서 예약 가능 시간대 수집."""
        await asyncio.sleep(REQUEST_DELAY_SECONDS)

        async with aiohttp.ClientSession() as session:
            # TODO: 실제 네이버 예약 API 엔드포인트로 교체 필요
            url = f"{NAVER_BOOKING_API_BASE}/{self.naver_biz_id}/services/{theme_id}/calendar/times"
            params = {"month": target_date.strftime("%Y%m")}
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://booking.naver.com",
            }

            try:
                async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                    return data.get("times", [])
            except aiohttp.ClientError as e:
                logger.error(f"[네이버 예약 - {self.cafe_name}] 예약 현황 수집 실패: {e}")
                return []
