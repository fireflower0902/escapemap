"""코드케이 공식 지점별 CQ 예약표. UTF-8·공식 지점 코드·테마별 CQ 블록을 구분."""
import sys,re,time,urllib.request
from pathlib import Path
from datetime import date,datetime,timedelta
from urllib.parse import urlencode,urljoin
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.config import settings
from app.firestore_db import init_firestore,get_db,upsert_cafe,get_or_create_theme,upsert_cafe_date_schedules
BASE_URL='http://codek5678.cafe24.com'
SITE_URL='http://www.code-k.co.kr'
REQUEST_DELAY=.2
BRANCHES = [{'cafe_id': '1475074228',
  'cafe_name': '코드케이',
  'branch_name': '인천구월점',
  'address': '인천시 남동구 구월동 1467-1 5층',
  'area': 'incheon',
  'source_code': 'S2'},
 {'cafe_id': 'official_codek_S1',
  'cafe_name': '코드케이',
  'branch_name': '강남점',
  'address': '서울시 강남구 역삼동 813-4 지층',
  'area': 'gangnam',
  'source_code': 'S1'},
 {'cafe_id': 'official_codek_S3',
  'cafe_name': '코드케이',
  'branch_name': '홍대점',
  'address': '서울시 마포구 상수동 86-22 3층',
  'area': 'hongdae',
  'source_code': 'S3'}]

def booking_url(day,source_code):
 return BASE_URL+'/sub/code_sub04_1.html?'+urlencode({'R_JIJEM':source_code,'CHOIS_DATE':day.isoformat(),'DIS_T':'A'})
def _fetch(target_date,source_code='S2'):
 request=urllib.request.Request(booking_url(target_date,source_code),headers={'User-Agent':'Mozilla/5.0'})
 with urllib.request.urlopen(request,timeout=25) as response:return response.read()
def _parse_page(raw,target_date):
 soup=BeautifulSoup(raw,'html.parser');result={}
 calendar=soup.select_one('input[name="chois_date"]')
 if calendar and calendar.get('value') and calendar['value']!=target_date.isoformat():raise ValueError('예약 날짜 불일치')
 for a in soup.select('a[href]'):
  match=re.search(r'CQview\(document\.all\.(CQ\d+)\)',a['href']);title=a.select_one('.thema1, .thema2, .thema3') or a.find('li')
  if not match or not title:continue
  box=soup.find(id=match.group(1))
  if not box:continue
  slots=[]
  for li in box.select('li.timeOn,li.timeOff'):
   m=re.search(r'((?:[012]\d):[0-5]\d)',li.get_text(' ',strip=True))
   if not m:continue
   link=li.find_parent('a',href=True);available='timeOn' in li.get('class',[]) and link is not None
   slots.append({'time':m.group(1),'status':'available' if available else 'full','booking_url':urljoin(BASE_URL+'/sub/',link['href']) if available else None})
  if len({s['time'] for s in slots})!=len(slots):raise ValueError('테마 내 시간대 중복')
  if slots:result[title.get_text(' ',strip=True)]=slots
 return result

def main(run_schedule=True,days=14):
 init_firestore(settings.firebase_credentials_path);db=get_db();today=date.today()
 for branch in BRANCHES:
  cid=branch['cafe_id']
  for offset in range(days+1 if run_schedule else 1):
   day=today+timedelta(days=offset);parsed=_parse_page(_fetch(day,branch['source_code']),day)
   if not parsed:raise ValueError('공식 예약표 파싱 실패: '+cid)
   if offset==0:upsert_cafe(db,cid,{'name':branch['cafe_name'],'branch_name':branch['branch_name'],'address':branch['address'],'area':branch['area'],'website_url':booking_url(day,branch['source_code']),'engine':'codek','is_active':True,'crawled':True})
   data={}
   for name,slots in parsed.items():
    tid=get_or_create_theme(db,cid,name,{'is_active':True})
    if slots:data[tid]={'slots':slots}
   if run_schedule and data:upsert_cafe_date_schedules(db,day.isoformat(),cid,data,datetime.now())
   print(cid,day,len(parsed),'themes',sum(len(v['slots']) for v in data.values()),'slots',flush=True);time.sleep(REQUEST_DELAY)
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--days',type=int,default=14);p.add_argument('--no-schedule',action='store_true');a=p.parse_args();main(not a.no_schedule,a.days)
