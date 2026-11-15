"""공식 지점 안내로 누락 카페 검증. 기본은 계획 생성, --apply는 신규 문서만 추가."""
from __future__ import annotations
import argparse,collections,datetime,hashlib,json,pathlib,re,sys,time
from urllib.parse import urljoin,parse_qs,urlparse
import requests
from bs4 import BeautifulSoup
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.compare_competitors import normalize,full_name,table
from app.areas import address_to_area
REPORT=ROOT/'reports/competitors'

def load(name):return json.loads((REPORT/name).read_text())
def save(name,data):(REPORT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
def get(url):
 r=requests.get(url,timeout=30);r.raise_for_status();return BeautifulSoup(r.content,'html.parser')
def text(node):return node.get_text(' ',strip=True) if node else ''
def known_cafe(cafe,ours):
 key=normalize(full_name(cafe))
 def same(c):
  if normalize(full_name(c))==key or key in {normalize(a) for a in c.get('aliases',[])}:return True
  return bool(c.get('branch_name') and cafe.get('branch_name') and normalize(c.get('name'))==normalize(cafe.get('name')) and normalize(c['branch_name']).removesuffix('점')==normalize(cafe['branch_name']).removesuffix('점'))
 return next((c for c in ours if same(c)),None)
def build_queue(ours):
 groups={}
 for result in load('comparison.json')['results']:
  for c in result['cafes']:
   if c['status']=='matched':continue
   key=normalize(c['name']);row=groups.setdefault(key,{'key':key,'name':c['name'],'status':'unverified','sources':[],'addresses':[],'candidates':[]})
   row['sources'].append(result['source'])
   if c.get('address') and c['address'] not in row['addresses']:row['addresses'].append(c['address'])
   row['candidates']+=c.get('candidates',[])
 return list(groups.values())

def collect_sherlock(ours):
 base='https://www.sherlock-holmes.co.kr';directory=base+'/branch/';s=get(directory);rows=[]
 for box in s.select('.col.s3'):
  title=box.select_one('.tit');a=next((a for a in box.select('a[href]') if text(a)=='지점소개'),None)
  if not title or not a:continue
  branch=text(title);c={'name':'셜록홈즈','branch_name':branch,'website_url':urljoin(base,a['href'])}
  if known_cafe(c,ours):continue
  page=get(c['website_url']);section=page.select_one('.branch_view');location=section.select_one('.contact .location') if section else None
  booking=next((a for a in section.select('a[href]') if text(a)=='예약하기'),None) if section else None
  if not location or not booking:continue
  bno=parse_qs(urlparse(c['website_url']).query)['bno'][0]
  c.update(id='official_sherlock_'+bno,address=text(location),phone=text(section.select_one('.call')),booking_url=urljoin(base,booking['href']),engine='sherlock',source_directory=directory,themes=[],verification_status='official_listing_verified')
  rows.append(c);print('verified',full_name(c),flush=True);time.sleep(.25)
 return rows

def collect_sslone(ours):
 base='https://sslone.co.kr/layout/res/';directory=base+'home.php?go=main';s=get(directory);rows=[]
 for a in s.select('a[href]'):
  if '지점 바로예약' not in text(a):continue
  block=a.parent;heading=block.find(['h2','h3','h4']);branch=text(heading)
  if not branch:continue
  c={'name':'상상락원','branch_name':branch}
  if known_cafe(c,ours):continue
  parts=list(block.stripped_strings);phone=next((p for p in parts if re.match(r'0[\d-]{8,}',p)),'');address=next((p for p in parts if re.match(r'^(서울(?:특별시)?|전북(?:특별자치도)?|전주시)\s',p)),'')
  if address.startswith('전주시'):address='전북특별자치도 '+address
  url=urljoin(base,a['href']);zizum=parse_qs(urlparse(url).query)['s_zizum'][0];page=get(url)
  themes=[]
  for box in page.select('.theme_box'):
   h=box.find(['h3','h4','h2']);name=text(h)
   if name:themes.append({'name':name})
  c.update(id='official_sslone_'+zizum,address=address,phone=phone,website_url=url,booking_url=url,engine='sinbiweb',source_directory=directory,themes=themes,verification_status='official_listing_verified',experience_type='table_escape')
  if address:rows.append(c);print('verified',full_name(c),'themes',len(themes),flush=True)
 return rows

def plan():
 ours=load('ours.json');queue=build_queue(ours);rows=collect_sherlock(ours['cafes'])+collect_sslone(ours['cafes'])
 at=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat()
 for c in rows:c.update(verified_at=at,area=address_to_area(c['address']),crawled=False,is_active=True,supported_area=True,crawler_status='not_tested',verification_sources=[c['source_directory'],c['website_url']])
 previous=load('verified-additions.json') if (REPORT/'verified-additions.json').exists() else {}
 merged={c['id']:c for c in previous.get('cafes',[])};merged.update({c['id']:c for c in rows})
 prior_queue=load('verification-queue.json') if (REPORT/'verification-queue.json').exists() else []
 queued={q['key']:q for q in prior_queue};queued.update({q['key']:q for q in queue if q['key'] not in queued});queue=list(queued.values())
 data={**previous,'verified_at':at,'scope':'공식 사이트 검증 1차: 셜록홈즈·상상락원. 전체 미검증 후보는 verification-queue.json에 보존.','cafes':list(merged.values())}
 save('verified-additions.json',data);save('verification-queue.json',queue);write_report(data,queue);return data

def write_report(data,queue):
 applied=set(data.get('applied_cafe_ids',[]))
 lines=['# 공식 사이트 검증 및 목록 반영','',data['scope'],'',f"검증 시각: {data['verified_at']}",'',f"공식 검증 신규 후보 {len(data['cafes'])}곳 · 반영 완료 {len(applied)}곳 · 미검증 후보 {sum(q['status']=='unverified' for q in queue)}개",'', '공식 지점 안내·주소·예약 링크를 확인했습니다. 사이트 존재와 현재 빈자리 확보는 별도입니다. 신규 카페는 미검증으로 시작하고, 실제 조회 검증 보고서의 테마·시간대 수와 범위를 별도로 기록합니다. 경쟁사 테마를 그대로 복사하지 않습니다. 상상락원은 테이블 방탈출로 구분합니다.','',table(['카페','주소','공식 근거','DB 테마 수','반영','수집 검증 (테마/시간대)'],[(full_name(c),c['address'],f"[지점/예약]({c['website_url']})",c.get('stored_themes',len(c['themes'])),'반영 완료' if c['id'] in applied else '미반영', ('통과' if c.get('crawler_status')=='smoke_pass' else c.get('crawler_status','미검증'))+' · '+str(data.get('crawler_checks',{}).get(c['id'],{}).get('themes','—'))+' / '+str(data.get('crawler_checks',{}).get(c['id'],{}).get('slots','—'))) for c in data['cafes']]),'', '검증 통과는 표시된 날짜·지점의 조회·파싱 성공이며 모든 미래 날짜의 빈자리나 예약 성사를 보장하지 않습니다.', '', '## 남은 검증 대상','',table(['카페명','경쟁사','상태'],[(q['name'],','.join(sorted(set(q['sources']))),q['status']) for q in queue if q['status']=='unverified']),'']
 (REPORT/'official-verification.md').write_text('\n'.join(lines))

def apply(data):
 from app.config import settings
 from app.firestore_db import init_firestore,get_db,_theme_doc_id
 init_firestore(settings.firebase_credentials_path);db=get_db()
 existing=[dict(d.to_dict(),id=d.id) for d in db.collection('cafes').stream()];created=[];themes_created=[];skipped=[]
 for row in data['cafes']:
  if known_cafe(row,existing):skipped.append(row['id']);continue
  if not row.get('address') or row.get('verification_status')!='official_listing_verified':raise ValueError('검증 근거 부족')
  payload={k:v for k,v in row.items() if k not in ('id','themes','source_directory')}
  # create has an exists=false precondition; existing documents are never overwritten.
  batch=db.batch();batch.create(db.collection('cafes').document(row['id']),payload);new_themes=[]
  for theme in row['themes']:
   tid=_theme_doc_id(row['id'],theme['name']);ref=db.collection('themes').document(tid)
   if ref.get().exists:continue
   batch.create(ref,{'name':theme['name'],'cafe_id':row['id'],'is_active':True,'verified_at':row['verified_at'],'verification_sources':[row['booking_url']],'verification_status':'official_listing_verified'});new_themes.append(tid)
  batch.commit();created.append(row['id']);themes_created+=new_themes;existing.append(row)
  data['applied_cafe_ids']=list(set(data.get('applied_cafe_ids',[])+created));data['applied_theme_ids']=list(set(data.get('applied_theme_ids',[])+themes_created));save('verified-additions.json',data)
 current={'source':'ours','collected_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'cafes':[dict(d.to_dict(),id=d.id) for d in db.collection('cafes').stream()],'themes':[dict(d.to_dict(),id=d.id) for d in db.collection('themes').stream()]}
 save('ours.json',current)
 queue=load('verification-queue.json')
 for q in queue:
  found=next((c for c in data['cafes'] if q['key']==normalize(full_name(c))),None)
  if found and found['id'] in data.get('applied_cafe_ids',[]):q.update(status='added_verified',our_id=found['id'],verification_sources=found['verification_sources'])
 save('verification-queue.json',queue);write_report(data,queue);print(json.dumps({'cafes_created':len(created),'themes_created':len(themes_created),'already_present':len(skipped),'ours_cafes':len(current['cafes']),'ours_themes':len(current['themes'])}))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');a=p.parse_args()
 apply(load('verified-additions.json')) if a.apply else plan()
