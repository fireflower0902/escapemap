"""지점별 독립 검증 후 통과한 결과만 Supabase에 게시. 실패는 상태로 기록."""
import argparse,asyncio,datetime,importlib,json,pathlib,subprocess,sys
from unittest.mock import patch
from zoneinfo import ZoneInfo
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts import check_crawlers
from scripts.crawler_catalog import catalog_entry
from app.supabase_storage import connect,import_metadata,save_cafe_date,record_failure

async def publish(check,store,cid,days):
 conn=await connect();when=datetime.datetime.fromisoformat(check['checked_at']);results=[]
 try:
  async with conn.transaction():
   run=await conn.fetchval('INSERT INTO escape.crawl_runs(script,started_at,finished_at,status,metadata) VALUES($1,$2,now(),$3,$4::jsonb) RETURNING id',check['script'],when,check['status'],json.dumps({'requested_cafe_ids':[cid],'issues':check.get('issues',[])}))
   if check['status']=='smoke_pass':
    # 정정한 기존 지점 이름/주소 보존. 수집된 테마 필드만 병합한다.
    exists=await conn.fetchval('SELECT EXISTS(SELECT 1 FROM escape.cafes WHERE id=$1)',cid)
    cafes=[] if exists else [dict(store.data['cafes'][cid],id=cid)]
    themes=[dict(store.data['themes'][tid],id=tid) for col,tid in set(store.writes) if col=='themes']
    await import_metadata(conn,cafes,themes)
    for day,data in store.data.get('schedules',{}).items():
     service_day=datetime.date.fromisoformat(day)
     if not when.date() <= service_day <= when.date()+datetime.timedelta(days=days):continue
     if cid not in data.get('cafes',{}):continue
     schedule=data['cafes'][cid]
     results.append(await save_cafe_date(conn,cid,day,schedule['themes'],when))
   else:
    for offset in range(days+1):await record_failure(conn,cid,when.date()+datetime.timedelta(days=offset),when,check['status'])
   counts=check.get('per_cafe',{}).get(cid,{})
   await conn.execute('INSERT INTO escape.crawl_results(run_id,cafe_id,themes_count,slots_count) VALUES($1,$2,$3,$4)',run,cid,counts.get('themes',0),counts.get('slots',0))
  return results
 finally:await conn.close(timeout=5)

def worker(args):
 store=check_crawlers.MemoryStore()
 with patch.object(check_crawlers,'MemoryStore',return_value=store):check,log=check_crawlers.run_one(args.script,False,args.days,[args.cafe_id])
 try:
  asyncio.run(publish(check,store,args.cafe_id,args.days))
 except Exception as error:
  check['status']='error';check['error']='storage: '+type(error).__name__+' '+str(getattr(error,'constraint_name',''))
  try:asyncio.run(publish(check,None,args.cafe_id,args.days))
  except Exception:check.setdefault('issues',[]).append('수집 실패 상태의 DB 기록도 실패했습니다.')
 check['storage']='supabase';check['published']=check['status']=='smoke_pass'
 dest=ROOT/'reports/crawlers/supabase';dest.mkdir(parents=True,exist_ok=True)
 (dest/(args.script+'-'+args.cafe_id+'.json')).write_text(json.dumps(check,ensure_ascii=False,indent=2)+'\n')
 print(args.cafe_id,check['status'],check.get('themes_fetched',0),'themes',check.get('slots',0),'slots',flush=True)
 return 0 if check['status']=='smoke_pass' else 1

def record_timeout(script,cid,days):
 check={'script':script,'checked_at':datetime.datetime.now(ZoneInfo('Asia/Seoul')).isoformat(),'status':'timeout','published':False,'storage':'supabase'}
 try:
  asyncio.run(publish(check,None,cid,days))
 except Exception as error:
  check['status']='error';check['error']='storage: '+type(error).__name__
 dest=ROOT/'reports/crawlers/supabase';dest.mkdir(parents=True,exist_ok=True)
 (dest/(script+'-'+cid+'.json')).write_text(json.dumps(check,ensure_ascii=False,indent=2)+'\n')
 return check

def main():
 p=argparse.ArgumentParser();p.add_argument('script');p.add_argument('--cafe-id');p.add_argument('--days',type=int,default=14);p.add_argument('--timeout',type=int,default=600);p.add_argument('--worker',action='store_true');p.add_argument('--start',type=int,default=0);p.add_argument('--end',type=int);args=p.parse_args()
 args.script=pathlib.Path(args.script).stem
 if args.days<0 or args.days>31 or args.timeout<=0:p.error('날짜 범위/제한 시간 오류')
 path=ROOT/'scripts'/(args.script+'.py')
 if path.parent!=ROOT/'scripts' or not path.is_file() or not args.script.startswith('sync_'):p.error('등록된 수집기 파일만 실행 가능')
 if args.worker:return worker(args)
 ids=catalog_entry(path)['cafe_ids']
 if args.cafe_id:
  if args.cafe_id not in ids:p.error('수집기에 등록되지 않은 카페')
  ids=[args.cafe_id]
 ids=ids[args.start:args.end]
 failed=0
 for cid in ids:
  cmd=[sys.executable,str(pathlib.Path(__file__).resolve()),args.script,'--worker','--cafe-id',cid,'--days',str(args.days)]
  try:
   result=subprocess.run(cmd,cwd=ROOT,timeout=args.timeout);failed+=result.returncode!=0
  except subprocess.TimeoutExpired:
   check=record_timeout(args.script,cid,args.days);failed+=1;print(cid,check['status'],flush=True)
 print('완료:',len(ids),'지점 / 확인 필요',failed,flush=True)
 return bool(failed)
if __name__=='__main__':
 try:raise SystemExit(main())
 except Exception as error:print('실행 중단:',type(error).__name__,getattr(error,'constraint_name',''),'(비밀값 출력 없음)',flush=True);raise SystemExit(1)
