"""
Firestore 클라이언트 초기화 및 공통 helper 함수들.

사용법 (API 엔드포인트):
  from app.firestore_db import get_db

사용법 (크롤 스크립트):
  from app.firestore_db import init_firestore, get_db, get_or_create_theme, upsert_schedule
  from app.config import settings
  init_firestore(settings.firebase_credentials_path)
  db = get_db()
"""
import os
import re

import firebase_admin
from firebase_admin import credentials, firestore as _fs

_db = None

# SKIP_META_WRITES=true 이면 cafe/theme upsert를 건너뜀 (schedule write만 수행)
_SKIP_META = os.getenv("SKIP_META_WRITES", "").lower() in ("1", "true", "yes")

# ── 지역 코드 ↔ 주소 prefix 매핑 ─────────────────────────────────────────────
# cafes.py 의 AREA_ADDRESS_MAP 과 동일하게 유지할 것
AREA_ADDRESS_MAP: dict[str, list[str]] = {
    "gangnam":    ["서울 강남구", "서울 서초구"],
    "hongdae":    ["서울 마포구"],
    "sinchon":    ["서울 서대문구"],
    "jamsil":     ["서울 송파구", "서울 강동구"],
    "itaewon":    ["서울 용산구"],
    "myeongdong": ["서울 중구", "서울 종로구"],
    "daehakro":   ["서울 종로구"],
    "sinlim":     ["서울 관악구"],
    "busan":      ["부산"],
    "daegu":      ["대구"],
    "gwangju":    ["광주"],
    "daejeon":    ["대전"],
    "incheon":    ["인천"],
    "ulsan":      ["울산"],
    "jeju":       ["제주"],
    "gyeonggi":   ["경기"],
    "gangwon":    ["강원"],
}


def address_to_area(address: str) -> str:
    """주소 문자열에서 area 코드를 결정합니다. 매칭 없으면 'etc' 반환."""
    if not address:
        return "etc"
    for area, prefixes in AREA_ADDRESS_MAP.items():
        for prefix in prefixes:
            if address.startswith(prefix):
                return area
    return "etc"


def _theme_doc_id(cafe_id: str, theme_name: str) -> str:
    """
    테마 Firestore 문서 ID를 결정적으로 생성합니다.
    같은 (cafe_id, theme_name) 조합은 항상 같은 ID를 반환합니다.
    """
    slug = re.sub(r"[^\w가-힣]", "_", theme_name)[:60]
    return f"{cafe_id}__{slug}"


# ── 초기화 ────────────────────────────────────────────────────────────────────


def init_firestore(credentials_path: str) -> None:
    """
    Firebase Admin SDK를 초기화하고 Firestore 클라이언트를 설정합니다.
    이미 초기화된 경우 재초기화 없이 클라이언트만 가져옵니다.
    """
    global _db
    if not firebase_admin._apps:
        cred = credentials.Certificate(credentials_path)
        firebase_admin.initialize_app(cred)
    _db = _fs.client()


def get_db():
    """Firestore 클라이언트를 반환합니다. init_firestore() 가 먼저 호출되어야 합니다."""
    if _db is None:
        raise RuntimeError(
            "Firestore가 초기화되지 않았습니다. "
            "init_firestore(settings.firebase_credentials_path)를 먼저 호출하세요."
        )
    return _db


# ── 카페 ──────────────────────────────────────────────────────────────────────


def upsert_cafe(db, cafe_id: str, data: dict) -> None:
    """
    카페 문서를 Firestore에 upsert합니다.
    SKIP_META_WRITES=true 환경변수가 설정된 경우 건너뜁니다.
    data 예시:
      {name, branch_name, address, area, phone, website_url,
       engine, crawled, lat, lng, is_active}
    """
    if _SKIP_META:
        return
    db.collection("cafes").document(cafe_id).set(data, merge=True)


# ── 테마 ──────────────────────────────────────────────────────────────────────


def get_or_create_theme(db, cafe_id: str, theme_name: str, data: dict) -> str:
    """
    테마를 Firestore에 upsert하고 문서 ID(str)를 반환합니다.
    반환된 ID는 이후 upsert_schedule() 의 theme_doc_id 인수로 사용합니다.
    SKIP_META_WRITES=true 환경변수가 설정된 경우 Firestore write를 건너뜁니다.

    data 예시:
      {difficulty, duration_min, poster_url, is_active, description}
    """
    doc_id = _theme_doc_id(cafe_id, theme_name)
    if not _SKIP_META:
        db.collection("themes").document(doc_id).set(
            {"cafe_id": cafe_id, "name": theme_name, **data},
            merge=True,
        )
    return doc_id


# ── 스케줄 ────────────────────────────────────────────────────────────────────


def upsert_cafe_date_schedules(
    db,
    date_str: str,    # "YYYY-MM-DD"
    cafe_id: str,
    themes: dict,     # {theme_doc_id: {"slots": [{"time":"HH:MM","status":...,"booking_url":...}]}}
    crawled_at,       # datetime
) -> None:
    """
    특정 날짜의 카페 전체 스케줄을 Firestore에 1번 write로 저장합니다.

    Firestore 경로:
      schedules/{YYYY-MM-DD}  (단일 문서, cafes.{cafe_id} 필드만 교체)

    merge=True 덕분에 같은 날짜의 다른 카페 데이터는 유지됩니다.

    themes 예시:
      {
        "1405262610__살랑살랑연구소": {
          "slots": [
            {"time": "14:00", "status": "available", "booking_url": "https://..."},
            {"time": "16:00", "status": "full",      "booking_url": None},
          ]
        }
      }
    """
    db.collection("schedules").document(date_str).set(
        {"cafes": {cafe_id: {"themes": themes, "crawled_at": str(crawled_at)}}},
        merge=True,
    )
