"""
키이스케이프 예약 시스템 크롤러.

API:
  [테마 목록]  POST /controller/run_proc.php  t=get_theme_info_list&zizum_num={N}
  [스케줄]    POST /controller/run_proc.php  t=get_theme_time&date={YYYY-MM-DD}&zizumNum={N}&themeNum={M}&endDay=0

enable == "Y" → 예약 가능 / "N" → 마감
"""
import asyncio
import re
import logging
from datetime import date
from datetime import time as dtime

import aiohttp

logger = logging.getLogger(__name__)

BASE_URL = "https://keyescape.com/controller/run_proc.php"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://keyescape.com/reservation1.php",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
}
REQUEST_DELAY_SECONDS = 0.5

# zizum_num → cafe.id (카카오 place_id)
BRANCH_MAP: dict[int, str] = {
    3:  "1405262610",  # 강남점
    14: "400448256",   # 강남 더오름
    16: "916422770",   # 우주라이크
    18: "459642234",   # 메모리컴퍼니
    19: "99889048",    # LOG_IN1
    20: "320987184",   # LOG_IN2
    22: "298789057",   # STATION
    23: "1872221698",  # 후즈데어
    10: "200411443",   # 홍대점
    9:  "1637143499",  # 부산점
    7:  "48992610",    # 전주점
}


def parse_duration(memo: str) -> int | None:
    m = re.search(r"시간\s*:\s*(\d+)\s*분", memo or "")
    return int(m.group(1)) if m else None


def parse_difficulty(memo: str) -> int | None:
    m = re.search(r"난이도\s*:\s*(\d+)", memo or "")
    if m:
        return max(1, min(5, int(m.group(1))))
    return None


async def fetch_themes(zizum_num: int) -> list[dict]:
    """지점 테마 목록 반환. [{"theme_num", "name", "duration_min", "difficulty", "description"}]"""
    await asyncio.sleep(REQUEST_DELAY_SECONDS)
    async with aiohttp.ClientSession() as session:
        async with session.post(
            BASE_URL,
            data=f"t=get_theme_info_list&zizum_num={zizum_num}",
            headers=HEADERS,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)

    results = []
    for t in (data.get("data") or []):
        memo = t.get("memo", "")
        results.append({
            "theme_num": t["theme_num"],
            "name": t["info_name"],
            "duration_min": parse_duration(memo),
            "difficulty": parse_difficulty(memo),
            "description": memo.strip() or None,
            "poster_url": None,
        })
    return results


async def fetch_slots(
    zizum_num: int,
    theme_num: int,
    target_date: date,
) -> list[dict]:
    """특정 날짜의 슬롯 반환. [{"time": dtime, "status": str, "booking_url": str|None}]"""
    await asyncio.sleep(REQUEST_DELAY_SECONDS)
    date_str = target_date.strftime("%Y-%m-%d")
    async with aiohttp.ClientSession() as session:
        async with session.post(
            BASE_URL,
            data=(
                f"t=get_theme_time"
                f"&date={date_str}"
                f"&zizumNum={zizum_num}"
                f"&themeNum={theme_num}"
                f"&endDay=0"
            ),
            headers=HEADERS,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)

    booking_base = f"https://keyescape.com/reservation1.php?zizum_num={zizum_num}"
    results = []
    for s in (data.get("data") or []):
        hh = int(s["hh"])
        mm = int(s["mm"])
        enable = s.get("enable", "N")
        status = "available" if enable == "Y" else "full"
        results.append({
            "time": dtime(hh, mm),
            "status": status,
            "booking_url": booking_base if status == "available" else None,
        })
    return results
