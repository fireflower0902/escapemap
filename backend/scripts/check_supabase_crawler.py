"""검증 통과한 대표 크롤러 결과를 Supabase에 저장하고 일치 여부를 대조한다."""
import asyncio,datetime,json,pathlib,sys
from unittest.mock import patch
from zoneinfo import ZoneInfo
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts import check_crawlers
from app.supabase_storage import connect,import_metadata,save_cafe_date
from scripts.migrate_to_supabase import prepare

async def save(store,check):
    cafes,themes,_=prepare();byid={c['id']:c for c in cafes}
    # 기존의 검증된 카페 기본정보를 유지하고 실제로 수집된 테마만 갱신.
    changed_themes=[dict(store.data['themes'][tid],id=tid) for col,tid in set(store.writes) if col=='themes']
    conn=await connect();results=[]
    try:
        await import_metadata(conn,[byid[cid] for cid in {t['cafe_id'] for t in changed_themes}],changed_themes)
        for day,schedule in store.data.get('schedules',{}).items():
            for cid,data in schedule['cafes'].items():
                when=datetime.datetime.fromisoformat(data['crawled_at'])
                if not when.tzinfo:when=when.replace(tzinfo=ZoneInfo('Asia/Seoul'))
                first=await save_cafe_date(conn,cid,day,data['themes'],when)
                second=await save_cafe_date(conn,cid,day,data['themes'],when)
                if second['changed']:raise ValueError('동일 예약 결과 중복 쓰기 검사 실패')
                actual=await conn.fetchval('SELECT count(*) FROM escape.reservation_slots WHERE cafe_id=$1 AND service_date=$2',cid,datetime.date.fromisoformat(day))
                if actual!=first['slots']:raise ValueError('저장 시간대 수 불일치')
                results.append({'cafe_id':cid,'date':day,**first,'duplicate_write_skipped':True})
        run=await conn.fetchval('''INSERT INTO escape.crawl_runs(script,started_at,finished_at,status,metadata) VALUES($1,$2,now(),$3,$4::jsonb) RETURNING id''',check['script'],datetime.datetime.fromisoformat(check['checked_at']),check['status'],json.dumps({'migration_validation':True,'source':'live public crawler'}))
        for cid,c in check['per_cafe'].items():
            await conn.execute('INSERT INTO escape.crawl_results(run_id,cafe_id,themes_count,slots_count) VALUES($1,$2,$3,$4)',run,cid,c['themes'],c['slots'])
        out=ROOT/'reports/supabase';out.mkdir(exist_ok=True);(out/'live-crawler-validation.json').write_text(json.dumps({'check':check,'stored':results},ensure_ascii=False,indent=2)+'\n')
        print('대표 크롤러 저장·조회·중복 쓰기 방지 검사 통과:',sum(r['slots'] for r in results),'시간대')
    finally:await conn.close(timeout=5)

if __name__=='__main__':
    store=check_crawlers.MemoryStore()
    with patch.object(check_crawlers,'MemoryStore',return_value=store):
        check,log=check_crawlers.run_one('sync_public_extra_db',False,2,['official_plus'])
    if check['status']!='smoke_pass':print('대표 크롤러 재검토 필요:',check['status']);raise SystemExit(1)
    try:asyncio.run(save(store,check))
    except Exception as error:print('저장 검증 중단:',type(error).__name__);raise SystemExit(1)
