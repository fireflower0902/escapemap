"""실제 DB 및 지점별 읽기 전용 검증 보고서를 합쳐 공식 검증 현황 갱신."""
from __future__ import annotations
import json,datetime,pathlib,sys,collections,argparse
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.verify_catalog_additions import load,save,write_report

def latest_checks():
 checks={}
 for path in (ROOT/'reports/crawlers').rglob('*.json'):
  try:data=json.loads(path.read_text())
  except (ValueError,OSError):continue
  for r in data if isinstance(data,list) else [data]:
   if not isinstance(r,dict) or not r.get('script') or not r.get('checked_at'):continue
   for cid,counts in (r.get('per_cafe') or {}).items():
    if r['checked_at']>checks.get(cid,{}).get('checked_at',''):
     checks[cid]={'script':r['script'],'checked_at':r['checked_at'],'scope':r.get('scope'),'status':r.get('status'),'report':str(path.relative_to(ROOT)),**counts}
 return checks

def main(refresh_db=False,update_status=False):
 if refresh_db:
  from app.config import settings
  from app.firestore_db import init_firestore,get_db
  init_firestore(settings.firebase_credentials_path);db=get_db()
  ours={'source':'ours','collected_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'cafes':[dict(d.to_dict(),id=d.id) for d in db.collection('cafes').stream()],'themes':[dict(d.to_dict(),id=d.id) for d in db.collection('themes').stream()]}
  save('ours.json',ours)
 else:ours=load('ours.json')
 manifest=load('verified-additions.json');checks=latest_checks();cafes={c['id']:c for c in ours['cafes']};theme_counts=collections.Counter(t['cafe_id'] for t in ours['themes']);selected={c['id']:checks[c['id']] for c in manifest['cafes'] if c['id'] in checks}
 manifest['crawler_checks']=selected
 for c in manifest['cafes']:
  record=selected.get(c['id'],{});c['crawler_status']=record.get('status','not_tested');c['stored_themes']=theme_counts[c['id']];c['live_crawled']=cafes.get(c['id'],{}).get('crawled',False)
  if refresh_db and update_status and c['id'] in cafes:
   db.collection('cafes').document(c['id']).update({'crawler_status':c['crawler_status'],'crawler_checked_at':record.get('checked_at'),'crawler_check_report':record.get('report'),'verified_theme_count':record.get('themes',0),'verified_slot_count':record.get('slots',0)})
 queue=load('verification-queue.json');by_name={}
 from scripts.compare_competitors import normalize,full_name
 for c in manifest['cafes']:
  by_name[normalize(full_name(c))]=c
  for alias in c.get('aliases',[]):by_name[normalize(alias)]=c
 for c in ours['cafes']:
  if c.get('alias_verification_sources'):
   for alias in c.get('aliases',[]):by_name[normalize(alias)]=c
 for q in queue:
  c=by_name.get(q['key'])
  if c:q.update(status='added_verified' if c['id'] in manifest.get('applied_cafe_ids',[]) else 'verified_existing',our_id=c['id'],verification_sources=c.get('verification_sources') or c.get('alias_verification_sources',[]))
 save('verified-additions.json',manifest);save('verification-queue.json',queue);write_report(manifest,queue)
 print(json.dumps({'cafes':len(ours['cafes']),'themes':len(ours['themes']),'verified_cafes':len(manifest['cafes']),'applied':len(manifest.get('applied_cafe_ids',[])),'checks':dict(collections.Counter(c['crawler_status'] for c in manifest['cafes'])),'remaining_unverified':sum(q['status']=='unverified' for q in queue)},ensure_ascii=False))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--refresh-db',action='store_true');p.add_argument('--update-status',action='store_true');a=p.parse_args()
 if a.update_status and not a.refresh_db:p.error('--update-status에는 --refresh-db가 필요합니다.')
 main(a.refresh_db,a.update_status)
