import unittest
from datetime import date
from scripts.sync_chaosesc_db import parse_timetable
DAY=date(2026,11,28)
def fixture(cell):
 return '<div class="rev_se"><span>2026-11-28 예약</span></div>'+''.join(f'<table><tr><td><div class="mission_content"></div></td><td><p>테마{i}<span>난이도</span></p><div class="time"><ul>'+cell.format(i=i)+'</ul></div></td></tr></table>'for i in range(1,7))
LINK='<li><a href="http://chaosesc.co.kr/2019/bbs/write.php?bo_table=reservation&amp;select=2026-11-28&amp;mission={i}&amp;time=11:20">11:20</a></li>'
CLOSED='<li class="end">예약완료</li>'
class ChaosTests(unittest.TestCase):
 def test_explicit_links_only(self):
  rows=parse_timetable(fixture(CLOSED+LINK),DAY);self.assertEqual(len(rows),6)
  for row in rows:self.assertEqual([(s['time'],s['status'])for s in row['slots']],[('11:20','available')])
 def test_all_closed_keeps_themes_without_invented_times(self):
  rows=parse_timetable(fixture(CLOSED*10),DAY);self.assertEqual(len(rows),6);self.assertTrue(all(not r['slots']for r in rows))
 def test_wrong_date_wrong_origin_and_ambiguous_cells_fail(self):
  for html in [fixture(LINK).replace('2026-11-28 예약','2026-11-27 예약'),fixture(LINK).replace('select=2026-11-28','select=2026-11-27'),fixture(LINK).replace('chaosesc.co.kr','example.com'),fixture(LINK).replace('>11:20<','>12:20<'),fixture('<li>시간 미확인</li>'),fixture(LINK+LINK)]:
   with self.subTest(html=html[:90]),self.assertRaises(ValueError):parse_timetable(html,DAY)
if __name__=='__main__':unittest.main()
