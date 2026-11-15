"""로컬에 확보한 기본정보를 PostgreSQL로 이전. --apply 없이는 데이터 검증만 수행."""
import argparse,asyncio,datetime,hashlib,json,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.areas import resolve_cafe_area
from app.supabase_storage import connect,migrate,import_metadata
from scripts.check_supabase_connection import validate_uri
from app.config import settings

def prepare():
    original=json.loads((ROOT/'reports/competitors/ours.json').read_text())
    directory=json.loads((ROOT/'data/cafe-directory.json').read_text())
    cafes={c['id']:c for c in original['cafes']}
    for c in directory['cafes']:cafes[c['id']]={**cafes.get(c['id'],{}),**c}
    for c in cafes.values():
        c['area']=resolve_cafe_area(c.get('area'),c.get('address'))
        if not c.get('name') or not c.get('address') or c['area']=='etc':raise ValueError('카페 기본정보 검증 실패')
    themes=original['themes'];ids=set()
    for t in themes:
        if t['id'] in ids or t['cafe_id'] not in cafes or not t.get('name'):raise ValueError('테마 ID/소속/이름 검증 실패')
        ids.add(t['id'])
    return list(cafes.values()),themes,original.get('collected_at')

async def run(apply):
    cafes,themes,source_at=prepare();print('이전 대상:',len(cafes),'카페 /',len(themes),'테마',flush=True)
    if not apply:return
    validate_uri(settings.supabase_database_url);conn=await connect()
    try:
        await migrate(conn);await import_metadata(conn,cafes,themes)
        actual_cafes={r['id'] for r in await conn.fetch('SELECT id FROM escape.cafes')}
        actual_themes={r['id'] for r in await conn.fetch('SELECT id FROM escape.themes')}
        if not {c['id'] for c in cafes}<=actual_cafes or not {t['id'] for t in themes}<=actual_themes:raise ValueError('이전 결과 ID 대조 실패')
        report={'completed_at':datetime.datetime.now().astimezone().isoformat(),'source_collected_at':source_at,'cafes':len(cafes),'themes':len(themes),'ids_verified':True,'source':'local Firestore export + corrected cafe directory','schedules_imported':False,'application_cutover':False}
        path=ROOT/'reports/supabase';path.mkdir(exist_ok=True);(path/'migration.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print('기본정보 이전 완료 · 기존 ID 대조 통과',flush=True)
    finally:await conn.close(timeout=5)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');a=p.parse_args()
    try:asyncio.run(run(a.apply))
    except Exception as error:
        print('이전 중단:',type(error).__name__,'· 연결 문자열/비밀번호는 출력하지 않습니다.');raise SystemExit(1)
