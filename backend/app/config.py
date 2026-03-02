"""
앱 전체 설정값 관리.

.env 파일에서 값을 자동으로 읽어옵니다.
새로운 설정값이 필요하면 이 파일에 추가하고,
.env.example 파일에도 동일하게 추가해두세요.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── 데이터베이스 (SQLite — User/Alert 전용) ──────────────
    database_url: str = "sqlite+aiosqlite:///./escape_aggregator.db"

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

    class Config:
        env_file = ".env"          # .env 파일에서 자동으로 값을 읽음
        env_file_encoding = "utf-8"
        case_sensitive = False     # 대소문자 구분 없이 환경변수 매칭


# 앱 전체에서 이 객체 하나를 import해서 사용합니다
# 예: from app.config import settings
settings = Settings()
