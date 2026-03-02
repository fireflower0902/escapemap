"""
모든 데이터베이스 모델을 한 곳에서 import.

이 파일이 없으면 Alembic(DB 버전 관리 도구)이
새로운 테이블이나 컬럼 변경을 자동으로 감지하지 못합니다.
모델 파일을 새로 만들면 반드시 여기에 추가하세요.
"""
from app.models.cafe import Cafe
from app.models.theme import Theme
from app.models.schedule import Schedule
from app.models.user import User
from app.models.alert import Alert

__all__ = ["Cafe", "Theme", "Schedule", "User", "Alert"]
