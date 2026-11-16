import contextlib
import copy
import io
import unittest
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from scripts import sync_reserv_public_db as reserv, sync_cubeescape_db as cube
from scripts import sync_amazed_db as amazed, sync_exodus_current_db as exodus, sync_sinbiweb_db as sinbi


class ReservPublicTests(unittest.TestCase):
    def fixture(self):
        branch = {'shop_key': 'official-key', 'base_url': 'https://official.example'}
        slots = [{'day_date': day, 'integer_to_time': '12:30', 'theme_id': 1,
                  'can_book': available, 'left_stock': 1 if available else 0}
                 for day, available in [('2026-11-16', True), ('2026-11-17', False), ('2026-12-01', True)]]
        data = {'result': 'success', 'data': {'shop': {'keycode': 'official-key', 'naver_only': False},
                'themes': [{'id': 1, 'title': '공식 테마', 'is_deleted': False, 'slots': slots}]}}
        return data, branch

    def parse(self, data, branch, hour=10):
        return reserv.parse_detail(data, branch, date(2026, 11, 16), 6,
                                   datetime(2026, 11, 16, hour, tzinfo=ZoneInfo('Asia/Seoul')))[1]

    def test_monthly_response_is_clamped_and_official_status_is_preserved(self):
        data, branch = self.fixture()
        parsed = self.parse(data, branch)[0]['dates']
        self.assertEqual(set(parsed), {'2026-11-16', '2026-11-17'})
        self.assertEqual(parsed['2026-11-16'][0]['status'], 'available')
        self.assertEqual(parsed['2026-11-17'][0]['status'], 'full')
        self.assertIn('shop=official-key', parsed['2026-11-16'][0]['booking_url'])

    def test_past_slot_is_closed_even_if_provider_can_book_is_true(self):
        data, branch = self.fixture()
        self.assertEqual(self.parse(data, branch, hour=20)[0]['dates']['2026-11-16'][0]['status'], 'closed')

    def test_wrong_store_and_naver_redirect_are_not_published(self):
        for change in ('keycode', 'naver_only'):
            data, branch = self.fixture()
            data['data']['shop'][change] = 'wrong-store' if change == 'keycode' else True
            with self.assertRaises(ValueError):
                self.parse(data, branch)

    def test_unknown_status_conflicting_stock_and_duplicate_slots_are_rejected(self):
        for change in ('unknown', 'stock', 'duplicate', 'theme'):
            data, branch = self.fixture()
            slots = data['data']['themes'][0]['slots']
            if change == 'unknown': slots[0]['can_book'] = 'true'
            elif change == 'stock': slots[0]['left_stock'] = 0
            elif change == 'theme': slots[0]['theme_id'] = 2
            else: slots.append(copy.deepcopy(slots[0]))
            with self.assertRaises(ValueError):
                self.parse(data, branch)


class CubeFixTests(unittest.TestCase):
    def test_range_time_and_span_status_preserve_start_and_midnight(self):
        html = '''<table><tbody>
        <tr><td>12:05 ~ 13:05</td><td>공식테마</td><td><span class="label label-default cursor" onclick="roomSubmit('12:05-13:05', '공식테마')">예약하기</span></td></tr>
        <tr><td>24:20 ~ 25:20</td><td>공식테마</td><td><span class="label label-success">매진</span></td></tr>
        </tbody></table>'''
        result = cube._parse_schedule(html, cube.BRANCHES[0], date(2030, 1, 1))['공식테마']
        self.assertEqual([r['time'] for r in result], ['12:05', '24:20'])
        self.assertEqual([r['status'] for r in result], ['available', 'full'])

    def test_reservation_page_initializes_office_before_ajax(self):
        opener = SimpleNamespace(open=lambda *a, **k: None)
        from unittest.mock import MagicMock
        opener.open = MagicMock()
        with patch.object(cube.urllib.request, 'build_opener', return_value=opener):
            cube._make_opener('https://official.example', 7)
        self.assertEqual(opener.open.call_args.args[0].full_url, 'https://official.example/?sd=3&sc=3_1&rbranch=7')

    def test_future_theme_is_registered_before_saving(self):
        today = date.today()
        slot = {'time': '23:59', 'status': 'full', 'booking_url': None}
        db = SimpleNamespace(collection=lambda *a: SimpleNamespace(document=lambda *a: SimpleNamespace(get=lambda: SimpleNamespace(exists=True))))
        saved = []
        def parse(_, __, day): return {'기존' if day == today else '미래 테마': [slot]}
        with contextlib.ExitStack() as stack:
            for name, value in [('get_db', db), ('_make_opener', object()), ('_fetch_schedule', 'official response'), ('load_cafe_hashes', {})]:
                stack.enter_context(patch.object(cube, name, return_value=value))
            stack.enter_context(patch.object(cube, '_parse_schedule', side_effect=parse))
            stack.enter_context(patch.object(cube, 'get_or_create_theme', side_effect=lambda db, cid, name, data: name))
            stack.enter_context(patch.object(cube, 'upsert_cafe'))
            stack.enter_context(patch.object(cube, 'save_cafe_hashes'))
            stack.enter_context(patch.object(cube.time, 'sleep'))
            stack.enter_context(patch.object(cube, 'upsert_cafe_date_schedules', side_effect=lambda db, day, cid, themes, *a, **k: saved.append(themes) or 'hash'))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            cube.sync_one_branch(cube.BRANCHES[0], True, 1)
        self.assertIn('미래 테마', saved[-1])


