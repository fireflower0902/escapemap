"""카오스 공식 공개 시간표: 시각이 명시된 예약 가능 링크만 수집합니다.

마감 셀은 시각을 숨기므로 위치·다른 날짜로 추정하지 않습니다.
전체 마감인 날짜는 6개 테마의 빈 슬롯 목록으로 저장합니다.
"""
from __future__ import annotations
import re,sys,time
from pathlib import Path
from datetime import date,datetime,timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urljoin,urlsplit,parse_qs
import requests
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.firestore_db import init_firestore,get_db,upsert_cafe,get_or_create_theme,upsert_cafe_date_schedules
CAFE_ID='431508316'
SITE_URL='http://chaosesc.co.kr'
RESERVE_URL=SITE_URL+'/2019/bbs/board.php'
CAFE_META={'name':'카오스이스케이프','branch_name':None,'address':'전북특별자치도 전주시 덕진구 명륜5길 10-2','area':'jeonbuk','engine':'chaosesc','website_url':SITE_URL,'is_active':True,'schedule_coverage':'available_only'}

def parse_timetable(html,day):
 soup=BeautifulSoup(html,'html.parser');heading=soup.select_one('.rev_se span')
 if not heading or not heading.get_text(strip=True).startswith(day.isoformat()+' 예약'):raise ValueError('선택 날짜 불일치')
 blocks=soup.select('div.time')
 if len(blocks)!=6:raise ValueError('공식 테마 구획 변경')
 themes=[];names=set();missions=set()
 for block in blocks:
  tr=block.find_parent('tr');title=tr.find('p')if tr else None
  name=''.join(str(x) for x in title.find_all(string=True,recursive=False)).strip()if title else ''
  if not name or name in names:raise ValueError('테마명 누락·중복')
  names.add(name);slots=[];seen=set();mission=None;cells=block.select('li')
  if not cells:raise ValueError('시간표 셀 누락')
  for li in cells:
   if 'end' in li.get('class',[]):
    if li.get_text(' ',strip=True)!='예약완료':raise ValueError('마감 상태 문구 변경')
    continue
   a=li.find('a',href=True)
   if not a:raise ValueError('확인할 수 없는 시간표 셀')
   url=urljoin(SITE_URL,a['href']);p=urlsplit(url);q=parse_qs(p.query)
   def single(key):
    values=q.get(key,[])
    if len(values)!=1:raise ValueError('예약 링크 필드 누락·중복')
    return values[0]
   value=single('time');mid=single('mission')
   if p.netloc!='chaosesc.co.kr' or p.scheme not in ('http','https') or p.path!='/2019/bbs/write.php' or single('bo_table')!='reservation' or single('select')!=day.isoformat():raise ValueError('예약 링크 출처·날짜 불일치')
   if not mid.isdigit() or (mission is not None and mid!=mission):raise ValueError('테마 식별자 불일치')
   mission=mid
   if not re.fullmatch(r'(?:[01]\d|2\d):[0-5]\d',value) or a.get_text(' ',strip=True)!=value or value in seen:raise ValueError('명시 시각 불일치·중복')
   seen.add(value);slots.append({'time':value,'status':'available','booking_url':url})
  if mission is not None:
   if mission in missions:raise ValueError('서로 다른 테마에 같은 식별자')
   missions.add(mission)
  image=tr.select_one('.mission_content img[src]');poster=urljoin(SITE_URL,image['src'])if image else None
  themes.append({'name':name,'poster_url':poster,'slots':slots})
 return themes

def main(run_schedule=True,days=6):
 init_firestore();db=get_db();upsert_cafe(db,CAFE_ID,CAFE_META)
 today=datetime.now(ZoneInfo('Asia/Seoul')).date()
 with requests.Session()as session:
  for offset in range(days+1 if run_schedule else 1):
   day=today+timedelta(days=offset);r=session.get(RESERVE_URL,params={'bo_table':'reservation','select':day.isoformat()},timeout=20);r.raise_for_status();r.encoding=r.apparent_encoding
   parsed=parse_timetable(r.text,day);themes={}
   for theme in parsed:
    tid=get_or_create_theme(db,CAFE_ID,theme['name'],{'poster_url':theme['poster_url'],'schedule_coverage':'available_only'})
    themes[tid]={'slots':theme['slots']}
   if run_schedule:upsert_cafe_date_schedules(db,day.isoformat(),CAFE_ID,themes,datetime.now(ZoneInfo('Asia/Seoul')))
   print(f'{day}: {len(parsed)} themes / {sum(len(t["slots"])for t in parsed)} explicitly available slots')
   time.sleep(.4)
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--days',type=int,default=6);p.add_argument('--no-schedule',action='store_true');a=p.parse_args();main(not a.no_schedule,a.days)
