"""공식 공개 예약표: 플러스이스케이프(날짜 JSON), 익스플로리아(날짜 HTML)."""
import sys,re,time
from pathlib import Path
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.config import settings
from app.areas import address_to_area
from app.firestore_db import init_firestore,get_db,upsert_cafe,get_or_create_theme,upsert_cafe_date_schedules
REQUEST_DELAY=.2
BRANCHES=[
 {'cafe_id':'official_plus','cafe_name':'플러스이스케이프','branch_name':'','address':'대구광역시 동구 장등로 36-1 6층','base_url':'https://www.plus-escape.com','engine':'plus_public'},
 {'cafe_id':'official_exploria','cafe_name':'익스플로리아이스케이프','branch_name':'수원점','address':'경기 수원시 팔달구 효원로235번길 51 3층','base_url':'https://www.exploria-escape.kr','engine':'exploria_public'},
]

def parse_plus_slots(data,day):
 if data.get('date')!=day.isoformat() or data.get('themeId')!=30002 or not isinstance(data.get('slots'),list):raise ValueError('공식 시간표 날짜/테마 불일치')
 slots=[]
 for row in data['slots']:
  value=row.get('startTime','')[:5]
  if not re.fullmatch(r'(?:[012]\d):[0-5]\d',value) or not isinstance(row.get('available'),bool):raise ValueError('공식 시간표 구조 변경')
  status='closed' if data.get('notYetOpen') or data.get('isBlocked') else 'available' if row['available'] else 'full'
  slots.append({'time':value,'status':status,'booking_url':'https://www.plus-escape.com/reservation' if status=='available' else None})
 return slots

def parse_exploria(html,day):
 soup=BeautifulSoup(html,'html.parser');calendar=soup.select_one('input[type="date"]')
 if not calendar or calendar.get('value')!=day.isoformat():raise ValueError('예약 날짜 불일치')
 themes=[]
 for article in soup.select('article.ex-book-card'):
  title=article.select_one('h3');slots=[]
  if not title:continue
  for el in article.select('.ex-slots .ex-slot'):
   value=el.select_one('b');label=el.select_one('small')
   if not value or not label:continue
   value=value.get_text(strip=True);label=label.get_text(strip=True)
   if not re.fullmatch(r'(?:[012]\d):[0-5]\d',value):raise ValueError('시간 형식 변경')
   if label=='예약' and el.name=='a' and el.get('href'):status='available'
   elif label=='마감':status='full'
   else:raise ValueError('알 수 없는 공식 예약 상태')
   slots.append({'time':value,'status':status,'booking_url':urljoin('https://www.exploria-escape.kr',el['href']) if status=='available' else None})
  themes.append({'name':title.get_text(strip=True),'slots':slots})
 return themes

def fetch_themes(branch,day):
 if branch['engine']=='plus_public':
  response=requests.get(branch['base_url']+'/api/themes/30002/available-slots',params={'date':day.isoformat()},timeout=25);response.raise_for_status()
  return [{'name':'루나빌리지','slots':parse_plus_slots(response.json(),day)}]
 response=requests.get(branch['base_url']+'/theme/'+day.isoformat()+'/',timeout=25);response.raise_for_status();themes=parse_exploria(response.text,day)
 if not themes:raise ValueError('공식 테마 파싱 실패')
 return themes

def main(run_schedule=True,days=14):
 init_firestore(settings.firebase_credentials_path);db=get_db();today=datetime.now(ZoneInfo('Asia/Seoul')).date()
 for branch in BRANCHES:
  cid=branch['cafe_id']
  for offset in range(days+1 if run_schedule else 1):
   day=today+timedelta(days=offset);themes=fetch_themes(branch,day)
   if offset==0:upsert_cafe(db,cid,{'name':branch['cafe_name'],'branch_name':branch['branch_name'],'address':branch['address'],'area':address_to_area(branch['address']),'website_url':branch['base_url'],'engine':branch['engine'],'is_active':True,'crawled':any(t['slots'] for t in themes)})
   data={}
   for theme in themes:
    tid=get_or_create_theme(db,cid,theme['name'],{'is_active':True})
    if theme['slots']:data[tid]={'slots':theme['slots']}
   if run_schedule and data:upsert_cafe_date_schedules(db,day.isoformat(),cid,data,datetime.now(ZoneInfo('Asia/Seoul')))
   print(cid,day,len(themes),'themes',sum(len(t['slots']) for t in themes),'slots',flush=True);time.sleep(REQUEST_DELAY)
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--days',type=int,default=14);p.add_argument('--no-schedule',action='store_true');a=p.parse_args();main(not a.no_schedule,a.days)
