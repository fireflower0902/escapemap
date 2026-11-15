"""엑스케이프 개편 공식 공개 예약표. 익명 공개 정보만 조회하며 고객 예약 정보는 읽지 않습니다."""
from __future__ import annotations
import sys,re,json,base64,time
from pathlib import Path
from datetime import date,datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.config import settings
from app.areas import address_to_area
from app.crawl_time import business_slot_datetime
from app.firestore_db import init_firestore,get_db,upsert_cafe,get_or_create_theme,upsert_cafe_date_schedules
BASE_URL='https://xcape.kr'
REQUEST_DELAY=.2
BRANCHES = [{'cafe_id': 'official_xcape_xc',
  'cafe_name': '엑스케이프',
  'branch_name': '건대1호점',
  'source_id': 'cb1f93e5-21fe-44cf-8b8c-82af18356de8',
  'code': 'xc',
  'address': '서울 광진구 동일로 112 엑스케이프 건대점',
  'phone': '024639366'},
 {'cafe_id': 'official_xcape_xr',
  'cafe_name': '엑스크라임',
  'branch_name': '건대2호점',
  'source_id': 'f09c86cb-0979-4e0c-a922-d375fc6f4c1b',
  'code': 'xr',
  'address': '서울 광진구 아차산로29길 38 B1 엑스크라임 방탈출카페',
  'phone': '024648788'},
 {'cafe_id': 'official_xcape_nc',
  'cafe_name': '뉴케이스',
  'branch_name': '건대3호점',
  'source_id': '9efec1c5-7f4c-419f-982a-b74d568b8103',
  'code': 'nc',
  'address': '서울 광진구 아차산로 191 B1층 뉴케이스 방탈출카페',
  'phone': '024981999'},
 {'cafe_id': 'official_xcape_gn',
  'cafe_name': '엑스케이프',
  'branch_name': '강남점',
  'source_id': 'caaa8bcc-de30-4303-849d-31992757eb9c',
  'code': 'gn',
  'address': '서울 강남구 봉은사로2길 16 현도빌딩 지하1층 엑스케이프 방탈출카페',
  'phone': '025559366'},
 {'cafe_id': 'official_xcape_sw',
  'cafe_name': '엑스케이프',
  'branch_name': '수원점',
  'source_id': 'c97814d1-9690-4d14-9925-da8025760c6a',
  'code': 'sw',
  'address': '경기 수원시 팔달구 효원로265번길 40 4층 엑스케이프 방탈출카페',
  'phone': '0312343350'}]

