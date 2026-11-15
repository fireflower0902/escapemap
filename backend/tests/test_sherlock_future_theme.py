import contextlib,io,unittest
from datetime import date,time
from types import SimpleNamespace
from unittest.mock import patch
from scripts import sync_sherlock_db as sherlock
class FutureThemeTests(unittest.TestCase):
 def test_theme_closed_today_but_available_tomorrow_is_saved(self):
  saved=[];today=date.today();slot={'time':time(23,59),'status':'available','booking_url':'https://example.com/reserve'}
  document=SimpleNamespace(get=lambda:SimpleNamespace(exists=True))
  db=SimpleNamespace(collection=lambda _:SimpleNamespace(document=lambda _:document))
  def parse(_,day):return {'현재 테마':[slot]} if day==today else {'현재 테마':[slot],'[프리미엄]시간의 회랑':[slot]}
  def save(_,day,cid,themes,*args,**kwargs):saved.append((day,themes));return 'hash'
  branch={'cafe_id':'test','cafe_name':'셜록홈즈','branch_name':'테스트','address':'부산','area':'busan','sido':15,'bno':95}
  with patch.object(sherlock,'get_db',return_value=db),patch.object(sherlock,'upsert_cafe'),patch.object(sherlock,'_fetch_schedule',return_value='official page'),patch.object(sherlock,'_parse_schedule',side_effect=parse),patch.object(sherlock,'get_or_create_theme',side_effect=lambda _,cid,name,meta:name),patch.object(sherlock,'load_cafe_hashes',return_value={}),patch.object(sherlock,'upsert_cafe_date_schedules',side_effect=save),patch.object(sherlock,'save_cafe_hashes'),patch.object(sherlock.time,'sleep'),contextlib.redirect_stdout(io.StringIO()):
   sherlock.sync_one_branch(branch,True,1)
  self.assertEqual(len(saved),2)
  self.assertIn('[프리미엄]시간의 회랑',saved[1][1])
  self.assertEqual(saved[1][1]['[프리미엄]시간의 회랑']['slots'][0]['status'],'available')
