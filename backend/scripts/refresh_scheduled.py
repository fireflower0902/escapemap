"""검증된 전국 지점을 분할 수집하고 실패를 CI 결과와 요약에 남긴다."""
from __future__ import annotations
import argparse, collections, concurrent.futures, datetime, json, pathlib, shutil, subprocess, sys, threading
ROOT=pathlib.Path(__file__).resolve().parents[1]

def select_tasks(items,shard,shards):
 if not 0<=shard<shards:raise ValueError('Invalid shard')
 partition=sorted(items,key=lambda row:(row['script'],row['cafe_id']))[shard::shards]
 groups=collections.defaultdict(collections.deque)
 for row in partition:groups[row['script']].append(row)
 ordered=[]
 while any(groups.values()):
  for script in sorted(groups):
   if groups[script]:ordered.append(groups[script].popleft())
 return ordered

def failure_details(report_path):
 try:
  check=json.loads(report_path.read_text())
 except (OSError,ValueError):
  return {'failure_kind':'infrastructure','reason':'검증 결과 파일이 생성되지 않음'}
 error=check.get('error','')
 infrastructure=error.startswith('storage: ') or '수집 실패 상태의 DB 기록도 실패했습니다.' in check.get('issues',[])
 calls=check.get('http_calls',[])
 codes=sorted({c['status'] for c in calls if c.get('status',0)>=400})
 # Do not echo raw exceptions/URLs, which could contain credentials.
 reason='Supabase 저장 오류' if infrastructure else 'HTTP '+','.join(map(str,codes)) if codes else '시간표 검증 오류' if error else '시간표 미수집 또는 검증 경고'
 return {'failure_kind':'infrastructure' if infrastructure else 'site','reason':reason}

def main():
 p=argparse.ArgumentParser();p.add_argument('--days',type=int,default=6);p.add_argument('--shard',type=int,default=0);p.add_argument('--shards',type=int,default=1);p.add_argument('--workers',type=int,default=2);p.add_argument('--timeout',type=int,default=180);p.add_argument('--allow-site-failures',action='store_true',help='개별 사이트 실패는 경고로 남기고 전체 수집률은 별도 집계 작업에서 판정');a=p.parse_args()
 if not 0<=a.days<=14 or not 1<=a.workers<=6 or a.timeout<1:p.error('Invalid collection limits')
 tasks=select_tasks(json.loads((ROOT/'data/scheduled-crawlers.json').read_text()),a.shard,a.shards)
 locks=collections.defaultdict(lambda:threading.Semaphore(1));results=[]
 def run(task):
  with locks[task['script']]:
   source=ROOT/'reports/crawlers/supabase'/f"{task['script']}-{task['cafe_id']}.json"
   source.unlink(missing_ok=True)  # A checked-in report from an older run is not evidence for this run.
   try:
    r=subprocess.run([sys.executable,str(ROOT/'scripts/run_supabase_crawler.py'),task['script'],'--cafe-id',task['cafe_id'],'--days',str(a.days),'--timeout',str(a.timeout)],cwd=ROOT,capture_output=True,text=True,timeout=a.timeout+30)
    return {**task,'status':'published' if r.returncode==0 else 'failed','exit_code':r.returncode,**(failure_details(source) if r.returncode else {})}
   except subprocess.TimeoutExpired:return {**task,'status':'timeout','exit_code':124,'failure_kind':'infrastructure','reason':'수집 자식 프로세스 종료/결과 기록 제한 시간 초과'}
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
 failures=[r for r in results if r['status']!='published']
 for row in failures:
  print(('::error::' if row.get('failure_kind')=='infrastructure' else '::warning::')+row['script']+' / '+row['cafe_id']+': '+row['reason'],flush=True)
 return int(any(r.get('failure_kind')=='infrastructure' or not a.allow_site_failures for r in failures))
if __name__=='__main__':raise SystemExit(main())