class PublicClient:
 def __init__(self):
  self.session=requests.Session();r=self.session.get(BASE_URL+'/',timeout=25);r.raise_for_status()
  soup=BeautifulSoup(r.text,'html.parser');tag=soup.select_one('script[type="module"][src]')
  if not tag:raise ValueError('공식 공개 모듈을 찾지 못했습니다.')
  asset=self.session.get(urljoin(BASE_URL,tag['src']),timeout=25);asset.raise_for_status()
  base=re.search(r'https://[a-z0-9]+\.supabase\.co',asset.text)
  if not base:raise ValueError('공개 조회 주소가 변경되었습니다.')
  key=None
  for candidate in re.findall(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+',asset.text):
   payload=json.loads(base64.urlsafe_b64decode(candidate.split('.')[1]+'==='))
   if payload.get('role')=='anon':key=candidate;break
  if not key:raise ValueError('공개 익명 조회 설정을 찾지 못했습니다.')
  self.base=base.group();self.session.headers.update(apikey=key,Authorization='Bearer '+key)
 def get(self,table,**params):
  if table not in {'branches','branch_settings','themes','time_slots','holidays'}:raise ValueError('공개 조회 허용 대상이 아닙니다.')
  r=self.session.get(self.base+'/rest/v1/'+table,params=params,timeout=25);r.raise_for_status();data=r.json()
  if not isinstance(data,list):raise ValueError('공개 응답 형식 변경')
  return data

def minutes(value):
 h,m=map(int,value[:5].split(':'));return h*60+m

def opening(settings,day,holidays):
 for exception in settings.get('exceptions') or []:
  if exception.get('date')==day.isoformat():
   if exception.get('kind')=='closed':return None
   if exception.get('kind')=='modified' and exception.get('hours'):return exception['hours']
 holiday=settings.get('holiday')
 if holiday and day.isoformat() in holidays:return holiday.get('hours') if holiday.get('open') else None
 week=settings.get('week') or []
 if len(week)!=7:return {'open':'10:00','close':'23:00'}
 row=next((x for x in week if x['weekday']==(day.weekday()+1)%7),None)
 return row.get('hours') if row and row.get('open') else None

def parse_slots(theme,settings,overrides,day,holidays,now=None):
 now=now or datetime.now(ZoneInfo('Asia/Seoul'));hours=(theme.get('admin_config') or {}).get('hours') or {'firstEntry':'10:40','lastEntry':'22:40','setupMin':15}
 start,end=minutes(hours['firstEntry']),minutes(hours['lastEntry']);step=(theme.get('play_time') or 75)+hours['setupMin']
 if step<=0 or end<start:raise ValueError('테마 운영 시간 형식 변경')
 timetable={f'{i//60:02d}:{i%60:02d}' for i in range(start,end+1,step)}
 actual={x['slot_time'][:5]:x for x in overrides if x.get('theme_id')==theme['id']}
 day_hours=opening(settings,day,holidays);opened=set()
 if day_hours:
  a,b=minutes(day_hours['open']),minutes(day_hours['close'])
  if b<=a:b+=1440
  opened={v for v in timetable if a<=minutes(v)<=b}
 results=[]
 for value in sorted(timetable|set(actual)):
  status='available' if value in opened else 'closed';override=actual.get(value)
  if override:
   state=override.get('status')
   if state not in {'available','blocked','reserved'}:raise ValueError('알 수 없는 공개 시간대 상태: '+str(state))
   status='available' if state=='available' else 'full'
   if state=='blocked' and override.get('auto_release_at'):
    released=datetime.fromisoformat(override['auto_release_at'].replace('Z','+00:00'))
    if released<=now:status='available'
   # Open-room joining is deliberately not advertised as exclusive room availability.
  h,m=map(int,value.split(':'));slot=business_slot_datetime(day,h,m).replace(tzinfo=ZoneInfo('Asia/Seoul'))
  if slot-timedelta(minutes=5)<=now:status='closed'
  results.append({'time':value,'status':status,'booking_url':None})
 return results

def main(run_schedule=True,days=14):
 init_firestore(settings.firebase_credentials_path);db=get_db();client=PublicClient();today=datetime.now(ZoneInfo('Asia/Seoul')).date()
 for branch in BRANCHES:
  bid=branch['source_id'];cid=branch['cafe_id'];themes=client.get('themes',select='id,name,play_time,poster_url,difficulty,admin_config',branch_id='eq.'+bid,is_public='eq.true')
  if not themes:raise ValueError('공개 테마 목록이 비었습니다: '+cid)
  config=client.get('branch_settings',select='week,exceptions,holiday',code='eq.'+branch['code'])
  if len(config)!=1:raise ValueError('지점 운영 설정 확인 실패')
  holidays={x['date'] for x in client.get('holidays',select='date',date='gte.'+today.isoformat())}
  upsert_cafe(db,cid,{'name':branch['cafe_name'],'branch_name':branch['branch_name'],'address':branch['address'],'phone':branch['phone'],'area':address_to_area(branch['address']),'website_url':BASE_URL+'/booking/'+branch['code'],'engine':'xcape_current','is_active':True,'crawled':True})
  ids={t['id']:get_or_create_theme(db,cid,t['name'],{'is_active':True,'duration_min':t.get('play_time'),'poster_url':t.get('poster_url'),'difficulty':t.get('difficulty')}) for t in themes}
  if not run_schedule:continue
  for offset in range(days+1):
   day=today+timedelta(days=offset);overrides=client.get('time_slots',select='theme_id,slot_time,status,auto_release_at',branch_id='eq.'+bid,slot_date='eq.'+day.isoformat());data={}
   for theme in themes:
    slots=parse_slots(theme,config[0],overrides,day,holidays)
    for slot in slots:
     if slot['status']=='available':slot['booking_url']=BASE_URL+'/booking/'+branch['code']
    if slots:data[ids[theme['id']]]={'slots':slots}
   if data:upsert_cafe_date_schedules(db,day.isoformat(),cid,data,datetime.now(ZoneInfo('Asia/Seoul')))
   print(cid,day,len(themes),'themes',sum(len(t['slots']) for t in data.values()),'slots',flush=True);time.sleep(REQUEST_DELAY)
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--days',type=int,default=14);p.add_argument('--no-schedule',action='store_true');a=p.parse_args();main(not a.no_schedule,a.days)
