"""판타스트릭 개편 공개 예약 API. 공식 slots/open/blocked 응답만 사용."""
import sys,time
from pathlib import Path
from datetime import date,datetime,timedelta
import requests
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.config import settings
from app.firestore_db import init_firestore,get_db,get_or_create_theme,upsert_cafe_date_schedules
BASE_URL='https://fantastrick.co.kr'
REQUEST_DELAY=.2
THEMES = [{'cafe_id': '1421844037',
  'name': '태초의 신부',
  'calendar_id': 17,
  'slug': 'firstfoundbride',
  'poster_url': 'http://fantastrick.co.kr/wp-content/uploads/2018/10/poster-scaled.jpg'},
 {'cafe_id': '192767471',
  'name': '사자의 서',
  'calendar_id': 23,
  'slug': 'bookofduat',
  'poster_url': None},
 {'cafe_id': '2020129484',
  'name': 'LOCKDOWN CITY',
  'calendar_id': 24,
  'slug': 'ldc',
  'poster_url': None},
 {'cafe_id': '2020129484', 'name': '시간의 영속성', 'slug': 'time'}]

def parse_slots(data):
    if not isinstance(data.get('slots'),list) or not isinstance(data.get('open'),list):raise ValueError('공식 시간표 응답 형식 변경')
    slots=data['slots'];opened=set(data['open']);blocked=set(data.get('blocked',[]))|set(data.get('taken',[]))
    if opened-set(slots):raise ValueError('공식 오픈 시간표 불일치')
    result=[]
    for value in slots:
        if data.get('dayClosed'):status='closed'
        elif value in blocked:status='full'
        elif value in opened:status='available'
        else:status='closed'
        result.append({'time':value,'status':status,'booking_url':BASE_URL+'/reserve' if status=='available' else None})
    return result

def main(run_schedule=True,days=14):
    init_firestore(settings.firebase_credentials_path);db=get_db();today=date.today();session=requests.Session()
    for offset in range(days+1 if run_schedule else 1):
        day=today+timedelta(days=offset);cafes={}
        for theme in THEMES:
            r=session.get(BASE_URL+'/api/slots',params={'theme':theme['slug'],'date':day.isoformat()},timeout=25);r.raise_for_status();slots=parse_slots(r.json())
            tid=get_or_create_theme(db,theme['cafe_id'],theme['name'],{'is_active':True})
            if slots:cafes.setdefault(theme['cafe_id'],{})[tid]={'slots':slots}
            time.sleep(REQUEST_DELAY)
        if run_schedule:
            for cid,data in cafes.items():upsert_cafe_date_schedules(db,day.isoformat(),cid,data,datetime.now())
        print(day,len(THEMES),'themes',sum(len(t['slots']) for c in cafes.values() for t in c.values()),'slots',flush=True)
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--days',type=int,default=14);p.add_argument('--no-schedule',action='store_true');a=p.parse_args();main(not a.no_schedule,a.days)
