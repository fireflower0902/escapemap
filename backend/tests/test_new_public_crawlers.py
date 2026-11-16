import unittest
from datetime import date
from scripts import sync_ccescapezone_db as zone, sync_sinbiweb_db as sinbi


class NewPublicCrawlerTests(unittest.TestCase):
    def zone_html(self, day='2026-11-16', extra=''):
        return f'''<script>$("#datepicker").datepicker("setDate", "{day}");</script>
        <div style="font-size:24px">제이콥</div><div>
        <span class="spurs_btn1" style="text-decoration:line-through">24:00</span>
        <span class="spurs_btn1" onclick="location.href='/kr/booking.php?no=1&amp;date={day}&amp;reserve_time=24:05'">24:05</span>{extra}</div>'''

    def test_business_date_and_midnight_hours_are_preserved(self):
        parsed = zone.parse_page(self.zone_html(), '2026-11-16')
        self.assertEqual(len(parsed), 1)
        self.assertEqual([s['time'] for s in parsed[0]['slots']], ['24:00', '24:05'])
        self.assertEqual([s['status'] for s in parsed[0]['slots']], ['full', 'available'])
        self.assertIn('date=2026-11-16', parsed[0]['slots'][1]['booking_url'])

    def test_wrong_response_date_and_unknown_slot_status_are_rejected(self):
        with self.assertRaises(ValueError):
            zone.parse_page(self.zone_html(), '2026-11-17')
        with self.assertRaises(ValueError):
            zone.parse_page(self.zone_html(extra='<span class="spurs_btn1">15:00</span>'), '2026-11-16')
        with self.assertRaises(ValueError):
            zone.parse_page(self.zone_html().replace('reserve_time=24:05', 'reserve_time=23:05'), '2026-11-16')

    def test_hidden_possible_label_does_not_make_closed_doors_slot_available(self):
        site = next(s for s in sinbi.SITES if s['cafe_id'] == '302959300')
        html = '''<div class="theme_box"><h3>테마</h3><ul class="reserve_Time">
        <li><a class="end" href="javascript:chkBooking('12:00','theme');"><span class="time">12:00</span><span class="possible">예약가능</span><span class="impossible">마감</span></a></li>
        <li><a href="javascript:chkBooking('13:00','theme');"><span class="time">13:00</span><span class="possible">예약가능</span><span class="impossible">마감</span></a></li>
        </ul></div>'''
        slots = sinbi._parse_page(html, site, date(2026, 11, 16))[0]['slots']
        self.assertEqual([s['status'] for s in slots], ['full', 'available'])
        self.assertIsNone(slots[0]['booking_url'])
        self.assertTrue(slots[1]['booking_url'].startswith('https://www.thedoorsescape.com/reserve/'))


if __name__ == '__main__':
    unittest.main()
