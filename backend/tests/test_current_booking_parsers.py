import unittest
from datetime import date,datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch
from app.sinbi_reservation import parse_theme_list,parse_time_list
from scripts.sync_secretgarden_db import parse_schedule
from scripts.sync_xcape_current_db import parse_slots as xcape_slots
from scripts.sync_fantastrick_db import parse_slots as fant_slots
from scripts.sync_codek_db import _parse_page as codek_page,booking_url
from scripts.sync_movieescape_cokr_db import _parse_current_page
from scripts.sync_orangetb_db import _parse_themes
from scripts import sync_rabbithole_db as rabbit
from scripts.sync_public_extra_db import parse_plus_slots,parse_exploria

class ParserTests(unittest.TestCase):
 def test_plus_unopened_date_does_not_become_available(self):
  data={'themeId':30002,'date':'2030-01-01','notYetOpen':True,'slots':[{'startTime':'12:00:00','available':True}]}
  self.assertEqual(parse_plus_slots(data,date(2030,1,1))[0]['status'],'closed')
  with self.assertRaises(ValueError):parse_plus_slots(data,date(2030,1,2))
 def test_exploria_does_not_confuse_closed_and_bookable(self):
  html='<input type="date" value="2030-01-01"><article class="ex-book-card"><h3>테마</h3><ul class="ex-slots"><li><span class="ex-slot"><b>12:00</b><small>마감</small></span></li><li><a class="ex-slot" href="/theme/2030-01-01/test/13:00/"><b>13:00</b><small>예약</small></a></li></ul></article>'
  self.assertEqual([x['status'] for x in parse_exploria(html,date(2030,1,1))[0]['slots']],['full','available'])
 def test_current_sinbi_nested_title_and_disabled_link(self):
  themes=parse_theme_list('<a href="javascript:fun_theme_select(\'1\',\'0\')"><p class="choice-themes__name">테마 | 1</p><p class="choice-themes__playtime">75분</p></a>')
  self.assertEqual(themes['1'],{'name':'테마 | 1','duration_min':75})
  slots=parse_time_list('<a href="javascript:fun_theme_time_select(1)">12:00</a><a class="disable" href="javascript:fun_theme_time_select(2)">13:00</a>')
  self.assertEqual([s['status'] for s in slots],['available','full'])
 def test_unknown_sinbi_link_not_available(self):
  self.assertEqual(parse_time_list('<a>12:00</a>'),[])
 def test_secretgarden_hidden_labels_do_not_override_end(self):
  day=date(2030,1,1);html='''<input id="datepicker_bbs" value="2030-01-01"><div class="time_Area"><h3 class="h3_theme">테마</h3><ul class="reserve_Time"><li><a class="end"><span class="time">12:00</span><span class="possible">예약가능</span><span class="impossible">예약마감</span></a></li><li><a onclick="SendVar('1','2030-01-01','24:15');"><span class="time">24:15</span></a></li></ul></div>'''
  slots=parse_schedule(html,3,day)[0]['slots'];self.assertEqual(slots[0]['status'],'full');self.assertEqual(slots[1]['time'],'24:15');self.assertEqual(slots[1]['status'],'available')
 def test_secretgarden_wrong_date_fails(self):
  with self.assertRaises(ValueError):parse_schedule('<input id="datepicker_bbs" value="2030-01-02">',3,date(2030,1,1))
 def xcape(self,overrides=None,settings=None):
  theme={'id':'1','play_time':60,'admin_config':{'hours':{'firstEntry':'12:00','lastEntry':'14:00','setupMin':0}}}
  return xcape_slots(theme,settings or {},overrides or [],date(2030,1,1),set(),datetime(2029,1,1,tzinfo=ZoneInfo('Asia/Seoul')))
 def test_xcape_overrides_and_reserved_open_room_not_exclusive(self):
  rows=self.xcape([{'theme_id':'1','slot_time':'12:00:00','status':'blocked'},{'theme_id':'1','slot_time':'13:00:00','status':'reserved','open_room':True}])
  self.assertEqual([x['status'] for x in rows],['full','full','available'])
 def test_xcape_closed_day_not_fabricated_available(self):
  rows=self.xcape(settings={'exceptions':[{'date':'2030-01-01','kind':'closed'}]})
  self.assertTrue(all(x['status']=='closed' for x in rows))
 def test_xcape_unknown_status_fails(self):
  with self.assertRaises(ValueError):self.xcape([{'theme_id':'1','slot_time':'12:00:00','status':'unknown'}])
 def test_fantastrick_blocked_wins_and_missing_response_fails(self):
  rows=fant_slots({'slots':['12:00','13:00'],'open':['12:00','13:00'],'blocked':['13:00']})
  self.assertEqual([x['status'] for x in rows],['available','full'])
  with self.assertRaises(ValueError):fant_slots({})
 def test_codek_utf8_and_separate_cq_blocks(self):
  html='''<a href="javascript:CQview(document.all.CQ1)"><li class="thema2">첫 테마</li></a><li id="CQ1"><li class="timeOff">★ 12:00</li></li><a href="javascript:CQview(document.all.CQ2)"><li class="thema2">둘째 테마</li></a><li id="CQ2"><a href="code_sub04_2.html?jijem_code=S2"><li class="timeOn">13:00</li></a></li>'''
  result=codek_page(html.encode(),date(2030,1,1));self.assertEqual([x['time'] for x in result['첫 테마']],['12:00']);self.assertEqual(result['둘째 테마'][0]['status'],'available');self.assertIn('R_JIJEM=S2',booking_url(date(2030,1,1),'S2'))
 def test_orange_button_semicolon_and_attribute_spacing(self):
  self.assertEqual(_parse_themes('<button onclick = "setTheme(23); return false;">돈마니</button>'),[{'t_id':23,'name':'돈마니'}])
 def test_tonybilly_refreshes_changed_ids(self):
  fixture='<select name="theme"><option value="">전체</option><option value="99">두껍아 두껍아 헌집줄게 새집다오</option><option value="100">신규</option></select>'
  with patch.object(rabbit,'_fetch_page',return_value=fixture),patch.dict(rabbit.THEME_MAP,{},clear=False):
   rabbit.refresh_theme_ids(1);self.assertEqual([x['theme_id'] for x in rabbit.THEME_MAP[1]],[99,100])
 def test_movie_renamed_closed_label(self):
  html='''<input id="me-date" value="2030-01-01"><div class="me-show-main"><h3>테마</h3><div class="me-slots"><span class="me-slot" data-time="12:00"><small>마감</small></span><a class="me-slot" data-time="13:00" href="/theme/2030-01-01/test/13:00/"><small>예약 가능</small></a></div></div>'''
  rows=_parse_current_page(html,date(2030,1,1))['테마'];self.assertEqual([x['status'] for x in rows],['full','available'])

class EscThemePlaceholderTests(unittest.TestCase):
 def test_empty_dropdown_option_is_not_a_theme(self):
  from scripts.sync_escbangtalul_db import _parse_themes
  html='<select name="select_room"><option value="0"> </option><option value="1">&nbsp;</option><option value="2">수상한 병원</option></select>'
  self.assertEqual(_parse_themes(html),{'2':'수상한 병원'})

if __name__=='__main__':unittest.main()
