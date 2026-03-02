"""
크롤링 Celery 태스크.

이 파일의 함수들은 Celery가 자동으로 실행합니다.
개발자가 직접 호출하지 않아도 됩니다.

실행 방법:
  터미널 1: celery -A app.tasks.crawl worker --loglevel=info
  터미널 2: celery -A app.tasks.crawl beat --loglevel=info
  (beat = 알람 시계 역할. worker = 실제 일하는 직원 역할)
"""
import logging
from datetime import date, timedelta

from celery import Celery

from app.config import settings

logger = logging.getLogger(__name__)

# Celery 앱 생성
# broker: 할 일 목록을 저장하는 곳 (Redis)
# backend: 작업 결과를 저장하는 곳 (Redis)
celery_app = Celery(
    "escape_aggregator",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

# ── 자동 실행 스케줄 설정 ──────────────────────────────────────
# Celery Beat(알람 시계)가 이 스케줄에 따라 자동으로 태스크를 실행합니다.
celery_app.conf.beat_schedule = {
    # 15분마다 모든 카페 크롤링
    "crawl-all-cafes-every-15-min": {
        "task": "app.tasks.crawl.crawl_all_cafes",
        "schedule": 900.0,  # 900초 = 15분
    },
    # 1주일마다 카페 기본 정보(테마 목록 등) 갱신
    "update-static-data-weekly": {
        "task": "app.tasks.crawl.update_static_data",
        "schedule": 604800.0,  # 604800초 = 7일
    },
}

celery_app.conf.timezone = "Asia/Seoul"


@celery_app.task(
    bind=True,
    max_retries=3,              # 실패 시 최대 3번 재시도
    default_retry_delay=60,     # 재시도 전 60초 대기
)
def crawl_all_cafes(self):
    """
    DB에 등록된 모든 활성 카페의 예약 현황을 수집합니다.
    15분마다 자동 실행됩니다.
    """
    logger.info("=== 전체 카페 크롤링 시작 ===")

    # TODO: DB에서 활성 카페 목록 조회
    # TODO: 각 카페의 엔진 타입에 맞는 크롤러 실행
    # TODO: 수집된 데이터를 Schedule 테이블에 저장
    # TODO: 빈자리가 새로 생긴 경우 notify_users 태스크 발행

    logger.info("=== 전체 카페 크롤링 완료 ===")


@celery_app.task
def crawl_single_cafe(cafe_id: str):
    """
    특정 카페 한 곳만 즉시 크롤링합니다.
    수동으로 특정 카페를 갱신하고 싶을 때 사용합니다.
    """
    logger.info(f"카페 단독 크롤링: {cafe_id}")
    # TODO: 구현


@celery_app.task
def update_static_data():
    """
    카페 기본 정보(테마 목록, 포스터 등)를 갱신합니다.
    자주 바뀌지 않으므로 1주일마다 실행합니다.
    """
    logger.info("정적 데이터 갱신 시작")
    # TODO: 카카오맵 API로 새로운 카페 추가 확인
    # TODO: 각 카페의 테마 목록 갱신
