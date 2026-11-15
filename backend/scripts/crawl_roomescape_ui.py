"""전방의 정상 공개 웹 UI에서 렌더링된 카드만 읽는 수집기."""
import argparse,json,pathlib,subprocess,datetime,re,os,shutil
ROOT=pathlib.Path(__file__).resolve().parents[1]
BROWSER=os.environ.get('AGENT_BROWSER_BIN') or shutil.which('agent-browser')
SESSION=os.environ.get('AGENT_BROWSER_SESSION','escapemap-competitor-audit')
def browser(*args,code=None):
 if not BROWSER:raise RuntimeError('agent-browser를 설치하거나 AGENT_BROWSER_BIN을 지정하세요.')
 r=subprocess.run([BROWSER,'--session',SESSION,*args],input=code,text=True,capture_output=True,timeout=40)
 if r.returncode:raise RuntimeError(r.stderr[-800:])
 value=r.stdout.strip()
 if code:
  try:
   value=json.loads(value)
   if isinstance(value,str):value=json.loads(value)
  except (ValueError,TypeError):pass
 return value

def main():
 p=argparse.ArgumentParser();p.add_argument('kind',choices=['cafes','themes']);p.add_argument('--rounds',type=int,default=400);p.add_argument('--from-top',action='store_true');a=p.parse_args()
 dest=ROOT/'reports/competitors/roomescape.json'
 data=json.loads(dest.read_text()) if dest.exists() else {'source':'roomescape','cafes':[],'themes':[],'coverage':{'complete':False,'method':'공개 웹 UI의 카드 텍스트'}}
 browser('mouse','move','1000','650')
 if a.from_top:browser('mouse','wheel','-1000000')
 seen={x['name']+'\n'+x.get('cafe_name',''):x for x in data[a.kind]};stale=0;pass_seen=set()
 for i in range(a.rounds):
  labels=browser('eval','--stdin',code="JSON.stringify(Array.from(document.querySelectorAll('[aria-label]')).map(n=>n.getAttribute('aria-label')).filter(x=>x&&x.includes('\\n')))")
  before=len(pass_seen)
  if isinstance(labels,list):
   for label in labels:
    parts=[x.strip() for x in label.split('\n') if x.strip()]
    if a.kind=='cafes':
     if len(parts)<3 or not parts[1].replace('.','').isdigit():continue
     row={'name':parts[0],'source_region':'전국','source_url':'https://www.roomescape.co.kr/cafe','raw_label':label}
    else:
     rating=next((j for j in range(2,len(parts)-1) if parts[j].replace('.','').isdigit() and re.fullmatch(r'\([\d,]+\)',parts[j+1])),None)
     if rating is None:continue
     title=' '.join(parts[1:rating-1]) if rating>=3 else parts[0]
     row={'name':title,'cafe_name':parts[rating-1],'source_region':'전국','source_url':'https://www.roomescape.co.kr/theme','raw_label':label}
    key=row['name']+'\n'+row.get('cafe_name','')
    seen[key]=row;pass_seen.add(key)
  stale=stale+1 if len(pass_seen)==before else 0
  data[a.kind]=list(seen.values());data['collected_at']=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat()
  data['coverage'][a.kind]={'count':len(seen),'rounds':i+1,'pass_unique_count':len(pass_seen),'scroll_end_observed':stale>=120}
  dest.write_text(json.dumps(data,ensure_ascii=False,indent=2))
  if i%15==0:print(a.kind,i+1,len(seen),'stale',stale,flush=True)
  if stale>=120:break
  browser('mouse','wheel','440')
 print('saved',a.kind,len(seen),flush=True)
if __name__=='__main__':main()
