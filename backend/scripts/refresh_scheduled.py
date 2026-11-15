"""검증된 전국 지점을 분할 수집하고 실패를 CI 결과와 요약에 남긴다."""
from __future__ import annotations
import argparse, collections, concurrent.futures, datetime, json, pathlib, shutil, subprocess, sys, threading
ROOT=pathlib.Path(__file__).resolve().parents[1]

def select_tasks(items,shard,shards):
 if not 0<=shard<shards:raise ValueError('Invalid shard')
 return sorted(items,key=lambda row:(row['script'],row['cafe_id']))[shard::shards]

def main():
 p=argparse.ArgumentParser();p.add_argument('--days',type=int,default=6);p.add_argument('--shard',type=int,default=0);p.add_argument('--shards',type=int,default=1);p.add_argument('--workers',type=int,default=2);p.add_argument('--timeout',type=int,default=180);a=p.parse_args()
 if not 0<=a.days<=14 or not 1<=a.workers<=6 or a.timeout<1:p.error('Invalid collection limits')
 tasks=select_tasks(json.loads((ROOT/'data/scheduled-crawlers.json').read_text()),a.shard,a.shards)
 locks=collections.defaultdict(lambda:threading.Semaphore(1));results=[]
 def run(task):
  with locks[task['script']]:
   try:
    r=subprocess.run([sys.executable,str(ROOT/'scripts/run_supabase_crawler.py'),task['script'],'--cafe-id',task['cafe_id'],'--days',str(a.days),'--timeout',str(a.timeout)],cwd=ROOT,capture_output=True,text=True,timeout=a.timeout+30)
    return {**task,'status':'published' if r.returncode==0 else 'failed','exit_code':r.returncode}
   except subprocess.TimeoutExpired:return {**task,'status':'timeout','exit_code':124}
 with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
  for future in concurrent.futures.as_completed([pool.submit(run,t) for t in tasks]):
   row=future.result();results.append(row);print(len(results),len(tasks),row['cafe_id'],row['status'],flush=True)
 out=ROOT/'reports/scheduled';out.mkdir(parents=True,exist_ok=True)
 report={'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'shard':a.shard,'days':a.days,'total':len(tasks),'published':sum(r['status']=='published' for r in results),'results':results}
 for row in results:
  if row['status']=='published':continue
  source=ROOT/'reports/crawlers/supabase'/f"{row['script']}-{row['cafe_id']}.json"
  if source.exists():shutil.copy2(source,out/source.name)
 (out/f'shard-{a.shard}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print('Published',report['published'],'of',report['total'],flush=True)
 return int(any(r['status']!='published' for r in results))
if __name__=='__main__':raise SystemExit(main())
