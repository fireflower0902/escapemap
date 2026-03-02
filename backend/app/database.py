"""
데이터베이스 연결 설정.

SQLAlchemy의 비동기(async) 방식으로 구성되어 있어서,
나중에 SQLite → PostgreSQL로 전환할 때 이 파일의
database_url 설정 한 줄만 바꾸면 됩니다.
"""
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


# ── 데이터베이스 엔진 생성 ────────────────────────────────────
# echo=True: 실행되는 SQL 쿼리를 터미널에 출력 (개발 중 디버깅용)
# 배포 환경에서는 echo=False 권장
engine = create_async_engine(
    settings.database_url,
    echo=(settings.environment == "development"),
)

# ── 세션 팩토리 ───────────────────────────────────────────────
# DB 작업을 할 때마다 이 팩토리로 세션을 만들어서 사용합니다
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── 모든 모델의 기본 클래스 ───────────────────────────────────
# models/ 폴더의 모든 테이블 클래스가 이 Base를 상속받습니다
class Base(DeclarativeBase):
    pass


# ── DB 세션 주입 함수 ─────────────────────────────────────────
# FastAPI의 Depends()와 함께 사용합니다.
# API 함수가 호출될 때 자동으로 DB 세션을 열고,
# 함수가 끝나면 자동으로 세션을 닫아줍니다.
#
# 사용 예시:
#   @router.get("/cafes")
#   async def get_cafes(db: AsyncSession = Depends(get_db)):
#       ...
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# ── 테이블 생성 함수 ──────────────────────────────────────────
# 개발 초기에 models/ 폴더의 모든 테이블을 DB에 생성합니다.
# 실제 운영에서는 Alembic 마이그레이션을 사용합니다.
async def create_all_tables():
    # 모든 모델을 명시적으로 import해야 Base.metadata에 등록됩니다
    import app.models.cafe      # noqa: F401
    import app.models.theme     # noqa: F401
    import app.models.schedule  # noqa: F401
    import app.models.user      # noqa: F401
    import app.models.alert     # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
