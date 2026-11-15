"""제로월드 개편 공식 예약표. 읽기 전용 theme_list/theme_time_list만 요청합니다."""
import sys,time
from pathlib import Path
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlencode
import requests
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.config import settings
from app.sinbi_reservation import parse_theme_list,parse_time_list
from app.firestore_db import init_firestore,get_db,upsert_cafe,get_or_create_theme,upsert_cafe_date_schedules
BASE_URL='https://zeroworldkorea.com'
REQUEST_DELAY=.2
BRANCHES = [{'cafe_id': 'official_zeroworld_1',
  'cafe_name': '제로월드',
  'branch_name': '김포본점',
  'address': '경기도 김포시 김포한강9로75번길 180 405호, 406호(구래동, 두원타워)',
  'phone': '031-982-9074',
  'area': 'gyeonggi',
  'zizum_num': '1',
  's_subj': 'A'},
 {'cafe_id': '1345840219',
  'cafe_name': '제로월드',
  'branch_name': '강남점',
  'address': '서울특별시 서초구 서초대로72길 40 지하1층 1비1호, 비2호, 비3호, 비4호(서초동, 강남오피스텔)',
  'phone': '02-599-1661',
  'area': 'gangnam',
  'zizum_num': '4',
  's_subj': 'A'},
 {'cafe_id': '1732671994',
  'cafe_name': '제로월드',
  'branch_name': '홍대점',
  'address': '서울특별시 마포구 잔다리로6길 20-9 지하 2층 전체(서교동)',
  'phone': '02-336-0275',
  'area': 'hongdae',
  'zizum_num': '5',
  's_subj': 'A'},
 {'cafe_id': 'official_zeroworld_2',
  'cafe_name': '제로월드',
  'branch_name': '다이브 건대점',
  'address': '서울특별시 광진구 아차산로26길 22 1층 1지층 전호(자양동)',
  'phone': '02-499-1223',
  'area': 'konkuk',
  'zizum_num': '2',
  's_subj': 'B'}]

def query(session,branch,day,act,theme=''):
 if act not in {'theme_list','theme_time_list'}:raise ValueError('예약 조회 외 동작 금지')
 r=session.post(BASE_URL+'/core/res/rev.make.sel.php',data={'act':act,'zizum_num':branch['zizum_num'],'s_subj':branch['s_subj'],'rev_days':day.isoformat(),'theme_num':theme},timeout=25);r.raise_for_status();return r.text

def booking_url(branch,day):
 return BASE_URL+'/layout/res/home.php?'+urlencode({'go':'rev.make','zizum_num':branch['zizum_num'],'s_subj':branch['s_subj'],'rev_days':day.isoformat()})

def main(run_schedule=True,days=14):
 init_firestore(settings.firebase_credentials_path);db=get_db();today=datetime.now(ZoneInfo('Asia/Seoul')).date();session=requests.Session()
 for b in BRANCHES:
  cid=b['cafe_id'];first=parse_theme_list(query(session,b,today,'theme_list'))
  if not first:raise ValueError('공식 테마 목록 확인 실패: '+cid)
  upsert_cafe(db,cid,{'name':b['cafe_name'],'branch_name':b['branch_name'],'address':b['address'],'phone':b['phone'],'area':b['area'],'website_url':booking_url(b,today),'engine':'zeroworld_current','is_active':True,'crawled':True})
  for offset in range(days+1 if run_schedule else 1):
   day=today+timedelta(days=offset);themes=first if offset==0 else parse_theme_list(query(session,b,day,'theme_list'));data={}
   for source_id,theme in themes.items():
    tid=get_or_create_theme(db,cid,theme['name'],{'is_active':True,'duration_min':theme['duration_min']})
    if not run_schedule:continue
    slots=parse_time_list(query(session,b,day,'theme_time_list',source_id))
    for slot in slots:slot['booking_url']=booking_url(b,day) if slot['status']=='available' else None
    if slots:data[tid]={'slots':slots}
    time.sleep(REQUEST_DELAY)
   if data:upsert_cafe_date_schedules(db,day.isoformat(),cid,data,datetime.now(ZoneInfo('Asia/Seoul')))
   print(cid,day,len(themes),'themes',sum(len(v['slots']) for v in data.values()),'slots',flush=True)
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--days',type=int,default=14);p.add_argument('--no-schedule',action='store_true');a=p.parse_args();main(not a.no_schedule,a.days)
