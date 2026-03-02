"""
비트포비아(던전 시리즈) 예약 시스템 크롤러.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  이 파일은 현재 스켈레톤(뼈대)입니다.
   실제 API 엔드포인트를 분석한 후 구현해야 합니다.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

분석 결과 문서: docs/engines/bitfobia.md (분석 후 작성)
"""
import asyncio
import logging
from datetime import date

import aiohttp

from app.engines.base import BaseEngine

logger = logging.getLogger(__name__)

REQUEST_DELAY_SECONDS = 2


class BitfobiaEngine(BaseEngine):
    """비트포비아 자체 예약 시스템 크롤러."""

    async def fetch_themes(self, cafe_id: str) -> list[dict]:
        """비트포비아 테마 목록 수집."""
        await asyncio.sleep(REQUEST_DELAY_SECONDS)

        async with aiohttp.ClientSession() as session:
            # TODO: 실제 API 엔드포인트로 교체 필요
            url = f"{self.base_url}/api/themes"
            params = {"branch": self.config.get("branch_id")}
            headers = {"User-Agent": "Mozilla/5.0"}

            try:
                async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                    return data.get("themes", [])
            except aiohttp.ClientError as e:
                logger.error(f"[비트포비아] 테마 수집 실패: {e}")
                return []

    async def fetch_schedules(self, theme_id: str, target_date: date) -> list[dict]:
        """비트포비아 예약 현황 수집."""
        await asyncio.sleep(REQUEST_DELAY_SECONDS)

        async with aiohttp.ClientSession() as session:
            # TODO: 실제 API 엔드포인트로 교체 필요
            url = f"{self.base_url}/api/schedules"
            params = {
                "theme_id": theme_id,
                "date": target_date.strftime("%Y-%m-%d"),
            }
            headers = {"User-Agent": "Mozilla/5.0"}

            try:
                async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                    return data.get("schedules", [])
            except aiohttp.ClientError as e:
                logger.error(f"[비트포비아] 예약 현황 수집 실패: {e}")
                return []
