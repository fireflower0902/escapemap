import unittest
from scripts.verify_catalog_additions import known_cafe

class CatalogAdditionTests(unittest.TestCase):
 def test_branch_suffix_does_not_duplicate_existing(self):
  ours=[{'id':'1','name':'셜록홈즈','branch_name':'부산아트몰링점'}]
  self.assertEqual(known_cafe({'name':'셜록홈즈','branch_name':'부산 아트몰링'},ours)['id'],'1')
 def test_separate_branches_never_merge(self):
  self.assertIsNone(known_cafe({'name':'셜록홈즈','branch_name':'수원역2호점'},[{'id':'1','name':'셜록홈즈','branch_name':'수원역점'}]))
 def test_brand_not_erased(self):
  self.assertIsNone(known_cafe({'name':'상상락원','branch_name':'잠실점'},[{'id':'1','name':'셜록홈즈','branch_name':'잠실점'}]))
