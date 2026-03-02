"""
알림 발송 Celery 태스크.

크롤러(crawl.py)가 빈자리를 감지하면
이 파일의 태스크를 발행(publish)합니다.
Celery가 큐에서 꺼내어 이메일/카카오 알림을 발송합니다.
"""
import logging

from app.tasks.crawl import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def send_vacancy_alert(self, alert_id: int):
    """
    빈자리 알림을 발송합니다.

    크롤러가 빈자리를 발견하면 이 태스크를 Celery 큐에 넣습니다:
      send_vacancy_alert.delay(alert_id=42)

    그러면 Celery worker가 큐에서 꺼내어 자동으로 이 함수를 실행합니다.
    """
    logger.info(f"알림 발송 시작: alert_id={alert_id}")

    # TODO: DB에서 alert 정보 조회
    # TODO: 채널(email/kakao)에 따라 발송 함수 선택
    # TODO: 발송 성공 시 alert.is_sent = True, sent_at 기록
    # TODO: 중복 발송 방지 (Redis 분산 락)

    logger.info(f"알림 발송 완료: alert_id={alert_id}")


@celery_app.task
def send_email_alert(alert_id: int, email: str, theme_name: str, booking_url: str):
    """이메일로 빈자리 알림을 발송합니다."""
    from app.notifications.email import send_vacancy_email
    send_vacancy_email(email=email, theme_name=theme_name, booking_url=booking_url)


@celery_app.task
def send_kakao_alert(alert_id: int, kakao_id: str, theme_name: str, booking_url: str):
    """카카오 알림톡으로 빈자리 알림을 발송합니다."""
    from app.notifications.kakao import send_vacancy_kakao
    send_vacancy_kakao(kakao_id=kakao_id, theme_name=theme_name, booking_url=booking_url)
