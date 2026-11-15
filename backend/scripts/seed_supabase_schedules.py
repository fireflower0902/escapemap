"""이미 지점별 검증을 통과한 곳의 첫 시간표를 제한된 동시성으로 수집한다."""
import argparse,collections,concurrent.futures,json,pathlib,subprocess,sys,threading
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.crawler_catalog import catalog_entry

def candidates():
 catalog={p.stem:catalog_entry(p) for p in (ROOT/'scripts').glob('sync_*_db.py')};latest={}
 for path in (ROOT/'reports/crawlers').rglob('sync_*.json'):
  try:r=json.loads(path.read_text())
  except (ValueError,OSError):continue
  if not isinstance(r,dict) or r.get('script') not in catalog or not r.get('checked_at'):continue
  ids=r.get('requested_cafe_ids') or list((r.get('per_cafe') or {}).keys())
  for cid in ids:
   if cid not in catalog[r['script']]['cafe_ids']:continue
   if cid not in latest or r['checked_at']>latest[cid]['checked_at']:latest[cid]=r
 return [(cid,r['script']) for cid,r in latest.items() if r.get('status')=='smoke_pass']

def main():
 p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');p.add_argument('--days',type=int,default=2);a=p.parse_args();tasks=candidates();print('대상',len(tasks),'지점 / 오늘부터',a.days,'일 후까지',flush=True)
 if not a.apply:return
 locks=collections.defaultdict(lambda:threading.Semaphore(2));out=ROOT/'reports/supabase/initial-schedules.json';results=[]
 def run(task):
  cid,script=task
  with locks[script]:
   result=subprocess.run([sys.executable,str(ROOT/'scripts/run_supabase_crawler.py'),script,'--cafe-id',cid,'--days',str(a.days),'--timeout','90'],cwd=ROOT,capture_output=True,text=True)
  return {'cafe_id':cid,'script':script,'status':'published' if result.returncode==0 else 'review'}
 with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
  futures=[pool.submit(run,t) for t in tasks]
  for i,future in enumerate(concurrent.futures.as_completed(futures),1):
   r=future.result();results.append(r);out.write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n');print(i,len(tasks),r['cafe_id'],r['status'],flush=True)
 print('완료',dict(collections.Counter(r['status'] for r in results)),flush=True)
if __name__=='__main__':main()
