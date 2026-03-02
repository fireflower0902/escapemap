"""
FastAPI 앱의 진입점(Entry Point).

서버를 실행하면 가장 먼저 이 파일이 실행됩니다.
모든 API 라우터를 여기에 등록합니다.

실행 방법:
  uvicorn app.main:app --reload
  (--reload: 코드 수정 시 자동으로 서버 재시작)
"""
import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import create_all_tables
from app.api.v1 import cafes, schedules, alerts, auth

# ── Sentry 에러 추적 초기화 ───────────────────────────────────
if settings.sentry_dsn:
    sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.environment)

# ── FastAPI 앱 생성 ────────────────────────────────────────────
app = FastAPI(
    title="방탈출 예약 통합 플랫폼 API",
    description="전국 방탈출 카페 예약 현황 조회 및 빈자리 알림 서비스",
    version="0.1.0",
    # /docs 로 접속하면 자동 생성된 API 문서를 볼 수 있습니다
)

# ── CORS 설정 ──────────────────────────────────────────────────
# 프론트엔드(Next.js)가 이 API를 호출할 수 있도록 허용합니다.
# 브라우저 보안 정책상 같은 주소가 아니면 기본적으로 차단됩니다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",   # Next.js 개발 서버
        "https://escapemap.kr",    # 실제 도메인 (배포 후 변경)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API 라우터 등록 ────────────────────────────────────────────
# prefix="/api/v1"을 붙이면 모든 엔드포인트가 /api/v1/...로 시작합니다
app.include_router(cafes.router,     prefix="/api/v1", tags=["카페"])
app.include_router(schedules.router, prefix="/api/v1", tags=["예약 현황"])
app.include_router(alerts.router,    prefix="/api/v1", tags=["알림"])
app.include_router(auth.router,      prefix="/api/v1", tags=["인증"])


# ── 서버 시작 이벤트 ──────────────────────────────────────────
@app.on_event("startup")
async def startup():
    """서버가 시작될 때 자동으로 실행됩니다."""
    # 개발 환경에서 DB 테이블 자동 생성
    if settings.environment == "development":
        await create_all_tables()


# ── 기본 엔드포인트 ────────────────────────────────────────────
@app.get("/", tags=["상태 확인"])
async def root():
    """서버가 살아있는지 확인하는 기본 엔드포인트."""
    return {"message": "방탈출 예약 통합 플랫폼 API 서버 동작 중", "version": "0.1.0"}


@app.get("/health", tags=["상태 확인"])
async def health_check():
    """모니터링 도구(Uptime Kuma 등)가 서버 상태를 확인하는 엔드포인트."""
    return {"status": "ok", "environment": settings.environment}
