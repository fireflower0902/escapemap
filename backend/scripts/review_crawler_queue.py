"""현황판 기준 우선순위별 지점 단독 검증. 실제 Firestore에는 쓰지 않습니다."""
import argparse,collections,concurrent.futures,datetime,json,pathlib,subprocess,sys,threading
ROOT=pathlib.Path(__file__).resolve().parents[1]

def main():
 p=argparse.ArgumentParser();p.add_argument('phase',choices=['safety','orange','gray_connected']);p.add_argument('--baseline',type=pathlib.Path,default=ROOT/'reports/crawlers/priority-review-2026-11-15/baseline.json');a=p.parse_args()
 groups=json.loads(a.baseline.read_text());out=ROOT/'reports/crawlers/priority-review-2026-11-15'/a.phase;out.mkdir(parents=True,exist_ok=True)
 tasks=[]
 if a.phase=='safety':tasks=[(s,None) for s in ['sync_oasisescape_db','sync_rememberesc_db','sync_reverseesc_db','sync_escapers_db','sync_zeroworld_db']]
 else:
  for c in groups[a.phase]:
   if c['scripts']==['sync_roomsa_catalog_db']:continue # 공개 목록 전용/시간대 보류 사유는 이미 확인됨.
   tasks.append((c['scripts'][0],c['id']))
 locks=collections.defaultdict(lambda:threading.Semaphore(2));results=[]
 def run(task):
  script,cid=task;dest=out/(cid or script)
  cmd=[sys.executable,str(ROOT/'scripts/check_crawlers.py'),script,'--days','2','--timeout','55','--output',str(dest)]
  if cid:cmd+=['--cafe-id',cid]
  with locks[script]:r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
  file=dest/(script+'.json')
  try:data=json.loads(file.read_text())
  except:data={'script':script,'status':'error','error':r.stderr[-800:]}
  data['requested_id']=cid
  return data
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  for i,result in enumerate(pool.map(run,tasks),1):
   results.append(result);(out/'summary.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
   print(a.phase,i,len(tasks),result['script'],result['requested_id'],result.get('status'),result.get('themes_fetched',0),result.get('slots',0),flush=True)
 print('DONE',a.phase,dict(collections.Counter(x['status'] for x in results)),flush=True)
if __name__=='__main__':main()
