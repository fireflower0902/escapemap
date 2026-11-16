import importlib.util,json,pathlib,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('refresh_scheduled',ROOT/'scripts/refresh_scheduled.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class ScheduledRefreshTests(unittest.TestCase):
 def test_partitions_cover_every_cafe_exactly_once(self):
  rows=json.loads((ROOT/'data/scheduled-crawlers.json').read_text());shards=[module.select_tasks(rows,i,8) for i in range(8)]
  ids=[r['cafe_id'] for group in shards for r in group]
  self.assertEqual(len(ids),len(set(ids)));self.assertEqual(set(ids),{r['cafe_id'] for r in rows})
  self.assertLessEqual(max(map(len,shards))-min(map(len,shards)),1)
  self.assertEqual(shards,[module.select_tasks(list(reversed(rows)),i,8) for i in range(8)])
 def test_rejects_invalid_partition_before_collection(self):
  for shard,shards in [(-1,8),(8,8),(0,0)]:
   with self.assertRaises(ValueError):module.select_tasks([],shard,shards)
 def test_manifest_uses_existing_crawlers(self):
  for row in json.loads((ROOT/'data/scheduled-crawlers.json').read_text()):
   self.assertTrue(row['script'].startswith('sync_'));self.assertTrue((ROOT/'scripts'/(row['script']+'.py')).is_file())

 def test_provider_order_avoids_blocking_every_worker_on_one_site(self):
  items=[{'script':'sync_a','cafe_id':str(n)} for n in range(5)]+[{'script':'sync_b','cafe_id':'b'}]
  selected=module.select_tasks(items,0,1)
  self.assertEqual([r['script'] for r in selected[:2]],['sync_a','sync_b'])

 def test_deferred_cafes_are_not_scheduled_automatically(self):
  scheduled=json.loads((ROOT/'data/scheduled-crawlers.json').read_text())
  deferred=json.loads((ROOT/'data/deferred-crawlers.json').read_text())
  self.assertFalse({r['cafe_id'] for r in scheduled} & {r['cafe_id'] for r in deferred})
  self.assertTrue(all(r.get('reason') and r.get('runtime')=='github_actions' for r in deferred))
