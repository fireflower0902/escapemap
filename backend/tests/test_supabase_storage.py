import unittest,json
from scripts.migrate_to_supabase import ROOT
from app.supabase_storage import normalize_slots
from scripts.migrate_to_supabase import prepare

class SupabaseStorageTests(unittest.TestCase):
    def test_service_midnight_preserved(self):
        rows=normalize_slots('c','2026-11-15',{'t':{'slots':[{'time':'24:30','status':'full'}]}})
        self.assertEqual(rows[0][3],1470)
        self.assertEqual(str(rows[0][2]),'2026-11-15')
    def test_unknown_or_ambiguous_availability_rejected(self):
        for slot in [{'time':'10:00'},{'time':'10:00','status':'available'}, {'time':'30:00','status':'full'},{'time':'10:60','status':'full'}]:
            with self.assertRaises(ValueError):normalize_slots('c','2026-11-15',{'t':{'slots':[slot]}})
    def test_duplicate_slots_rejected(self):
        slot={'time':'10:00','status':'full'}
        with self.assertRaises(ValueError):normalize_slots('c','2026-11-15',{'t':{'slots':[slot,slot]}})
    def test_export_ids_and_corrected_addresses_preserved(self):
        cafes,themes,_=prepare();ids={c['id'] for c in cafes}
        exported=json.loads((ROOT/'reports/competitors/ours.json').read_text())
        self.assertEqual({t['id'] for t in themes},{t['id'] for t in exported['themes']})
        self.assertTrue({c['id'] for c in exported['cafes']} <= ids)
        self.assertTrue(all(t['cafe_id'] in ids for t in themes))
        self.assertEqual(next(c for c in cafes if c['id']=='27329834')['area'],'sinchon')

class PostgresApiContractTests(unittest.TestCase):
    def test_schedule_region_filter_and_text_theme_ids(self):
        from app.api.v1.schedules import _postgres_slots
        from scripts.check_crawlers import MemoryStore
        db=MemoryStore();db.data={'cafes':{'c':{'name':'부산','is_active':True,'area':'busan','address':'부산 부산진구'},'other':{'name':'서울','is_active':True,'area':'gangnam','address':'서울 강남구'}},'schedules':{'2030-01-01':{'cafes':{'c':{'themes':{'c__theme':{'slots':[{'time':'24:30','status':'full'}]}}},'other':{'themes':{'other__theme':{'slots':[{'time':'12:00','status':'full'}]}}}}}}}
        rows=_postgres_slots('2030-01-01','busan','c__theme',db)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['time_slot'],'24:30')
        self.assertEqual(rows[0]['theme_id'],'c__theme')
        self.assertEqual(_postgres_slots('2030-01-01','gangnam','c__theme',db),[])

class StorageRoutingTests(unittest.TestCase):
    def test_supabase_initialization_does_not_initialize_firebase(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from app import firestore_db
        from app.config import settings
        expected=SimpleNamespace(backend='supabase')
        with patch.object(settings,'crawl_storage','supabase'), patch.object(firestore_db,'_db',None), patch('app.postgres_document_store.PostgresStore',return_value=expected), patch.object(firestore_db.credentials,'Certificate',side_effect=AssertionError('Firebase forbidden')):
            firestore_db.init_firestore('unused')
            self.assertIs(firestore_db.get_db(),expected)
    def test_user_auth_database_remains_firebase(self):
        from unittest.mock import patch
        from app import firestore_db
        expected=object()
        with patch.object(firestore_db.firebase_admin,'_apps',{'existing':object()}), patch.object(firestore_db._fs,'client',return_value=expected):
            self.assertIs(firestore_db.get_auth_db(),expected)
    def test_document_filter_is_bound_and_metadata_fields_are_preserved(self):
        import asyncio
        from app.postgres_document_store import PostgresStore
        class Connection:
            async def fetch(self,sql,*params):
                self.sql=sql;self.params=params
                return [{'id':'c','name':'카페','metadata':'{"phone":"02-000"}'}]
        connection=Connection();store=object.__new__(PostgresStore)
        store.call=lambda fn:asyncio.run(fn(connection))
        rows=store.collection('cafes').where('id','==',"value' OR true --").get()
        self.assertNotIn("value'",connection.sql)
        self.assertEqual(connection.params,("value' OR true --",))
        self.assertEqual(rows[0].to_dict()['phone'],'02-000')
        with self.assertRaises(ValueError):store.collection('cafes').where('id; DROP TABLE themes','==','x').get()
