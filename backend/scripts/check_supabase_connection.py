"""비밀번호·연결 문자열을 출력하지 않고 Supabase 연결을 확인한다 (읽기 전용)."""
import asyncio,pathlib,sys
from urllib.parse import urlsplit
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.config import settings

def validate_uri(uri):
    if not uri or 'YOUR-PASSWORD' in uri:
        raise ValueError('SUPABASE_DATABASE_URL에 실제 DB 비밀번호를 설정하세요.')
    try:
        parts=urlsplit(uri)
        if parts.scheme not in ('postgres','postgresql') or not parts.hostname or not parts.username or not parts.password or not parts.port or parts.fragment:
            raise ValueError()
    except ValueError:
        raise ValueError('DB 연결 URI 형식을 확인하세요. 비밀번호 특수문자는 URL 인코딩해야 합니다.') from None
    return uri

async def main():
    import asyncpg
    try:uri=validate_uri(settings.supabase_database_url)
    except ValueError as error:print(str(error));return 1
    connection=None
    try:
        from app.supabase_storage import tls_context
        connection=await asyncpg.connect(uri,ssl=tls_context(),timeout=15,statement_cache_size=0)
        valid=await connection.fetchval('SELECT 1')
        print('Supabase 연결 성공 · 읽기 전용 확인 완료' if valid==1 else 'DB 응답 확인 필요')
        return 0 if valid==1 else 1
    except Exception as error:
        # 드라이버 오류 메시지에 URI·비밀번호가 포함될 수 있어 유형만 표시.
        print('연결 실패:',type(error).__name__,'· 연결 정보 또는 네트워크 설정을 확인하세요.')
        return 1
    finally:
        if connection:await connection.close(timeout=5)
if __name__=='__main__':raise SystemExit(asyncio.run(main()))
