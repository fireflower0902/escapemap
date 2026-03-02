"""
이메일 알림 발송 모듈.

Resend(resend.com)를 사용합니다.
간단한 API로 이메일을 발송할 수 있는 서비스입니다.
무료 플랜으로 월 3,000건까지 발송 가능합니다.
"""
import logging

import resend

from app.config import settings

logger = logging.getLogger(__name__)

resend.api_key = settings.resend_api_key

# 발신자 이메일 (Resend에서 도메인 인증 후 변경)
FROM_EMAIL = "알림 <noreply@escapemap.kr>"


def send_vacancy_email(email: str, theme_name: str, booking_url: str) -> bool:
    """
    빈자리 알림 이메일을 발송합니다.

    Args:
        email: 수신자 이메일 주소
        theme_name: 테마 이름 (예: "셜록홈즈의 비밀")
        booking_url: 예약 페이지 딥링크

    Returns:
        True: 발송 성공, False: 발송 실패
    """
    try:
        resend.Emails.send({
            "from": FROM_EMAIL,
            "to": [email],
            "subject": f"[이스케이프맵] '{theme_name}' 빈자리가 났습니다!",
            "html": _build_email_html(theme_name=theme_name, booking_url=booking_url),
        })
        logger.info(f"이메일 발송 성공: {email} / {theme_name}")
        return True
    except Exception as e:
        logger.error(f"이메일 발송 실패: {email} / {e}")
        return False


def _build_email_html(theme_name: str, booking_url: str) -> str:
    """이메일 HTML 본문을 생성합니다."""
    # TODO: 실제 디자인된 HTML 이메일 템플릿으로 교체
    return f"""
    <html>
      <body style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2>🎉 빈자리가 났습니다!</h2>
        <p>신청하신 <strong>{theme_name}</strong> 테마에 예약 가능한 자리가 생겼습니다.</p>
        <p>빈자리는 금방 채워질 수 있으니 서둘러 예약하세요!</p>
        <a href="{booking_url}"
           style="display: inline-block; background: #f59e0b; color: white;
                  padding: 12px 24px; border-radius: 8px; text-decoration: none;
                  font-weight: bold; margin-top: 16px;">
          지금 바로 예약하기 →
        </a>
        <p style="color: #888; font-size: 12px; margin-top: 32px;">
          이스케이프맵 | 알림 설정은 마이페이지에서 변경할 수 있습니다.
        </p>
      </body>
    </html>
    """
