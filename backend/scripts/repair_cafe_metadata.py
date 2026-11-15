"""주소 기준 지역 정정 및 공식 확인한 누락 지점 등록. --apply 때만 변경."""
import argparse,datetime,json,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.areas import resolve_cafe_area
from app.config import settings
from app.firestore_db import init_firestore,get_db
SOURCE='https://www.ex-cape.com/reservation/'
VERIFIED=[
 {'id':'27329834','name':'룸익스케이프','branch_name':'신촌 블랙점','address':'서울 서대문구 연세로4길 6 3층'},
 {'id':'1542251042','name':'룸익스케이프','branch_name':'신촌 화이트점','address':'서울 서대문구 명물길 66 2층'},
 {'id':'912842418','name':'룸익스케이프','branch_name':'신촌 올리브점','address':'서울 서대문구 연세로9길 25 지하 1층'},
]
PUBLIC_FIELDS=('id','name','branch_name','address','area','website_url','engine','is_active')
def plan(rows):
 byid={r['id']:r for r in rows};changes=[]
 for c in rows:
  area=resolve_cafe_area(c.get('area'),c.get('address'))
  if area!=c.get('area'):changes.append({'id':c['id'],'before':{'area':c.get('area')},'after':{'area':area},'reason':'stored_address_region_correction','address':c.get('address')})
 for item in VERIFIED:
  cid=item['id'];old=byid.get(cid,{})
  # 주소나 이름이 같아도 기존 문서를 합치거나 ID를 바꾸지 않는다.
  desired={k:v for k,v in item.items() if k!='id'}
  desired.update(area=resolve_cafe_area(None,item['address']),website_url='https://ex-cape.com/',metadata_source_url=SOURCE,metadata_verified_at='2026-11-15')
  if not old:desired.update(is_active=True,supported_area=True,engine='playtheworld',crawled=False)
  changed={k:v for k,v in desired.items() if old.get(k)!=v}
  if changed:changes.append({'id':cid,'before':{k:old.get(k) for k in changed},'after':changed,'reason':'official_store_directory','source':SOURCE,'new':not bool(old)})
 return changes

def main():
 p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');p.add_argument('--snapshot',type=pathlib.Path,help='이미 읽은 카페 목록 JSON 사용; 읽기 쿼터 소진 시 중복 전체 조회 방지');a=p.parse_args()
 init_firestore(settings.firebase_credentials_path);db=get_db();rows=json.loads(a.snapshot.read_text()) if a.snapshot else [dict(d.to_dict(),id=d.id) for d in db.collection('cafes').stream(retry=None,timeout=25)]
 changes=plan(rows);report=ROOT/'reports/crawlers/cafe-metadata-repair-2026-11-15.json'
 payload={'checked_at':datetime.datetime.now().astimezone().isoformat(),'applied':False,'changes':changes};report.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
 print('planned',len(changes),'new',sum(bool(c.get('new')) for c in changes),flush=True)
 if not a.apply:return
 batch=db.batch()
 for c in changes:
  ref=db.collection('cafes').document(c['id'])
  if c.get('new'):batch.create(ref,c['after'])
  else:batch.set(ref,c['after'],merge=True)
 try:
  if changes:batch.commit(retry=None,timeout=25)
 except Exception as error:
  payload['apply_error']=type(error).__name__;report.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n');print('DB 반영 실패:',type(error).__name__,flush=True);raise SystemExit(1)
 merged={r['id']:r for r in rows}
 for c in changes:merged.setdefault(c['id'],{'id':c['id']}).update(c['after'])
 # 名前・住所など公開基本情報だけ。予約結果・認証情報は含めない。
 snapshot={'captured_at':payload['checked_at'],'source':'Firestore cafe public metadata snapshot; not a reservation cache','cafes':[{k:r.get(k) for k in PUBLIC_FIELDS} for r in sorted(merged.values(),key=lambda r:r['id'])]}
 (ROOT/'data/cafe-directory.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+'\n')
 payload['applied']=True;report.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n');print('applied; directory entries',len(merged))
if __name__=='__main__':main()
