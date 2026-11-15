import unittest
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import URLError
from datetime import date
from app.crawl_availability import reservation_status,require_reservation_feed
from scripts.crawler_selection import select_cafes
from scripts import sync_oasisescape_db as oasis

class PriorityReviewTests(unittest.TestCase):
 def test_missing_or_non_boolean_reservation_is_never_available(self):
  for value in [None,0,1,'false','true',{},[]]:
   with self.assertRaises(ValueError):reservation_status(value)
  self.assertEqual(reservation_status(False),'available')
 def test_missing_reserved_list_is_not_an_empty_reserved_list(self):
  with self.assertRaises(ValueError):require_reservation_feed({'theme_data':[{}]})
  with self.assertRaises(ValueError):require_reservation_feed({'theme_data':[{}],'reserv_data':[{}]})
  self.assertEqual(require_reservation_feed({'theme_data':[],'reserv_data':[]}),([],[]))
 def test_failed_closed_schedule_query_does_not_return_no_closed_slots(self):
  with patch.object(oasis.urllib.request,'urlopen',side_effect=URLError('temporary failure')):
   with self.assertRaises(RuntimeError):oasis.fetch_closed_schedule_ids(1,date(2030,1,1))
 def test_select_dictionary_branch_keeps_only_requested_branch(self):
  m=SimpleNamespace(BRANCH_MAP={1:{'cafe_id':'a'},2:{'cafe_id':'b'}},THEME_MAP={1:[1],2:[2]})
  select_cafes(m,['b']);self.assertEqual(list(m.BRANCH_MAP),[2]);self.assertEqual(m.THEME_MAP[2],[2])
 def test_single_cafe_theme_name_mapping_is_preserved(self):
  m=SimpleNamespace(CAFE_ID='a',THEMES={'A':'정상 테마'})
  select_cafes(m,['a']);self.assertEqual(m.THEMES,{'A':'정상 테마'})
 def test_brand_shop_map_is_selected_without_changing_original(self):
  source={'shop_map':{'one':'a','two':'b'}};m=SimpleNamespace(BRANDS=[source]);select_cafes(m,['b'])
  self.assertEqual(m.BRANDS[0]['shop_map'],{'two':'b'});self.assertEqual(len(source['shop_map']),2)
 def test_unknown_cafe_is_rejected(self):
  with self.assertRaises(ValueError):select_cafes(SimpleNamespace(CAFE_ID='a'),['unknown'])
if __name__=='__main__':unittest.main()


class ServiceTimeTests(unittest.TestCase):
    def test_late_service_time_keeps_next_day(self):
        from datetime import date, datetime
        from app.crawl_availability import service_slot_datetime
        self.assertEqual(service_slot_datetime(date(2026,11,15), "24:30"), datetime(2026,11,16,0,30))
        self.assertEqual(service_slot_datetime(date(2026,11,15), "23:30"), datetime(2026,11,15,23,30))
        with self.assertRaises(ValueError): service_slot_datetime(date(2026,11,15), "24:60")
