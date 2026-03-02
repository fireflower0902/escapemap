"""
도어이스케이프 예약 시스템 크롤러.

플랫폼: macro.playthe.world (공용 SaaS 예약 시스템)
인증: JWT (HS256) — Brand Keycode를 secret으로 사용

API:
  GET /v2/shops/{shop_keycode}
  → { data: { shop, themes: [{ id, title, image_url, summary, slots: [{ id, day_string, integer_to_time, can_book }] }] } }

can_book == True → 예약 가능
"""
import asyncio
import base64
import hashlib
import hmac as _hmac
import json
import logging
import re
import ssl
import string
import time
from datetime import date
from datetime import time as dtime
from random import choices

import aiohttp

logger = logging.getLogger(__name__)

BRAND_KEYCODE = "MmtAku42Sc4f1V2N"
BASE_URL = "https://macro.playthe.world"
SITE_REFERER = "https://doorescape.co.kr"
REQUEST_DELAY_SECONDS = 0.5

# shop keycode → cafe.id (카카오 place_id)
SHOP_MAP: dict[str, str] = {
    "aAo1RDEnfyPkbeix": "691418241",   # 강남 가든점
    "NeZqzMtPCBsSvbAq": "765336936",   # 신논현 레드점
    "yGozPSZSJXwrzbin": "2058736611",  # 신논현 블루점
    "o83TaXbnod8DtEX5": "153136502",   # 홍대점
    "h1i4d4YyEfBctnpQ": "190103388",   # 이수역점
    "DGpkkgMQYaNLYXTZ": "27609271",    # 안산점
    "fGDxtefVDEyWczai": "1836271694",  # 대전유성 NC백화점
    "FgBZDHfrR8p5UDmF": "1460830485",  # 부평점
}


# ── JWT ───────────────────────────────────────────────────────────────────────

def _b64url(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode()
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _create_jwt(secure: str) -> str:
    header = json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":"))
    payload = json.dumps(
        {"X-Auth-Token": secure, "expired_at": int(time.time()) + 3600},
        separators=(",", ":"),
    )
    msg = f"{_b64url(header)}.{_b64url(payload)}"
    sig = _hmac.new(BRAND_KEYCODE.encode(), msg.encode(), hashlib.sha256).digest()
    return f"{msg}.{_b64url(sig)}"


def _auth_headers() -> dict[str, str]:
    secure = "".join(choices(string.ascii_letters + string.digits, k=16))
    return {
        "Bearer-Token": BRAND_KEYCODE,
        "Name": "door-escape",
        "Site-Referer": SITE_REFERER,
        "X-Request-Origin": SITE_REFERER,
        "X-Request-Option": _create_jwt(secure),
        "X-Secure-Random": secure,
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    }


# ── 파싱 헬퍼 ─────────────────────────────────────────────────────────────────

def parse_duration(summary: str) -> int | None:
    m = re.search(r"\[\s*(\d+)\s*분\s*\]", summary or "")
    return int(m.group(1)) if m else None


def parse_difficulty(summary: str) -> int | None:
    m = re.search(r"난이도\s*[:\s]+(\d+)", summary or "")
    if m:
        return max(1, min(5, int(m.group(1))))
    return None


def _clean(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"<[^>]+>", "", text).strip()


# ── API 호출 ──────────────────────────────────────────────────────────────────

# SSL 검증 우회 (macro.playthe.world 인증서 체인 문제)
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

_CONNECTOR_KW = {"ssl": _SSL_CTX}


async def _get(path: str) -> dict:
    url = BASE_URL + path
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(**_CONNECTOR_KW)) as session:
        async with session.get(
            url,
            headers=_auth_headers(),
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            resp.raise_for_status()
            return await resp.json(content_type=None)


async def fetch_shop_detail(shop_keycode: str) -> dict:
    """지점 상세 반환 (테마 + 슬롯 포함)."""
    await asyncio.sleep(REQUEST_DELAY_SECONDS)
    data = await _get(f"/v2/shops/{shop_keycode}")
    return data.get("data", {})


async def fetch_themes(shop_keycode: str) -> list[dict]:
    """지점 테마 목록 반환. [{"api_id", "name", "duration_min", "difficulty", "description", "poster_url"}]"""
    detail = await fetch_shop_detail(shop_keycode)
    results = []
    for t in detail.get("themes", []):
        summary = _clean(t.get("summary"))
        results.append({
            "api_id": t["id"],
            "name": t["title"],
            "duration_min": parse_duration(summary),
            "difficulty": parse_difficulty(summary),
            "description": summary or None,
            "poster_url": t.get("image_url") or None,
        })
    return results


async def fetch_slots(
    shop_keycode: str,
    api_theme_id: int,
    target_date: date,
) -> list[dict]:
    """특정 날짜의 슬롯 반환. [{"time": dtime, "status": str, "booking_url": str|None}]"""
    detail = await fetch_shop_detail(shop_keycode)
    target_str = target_date.strftime("%Y-%m-%d")
    booking_base = f"{SITE_REFERER}/reservation.html?keycode={shop_keycode}"

    for t in detail.get("themes", []):
        if t["id"] != api_theme_id:
            continue
        results = []
        for s in t.get("slots", []):
            if s.get("day_string") != target_str:
                continue
            time_str = s.get("integer_to_time", "")
            if not time_str or ":" not in time_str:
                continue
            hh, mm = map(int, time_str.split(":"))
            can_book = s.get("can_book", False)
            status = "available" if can_book else "full"
            results.append({
                "time": dtime(hh, mm),
                "status": status,
                "booking_url": booking_base if status == "available" else None,
            })
        return results
    return []
