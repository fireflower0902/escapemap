"""실제 사이트 점검 중 발견된 잘못된 예약 상태·테마 혼합·심야 오류 재현."""
import contextlib
from datetime import date, datetime
import io
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from app.crawl_time import business_slot_datetime
from scripts.check_crawlers import MemoryStore
from scripts import sync_escapecity_db as city
from scripts import sync_thecode_db as thecode
from scripts import sync_zescape_db as zescape
from scripts import sync_xphobia_db as xphobia


class CrawlerRegressionTests(unittest.TestCase):
    def test_hidden_theme_schedules_never_merge_into_first_theme(self):
        html = '''
<a href="javascript:CQview(document.all.CQ1)"><li class="thema1">좀비바이러스</li></a>
<li id="CQ1" style="display:none"><ul class="list">
<a href="sub03_2.html?room_time=12:00&amp;room_code=A"><li class="timeOn">☆ 12:00</li></a>
</ul></li>
<a href="javascript:CQview(document.all.CQ2)" class="active"><li class="thema1">마법학교</li></a>
<div><ul class="list">
<a href="sub03_2.html?room_time=12:10&amp;room_code=B"><li class="timeOn">☆ 12:10</li></a>
<li class="timeOff">★ 13:20</li></ul></div>
'''
        a = city._parse_page(html, 'S1', 'A', date(2026, 11, 15))
        b = city._parse_page(html, 'S1', 'B', date(2026, 11, 15))
        self.assertEqual(a['name'], '좀비바이러스')
        self.assertEqual([s['time'] for s in a['slots']], ['12:00'])
        self.assertEqual(b['name'], '마법학교')
        self.assertEqual([s['status'] for s in b['slots']], ['available', 'full'])
        self.assertIn('room_code=B', b['slots'][0]['booking_url'])
        self.assertNotIn('&amp;', b['slots'][0]['booking_url'])
        self.assertIsNone(city._parse_page(html, 'S1', 'C', date(2026, 11, 15)))

    def test_midnight_is_next_civil_day_but_original_business_time_is_preserved(self):
        self.assertEqual(business_slot_datetime(date(2026, 11, 14), 24, 30),
                         datetime(2026, 11, 15, 0, 30))
        for hour, minute in ((30, 0), (-1, 0), (12, 60)):
            with self.assertRaises(ValueError):
                business_slot_datetime(date(2026, 11, 14), hour, minute)
        slot = {'time': '24:10', 'status': 'available', 'booking_url': 'https://example.com/booking'}
        for module in (thecode, zescape):
            with self.subTest(module=module.__name__), contextlib.ExitStack() as stack:
                store = MemoryStore()
                stack.enter_context(patch.object(module, 'init_firestore'))
                stack.enter_context(patch.object(module, 'get_db', return_value=store))
                stack.enter_context(patch.object(module, '_fetch', return_value=''))
                slots = [slot] if module is thecode else {'13': [slot]}
                stack.enter_context(patch.object(module, '_parse_slots', return_value=slots))
                stack.enter_context(patch.object(module, 'REQUEST_DELAY', 0))
                stack.enter_context(patch('app.firestore_db._SKIP_META', False))
                stack.enter_context(patch('app.firestore_db._CRAWL_SEOUL_ONLY', False))
                stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                module.main(days=0)
                cafes = store.data['schedules'][str(date.today())]['cafes']
                stored = [s for cafe in cafes.values() for theme in cafe['themes'].values()
                          for s in theme['slots']]
                self.assertTrue(stored)
                self.assertEqual(stored[0]['time'], '24:10')
                self.assertEqual(stored[0]['booking_url'], slot['booking_url'])

    def test_http_failure_never_means_available(self):
        opener = Mock()
        opener.open.side_effect = HTTPError('https://example.com', 503, 'Unavailable', {}, None)
        with self.assertRaises(RuntimeError):
            xphobia._check_slot(opener, '홍대점', '테마', date(2026, 11, 15), '14:00')
        with patch.object(xphobia, '_post', return_value={'error': 'failed'}):
            with self.assertRaises(ValueError):
                xphobia._check_slot(opener, '홍대점', '테마', date(2026, 11, 15), '14:00')
        with patch.object(xphobia, '_post', return_value=[]):
            self.assertTrue(xphobia._check_slot(opener, '홍대점', '테마', date(2026, 11, 15), '14:00'))


if __name__ == '__main__':
    unittest.main()
