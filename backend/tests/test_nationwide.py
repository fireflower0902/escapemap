"""전국 전환의 회귀 검증. 외부 네트워크와 실제 DB를 사용하지 않습니다."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from app.areas import QUERY_AREAS, address_to_area, area_matches, resolve_cafe_area
from app.api.v1.cafes import _get_cafes_sync, _validate_area
from app.firestore_db import upsert_cafe
from scripts.check_crawlers import MemoryStore, validate_store

ROOT = Path(__file__).resolve().parents[2]


class NationwideTests(unittest.TestCase):
    def test_seoul_legacy_and_national_addresses(self):
        cases = [
            ('etc', '부산광역시 부산진구 중앙대로', 'busan'),
            ('etc', '전북특별자치도 전주시 완산구', 'jeonbuk'),
            ('etc', '강원특별자치도 춘천시', 'gangwon'),
            ('etc', '충청북도 청주시', 'chungbuk'),
            ('etc', '서울특별시 성동구 연무장길', 'seongsu'),
            ('etc', '서울 노원구 동일로', 'seoul_other'),
            ('daehakro', '서울 종로구 대학로', 'daehakro'),
            ('cheonan', '충남 천안시 서북구', 'cheonan'),
            ('gwangju', '경기도 광주시 경안동', 'gyeonggi'),
            ('unknown', '', 'etc'),
            ('hongdae', '서울 서대문구 연세로 1', 'sinchon'),
            ('gangnam', '서울 광진구 동일로 1', 'konkuk'),
            ('daehakro', '서울 성북구 보문로 1', 'seoul_other'),
            ('cheonan', '충남 당진시 중앙로 1', 'chungnam'),
        ]
        for area, address, expected in cases:
            with self.subTest(address=address):
                self.assertEqual(resolve_cafe_area(area, address), expected)
        self.assertEqual(address_to_area(' 제주특별자치도 제주시'), 'jeju')
        self.assertTrue(area_matches('chungnam', 'cheonan'))
        self.assertTrue(area_matches('seoul', 'seoul_other'))
        self.assertFalse(area_matches('busan', 'gangnam'))

    def test_old_false_support_flag_does_not_hide_national_cafes(self):
        db = MemoryStore()
        db.data = {'cafes': {
            'busan': {'name': '부산 카페', 'area': 'etc', 'address': '부산 부산진구',
                      'is_active': True, 'supported_area': False},
            'seoul': {'name': '건대 카페', 'area': 'konkuk', 'address': '서울 광진구',
                      'is_active': True, 'supported_area': True},
            'closed': {'name': '폐업 카페', 'area': 'busan', 'is_active': False},
        }}
        self.assertEqual([c['id'] for c in _get_cafes_sync(db, 'busan')], ['busan'])
        self.assertEqual([c['id'] for c in _get_cafes_sync(db, 'konkuk')], ['seoul'])
        self.assertEqual(len(_get_cafes_sync(db, None)), 2)

    def test_invalid_region_rejected_and_blank_means_nationwide(self):
        self.assertEqual(_validate_area(None), 'all')
        self.assertEqual(_validate_area(' BUSAN '), 'busan')
        self.assertEqual(_validate_area('  '), 'all')
        with self.assertRaises(HTTPException) as error:
            _validate_area('not-a-region')
        self.assertEqual(error.exception.status_code, 400)

    def test_metadata_upsert_restores_national_region(self):
        db = MemoryStore()
        with patch('app.firestore_db._SKIP_META', False), patch('app.firestore_db._CRAWL_SEOUL_ONLY', False):
            upsert_cafe(db, 'test-busan', {'area': 'etc', 'address': '부산 부산진구'})
        cafe = db.collection('cafes').document('test-busan').get().to_dict()
        self.assertEqual(cafe['area'], 'busan')
        self.assertTrue(cafe['supported_area'])

    def test_frontend_backend_region_contract(self):
        # TypeScript를 실제 실행해 두 API의 지역 해석이 일치하는지 검사.
        script = '''
const fs = require('fs'), ts = require('./node_modules/typescript');
const source = fs.readFileSync('./lib/areas.ts', 'utf8');
const compiled = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.CommonJS}}).outputText;
const mod = {exports: {}};
new Function('exports', 'module', compiled)(mod.exports, mod);
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify({codes: mod.exports.AREA_VALUES,
 results: input.map(x => mod.exports.resolveCafeArea(x[0], x[1]))}));
'''
        regions = [
            ('etc', prefix + ' 테스트주소')
            for prefix in ('부산', '대구', '인천', '광주', '대전', '울산', '세종', '경기',
                           '강원특별자치도', '충청북도', '충청남도', '전북특별자치도',
                           '전라남도', '경상북도', '경상남도', '제주특별자치도')
        ] + [('etc', '서울특별시 ' + district + ' 테스트주소')
             for district in ('강남구', '광진구', '서초구', '성동구', '노원구')]
        regions += [('hongdae', '서울 서대문구 연세로 1'), ('gangnam', '서울 광진구 동일로 1'), ('cheonan', '충남 당진시 중앙로 1')]
        regions += [('daehakro', '서울 종로구'), ('cheonan', '충남 천안시'), ('unknown', '')]
        output = subprocess.check_output(['node', '-e', script], cwd=ROOT / 'frontend',
                                         input=json.dumps(regions).encode())
        data = json.loads(output)
        self.assertEqual(set(data['codes']), QUERY_AREAS)
        self.assertEqual(data['results'], [resolve_cafe_area(*case) for case in regions])

    def test_crawl_flags_are_loaded_from_dotenv(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, '.env').write_text('SKIP_META_WRITES=true\nCRAWL_SEOUL_ONLY=false\n')
            env = __import__('os').environ.copy()
            env.pop('SKIP_META_WRITES', None)
            env.pop('CRAWL_SEOUL_ONLY', None)
            env['PYTHONPATH'] = str(ROOT / 'backend')
            output = subprocess.check_output([
                sys.executable, '-c',
                'from app.firestore_db import _SKIP_META, _CRAWL_SEOUL_ONLY; '
                'print(_SKIP_META, _CRAWL_SEOUL_ONLY)',
            ], cwd=directory, env=env)
            self.assertEqual(output.strip(), b'True False')

    def test_checker_detects_invalid_or_duplicate_slots(self):
        db = MemoryStore()
        db.data = {'themes': {'t': {'name': '테스트'}}, 'schedules': {
            '2026-11-14': {'cafes': {'c': {'themes': {'t': {'slots': [
                {'time': '14:00', 'status': 'available', 'booking_url': None},
                {'time': '14:00', 'status': 'full'},
                {'time': '99:00', 'status': 'unknown'},
            ]}}}}}
        }}
        result = validate_store(db)
        self.assertEqual(len(result['issues']), 4)


if __name__ == '__main__':
    unittest.main()
