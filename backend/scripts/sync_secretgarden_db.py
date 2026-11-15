"""비밀의화원 공식 지점별 공개 예약표. 예약 제출 없이 GET만 수행합니다."""
from __future__ import annotations
import sys,re,time
from pathlib import Path
from datetime import date,datetime,timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlencode
import requests
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.config import settings
from app.firestore_db import init_firestore,get_db,upsert_cafe,get_or_create_theme,upsert_cafe_date_schedules
from app.crawl_time import business_slot_datetime
BASE_URL='https://www.secretgardenescape.com'
REQUEST_DELAY=.3
BRANCHES = [{'cafe_id': 'official_secretgarden_3',
  'cafe_name': '비밀의화원',
  'branch_name': '서면점',
  'address': '부산 부산진구 중앙대로 700 (부전동) 지하1층',
  'area': 'busan',
  'shop': 3},
 {'cafe_id': 'official_secretgarden_4',
  'cafe_name': '비밀의화원',
  'branch_name': '대학로점',
  'address': '서울 종로구 대학로 130 (동숭동, 맥도널드) 지하 1층',
  'area': 'myeongdong',
  'shop': 4},
 {'cafe_id': 'official_secretgarden_5',
  'cafe_name': '비밀의화원',
  'branch_name': '건대점',
  'address': '서울 광진구 아차산로 235 (화양동) 3층',
  'area': 'konkuk',
  'shop': 5},
 {'cafe_id': 'official_secretgarden_6',
  'cafe_name': '비밀의화원',
  'branch_name': '동성로점',
  'address': '대구 중구 동성로5길 55 (삼덕동1가) 4층',
  'area': 'daegu',
  'shop': 6},
 {'cafe_id': 'official_secretgarden_10',
  'cafe_name': '비밀의화원',
  'branch_name': '광주점',
  'address': '광주 동구 충장로 90 (충장로2가, 갤러리존) 4층',
  'area': 'gwangju',
  'shop': 10},
 {'cafe_id': 'official_secretgarden_11',
  'cafe_name': '비밀의화원',
  'branch_name': '시네마틱 혜화점',
  'address': '서울 종로구 대명길 9 (명륜4가) 지하2층 방탈출',
  'area': 'myeongdong',
  'shop': 11},
 {'cafe_id': 'official_secretgarden_12',
  'cafe_name': '비밀의화원',
  'branch_name': '전주점',
  'address': '전북 전주시 완산구 문화광장로 2 (고사동) 지하층',
  'area': 'jeonbuk',
  'shop': 12}]

def reservation_url(shop,day):
 return BASE_URL+'/reservation.html?'+urlencode({'k_shopno':shop,'rdate':day.isoformat()})
def parse_schedule(html,shop,day):
 soup=BeautifulSoup(html,'html.parser');calendar=soup.select_one('#datepicker_bbs')
 if not calendar or calendar.get('value')!=day.isoformat():raise ValueError('예약 날짜 또는 페이지 구조가 일치하지 않습니다.')
 result=[]
 for box in soup.select('.time_Area'):
  title=box.select_one('.h3_theme')
  if not title:continue
  slots=[]
  for li in box.select('.reserve_Time li'):
   span=li.select_one('.time');a=li.select_one('a')
   if not span or not a:continue
   value=span.get_text(strip=True)
   if not re.fullmatch(r'(?:[012]\d):[0-5]\d',value):continue
   h,m=map(int,value.split(':'));business_slot_datetime(day,h,m)
   action=a.get('onclick','')
   if 'end' in a.get('class',[]):status='full'
   elif re.search(r"SendVar\('\d+','"+day.isoformat()+"','"+re.escape(value)+r"'\)",action):status='available'
   else:continue  # Hidden possible/impossible labels alone do not indicate availability.
   slots.append({'time':value,'status':status,'booking_url':reservation_url(shop,day) if status=='available' else None})
  result.append({'name':title.get_text(strip=True),'slots':slots})
 return result

def main(run_schedule=True,days=14):
 init_firestore(settings.firebase_credentials_path);db=get_db();today=datetime.now(ZoneInfo('Asia/Seoul')).date()
 for b in BRANCHES:
  cid=b['cafe_id'];name_to_id={};at=datetime.now(ZoneInfo('Asia/Seoul'))
  for offset in range(days+1 if run_schedule else 1):
   day=today+timedelta(days=offset);r=requests.get(reservation_url(b['shop'],day),timeout=25);r.raise_for_status()
   parsed=parse_schedule(r.text,b['shop'],day)
   if not parsed:raise ValueError('공식 예약표에 테마가 없습니다: '+cid)
   if offset==0:
    upsert_cafe(db,cid,{'name':b['cafe_name'],'branch_name':b['branch_name'],'address':b['address'],'area':b['area'],'website_url':reservation_url(b['shop'],day),'engine':'secretgarden','is_active':True,'crawled':True})
   data={}
   for theme in parsed:
    tid=get_or_create_theme(db,cid,theme['name'],{'is_active':True});name_to_id[theme['name']]=tid
    if theme['slots']:data[tid]={'slots':theme['slots']}
   if run_schedule and data:upsert_cafe_date_schedules(db,day.isoformat(),cid,data,at)
   print(cid,day,len(parsed),'themes',sum(len(t['slots']) for t in parsed),'slots',flush=True);time.sleep(REQUEST_DELAY)
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--days',type=int,default=14);p.add_argument('--no-schedule',action='store_true');a=p.parse_args();main(not a.no_schedule,a.days)
