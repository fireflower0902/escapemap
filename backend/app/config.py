"""
앱 전체 설정값 관리.

.env 파일에서 값을 자동으로 읽어옵니다.
새로운 설정값이 필요하면 이 파일에 추가하고,
.env.example 파일에도 동일하게 추가해두세요.
"""
import os
from typing import Literal
import certifi
from pydantic_settings import BaseSettings

# macOS Python의 기본 CA 파일 누락을 보완하며 TLS 검증은 유지합니다.
# 읽기 전용 검증기와 실제 크롤러가 동일한 CA 설정을 사용합니다.
os.environ.setdefault("SSL_CERT_FILE", certifi.where())


class Settings(BaseSettings):
    # ── 데이터베이스 (SQLite — User/Alert 전용) ──────────────
    database_url: str = "sqlite+aiosqlite:///./escape_aggregator.db"
    crawl_storage: Literal["firestore", "supabase"] = "firestore"
    crawl_freshness_seconds: int = 5400  # 1시간 수집 주기에 맞춘 최대 신선도
    supabase_database_url: str = ""  # 크롤링 PostgreSQL 이전용; 기존 SQLite 설정과 분리

    # ── Firebase / Firestore ──────────────────────────────────
    firebase_credentials_path: str = "./firebase_credentials.json"

    # ── Redis (캐싱 + 태스크 큐) ──────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── 카카오맵 API (카페 목록 수집용) ──────────────────────
    kakao_rest_api_key: str = ""

    # ── 이메일 알림 (Resend) ──────────────────────────────────
    resend_api_key: str = ""

    # ── 카카오 알림톡 ─────────────────────────────────────────
    kakao_channel_public_key: str = ""

    # ── 에러 모니터링 (Sentry) ────────────────────────────────
    sentry_dsn: str = ""

    # ── 앱 동작 설정 ──────────────────────────────────────────
    environment: str = "development"
    cache_ttl_seconds: int = 300  # Redis 캐시 유지 시간 (기본 5분)
    skip_meta_writes: bool = False  # True 시 cafe/theme Firestore 쓰기 건너뜀
    crawl_seoul_only: bool = False  # 기본은 전국. 필요한 경우에만 서울 저장 제한.

    class Config:
        env_file = ".env"          # .env 파일에서 자동으로 값을 읽음
        env_file_encoding = "utf-8"
        case_sensitive = False     # 대소문자 구분 없이 환경변수 매칭


# 앱 전체에서 이 객체 하나를 import해서 사용합니다
# 예: from app.config import settings
settings = Settings()
