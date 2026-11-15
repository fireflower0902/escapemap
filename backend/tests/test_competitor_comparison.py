import unittest
from scripts.compare_competitors import compare, normalize, cell

class ComparisonTests(unittest.TestCase):
 def setUp(self):
  self.ours={'cafes':[{'id':'a','name':'단편선','branch_name':'강남점'},{'id':'b','name':'단편선','branch_name':'홍대점'}], 'themes':[{'id':'ta','cafe_id':'a','name':'기억 1'},{'id':'tb','cafe_id':'b','name':'기억 2'}]}
 def run_comparison(self,cafe,theme):
  return compare({'source':'test','cafes':[{'name':cafe}],'themes':[{'cafe_name':cafe,'name':theme}]},self.ours)
 def test_verified_alias_does_not_duplicate_identity(self):
  self.ours['cafes'][0]['aliases']=['단편선 강남점','단편선 강남','공식 확인 별칭']
  self.assertEqual(self.run_comparison('공식 확인 별칭','기억 1')['themes'][0]['status'],'matched')
 def test_branch_suffix_alias(self):
  r=self.run_comparison('단편선 강남','기억 1')
  self.assertEqual(r['themes'][0]['status'],'matched')
 def test_theme_only_matches_inside_same_branch(self):
  r=self.run_comparison('단편선 강남점','기억 2')
  self.assertNotEqual(r['themes'][0]['status'],'matched')
 def test_ambiguous_cafe_not_automatically_linked(self):
  self.ours['cafes'].append({'id':'c','name':'단편선','branch_name':'강남점'})
  self.assertEqual(self.run_comparison('단편선 강남점','기억 1')['themes'][0]['status'],'cafe_missing')
 def test_fuzzy_candidate_not_match(self):
  self.assertEqual(self.run_comparison('단편선 강남지점','기억 1')['cafes'][0]['status'],'candidate')
 def test_numbers_preserved_and_markdown_escaped(self):
  self.assertNotEqual(normalize('기억 1'),normalize('기억 2'))
  self.assertEqual(cell('a|b\nc'),'a\\|b c')

if __name__=='__main__':unittest.main()
