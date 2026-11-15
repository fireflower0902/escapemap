"""기본정보 표시와 주소 기반 정정에서 잘못된 지점·테마 이름이 섞이지 않는지 검사."""
import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from scripts.crawler_catalog import catalog_entry
from scripts.repair_cafe_metadata import plan

class CafeMetadataTests(unittest.TestCase):
    def test_theme_name_never_becomes_cafe_name(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'sync_example_db.py'
            p.write_text("THEMES=[{'cafe_id':'1','name':'테마 이름'}]")
            with patch('scripts.crawler_catalog.load_cafe_directory',return_value={}):result=catalog_entry(p)
            self.assertNotIn('name',result['cafes'][0])
            with patch('scripts.crawler_catalog.load_cafe_directory',return_value={'1':{'id':'1','name':'실제 카페','address':'서울 서초구 강남대로 1','area':'gangnam'}}):result=catalog_entry(p)
            self.assertEqual(result['cafes'][0]['name'],'실제 카페')
            self.assertEqual(result['cafes'][0]['area'],'gangnam')
    def test_metadata_plan_updates_only_region_for_existing_unrelated_cafe(self):
        result=plan([{'id':'existing','name':'기존 이름','address':'서울 서대문구 명물길 1','area':'hongdae'}])
        existing=next(r for r in result if r['id']=='existing')
        self.assertEqual(existing['after'],{'area':'sinchon'})
        verified=[r for r in result if r.get('source')]
        self.assertEqual(len(verified),3)
        self.assertTrue(all(r['after']['area']=='sinchon' for r in verified))
        self.assertTrue(all('schedules' not in r['after'] for r in result))
