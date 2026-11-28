import importlib.util,json,pathlib,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('refresh_scheduled',ROOT/'scripts/refresh_scheduled.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class ScheduledRefreshTests(unittest.TestCase):
 def test_partitions_cover_every_cafe_exactly_once(self):
  rows=json.loads((ROOT/'data/scheduled-crawlers.json').read_text());shards=[module.select_tasks(rows,i,8) for i in range(8)]
  ids=[r['cafe_id'] for group in shards for r in group]
  self.assertEqual(len(ids),len(set(ids)));self.assertEqual(set(ids),{r['cafe_id'] for r in rows})
  self.assertTrue(all(shards))
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


def test_candidate_manifest_does_not_collect_production_list(tmp_path, monkeypatch):
 from types import SimpleNamespace
 candidate=tmp_path/'candidates.json'
 candidate.write_text(json.dumps([{'script':'sync_candidate_db','cafe_id':'candidate-only'}]))
 output=tmp_path/'verification'
 calls=[]
 def fake_run(args, **kwargs):
  calls.append(args)
  return SimpleNamespace(returncode=0)
 monkeypatch.setattr(module,'ROOT',tmp_path)
 monkeypatch.setattr(module.subprocess,'run',fake_run)
 monkeypatch.setattr(module.sys,'argv',['refresh_scheduled.py','--manifest',str(candidate),'--output',str(output),'--workers','1'])
 assert module.main()==0
 assert len(calls)==1 and 'candidate-only' in calls[0]
 report=json.loads((output/'shard-0.json').read_text())
 assert report['total']==report['published']==1
 assert report['results'][0]['cafe_id']=='candidate-only'
 assert not (tmp_path/'reports/scheduled').exists()


def test_provider_fanout_is_bounded_across_all_groups():
 rows=json.loads((ROOT/'data/scheduled-crawlers.json').read_text())
 groups=[module.select_tasks(rows,i,12) for i in range(12)]
 for provider in {r['script'] for r in rows}:
  count=sum(any(r['script']==provider for r in group) for group in groups)
  assert count <= (10 if provider=='sync_escapetop_db' else 6)
 assert sum(map(len,groups))==len(rows)


def test_runtime_weighting_avoids_one_slow_group():
 rows=[{'script':'sync_a','cafe_id':str(i),'estimated_seconds':100 if i<4 else 1} for i in range(16)]
 groups=[module.select_tasks(rows,i,4) for i in range(4)]
 weights=[sum(r['estimated_seconds'] for r in g) for g in groups]
 assert max(weights)-min(weights)<=1
 assert groups==[module.select_tasks(list(reversed(rows)),i,4) for i in range(4)]


def test_long_provider_queues_start_first_without_lock_waiter_tasks():
 rows=[{'script':'sync_a','cafe_id':str(i),'estimated_seconds':1} for i in range(3)]
 rows+=[{'script':'sync_b','cafe_id':'slow','estimated_seconds':20}]
 batches=module.provider_batches(rows)
 assert [[r['cafe_id'] for r in b] for b in batches]==[['slow'],['0','1','2']]
 assert len({b[0]['script'] for b in batches})==len(batches)
 assert sum(map(len,batches))==len(rows)
