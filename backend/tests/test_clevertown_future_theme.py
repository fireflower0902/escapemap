import contextlib,io,unittest
from datetime import date,time
from unittest.mock import patch
from scripts import sync_clevertown_db as clever
class FutureThemeTests(unittest.TestCase):
 def test_future_limited_theme_is_registered_before_saving_slots(self):
  today=date.today();saved=[];slot={'time':time(23,59),'status':'available','booking_url':'https://example.com/reserve'}
  def parsed(_,day):return [{'theme_name':'기존','slots':[slot]}] if day==today else [{'theme_name':'기념 축제(14시 타임 전용)','slots':[slot]}]
  def save(_,day,cid,themes,*args,**kwargs):saved.append((day,themes));return 'hash'
  with patch.object(clever,'get_db',return_value=object()),patch.object(clever,'_fetch_reserve_page',return_value='official page'),patch.object(clever,'_parse_reserve_page',side_effect=parsed),patch.object(clever,'sync_themes',side_effect=lambda rows:{r['theme_name']:r['theme_name'] for r in rows}),patch.object(clever,'load_cafe_hashes',return_value={}),patch.object(clever,'save_cafe_hashes'),patch.object(clever,'upsert_cafe_date_schedules',side_effect=save),patch.object(clever.time,'sleep'),contextlib.redirect_stdout(io.StringIO()):
   clever.sync_schedules(object(),{'기존':'기존'},days=1)
  self.assertIn('기념 축제(14시 타임 전용)',saved[-1][1])
