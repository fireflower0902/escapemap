"""
카카오 알림톡 발송 모듈.

카카오 비즈메시지 API를 사용합니다.
한국 사용자에게 이메일보다 오픈율이 높습니다.

사전 준비:
  1. 카카오 비즈니스 채널 등록
  2. 알림톡 채널 승인
  3. 메시지 템플릿 등록 (카카오 측 심사 필요, 약 1~2주 소요)

⚠️  MVP에서는 이메일 알림만 먼저 구현하고,
    카카오 알림톡은 채널 심사 통과 후 추가합니다.
"""
import logging

import requests

from app.config import settings

logger = logging.getLogger(__name__)

KAKAO_API_URL = "https://kapi.kakao.com/v1/api/talk/friends/message/send"


def send_vacancy_kakao(kakao_id: str, theme_name: str, booking_url: str) -> bool:
    """
    카카오 알림톡으로 빈자리 알림을 발송합니다.

    Args:
        kakao_id: 수신자의 카카오 고유 ID
        theme_name: 테마 이름
        booking_url: 예약 페이지 딥링크

    Returns:
        True: 발송 성공, False: 발송 실패
    """
    # TODO: 카카오 비즈메시지 API 연동 구현
    # 현재는 로그만 출력하는 스텁(stub) 구현
    logger.info(f"[STUB] 카카오 알림 발송: {kakao_id} / {theme_name}")
    logger.warning("카카오 알림톡은 아직 구현되지 않았습니다. 채널 심사 후 구현 예정.")
    return False