class AdditionalPublicSiteTests(unittest.TestCase):
    def test_amazed_date_calendar_and_disabled_state_are_checked(self):
        html = '''<div class="booked-appt-list" data-list-date="2026-11-17">
        <div class="timeslot"><button class="new-appt" data-calendar-id="19" data-date="2026-11-17" data-timeslot="1000-1140">바로 예매하기</button></div>
        <div class="timeslot"><button class="new-appt" disabled data-calendar-id="19" data-date="2026-11-17" data-timeslot="1055-1235">매진되었습니다</button></div></div>'''
        slots = amazed.parse_slots(html, '2026-11-17')
        self.assertEqual([s['status'] for s in slots], ['available', 'full'])
        for wrong in [html.replace('calendar-id="19"', 'calendar-id="20"'), html.replace('매진되었습니다', '상태 미확인')]:
            with self.assertRaises(ValueError): amazed.parse_slots(wrong, '2026-11-17')

    def test_exodus_scopes_branch_theme_date_and_status(self):
        data = {'branch': 'gangnam', 'branch_info': {'name': '엑소더스 강남1호점'},
                'themes': {'t': {'name': 'CLAIM'}}, 'days': {'2026-11-17': [
                    {'theme_id': 't', 'theme': 'CLAIM', 'time': '12:00', 'status': 'available', 'past': False},
                    {'theme_id': 't', 'theme': 'CLAIM', 'time': '13:00', 'status': 'booked', 'past': False}],
                    '2026-12-01': [{'invalid': 'out of requested range'}]}}
        themes, schedules = exodus.parse_payload(data, date(2026, 11, 17), 6)
        self.assertEqual(set(schedules), {'2026-11-17'})
        self.assertEqual([s['status'] for s in schedules['2026-11-17']['t']], ['available', 'full'])
        data['days']['2026-11-17'][0]['status'] = 'unknown'
        with self.assertRaises(ValueError): exodus.parse_payload(data, date(2026, 11, 17), 6)

    def test_doom_midnight_time_is_not_truncated_to_zero(self):
        site = next(s for s in sinbi.SITES if s['cafe_id'] == '997136500')
        html = '''<input name="rev_days" value="2026-11-17"><select><option value="1" selected>1호점</option></select>
        <div class="info_box"><div class="tit"><p class="name">공식 테마</p></div><div class="time"><ul>
        <li class="on"><a href="home.php?go=rev.make.input&amp;rev_days=2026-11-17&amp;theme_time_num=1"><span class="num">24:20</span><span class="txt">예약가능</span></a></li>
        <li><a><span class="num">23:00</span><span class="txt">예약마감</span></a></li></ul></div></div>'''
        slots = sinbi._parse_page(html, site, date(2026, 11, 17))[0]['slots']
        self.assertEqual(slots[0]['time'].hour, 24)
        self.assertEqual([s['status'] for s in slots], ['available', 'full'])
        with self.assertRaises(ValueError): sinbi._parse_page(html, site, date(2026, 11, 18))


if __name__ == '__main__':
    unittest.main()
