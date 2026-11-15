import datetime,unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
from scripts import run_supabase_crawler as runner
class Transaction:
 async def __aenter__(self):return self
 async def __aexit__(self,*args):return False
class Connection:
 def transaction(self):return Transaction()
 async def fetchval(self,sql,*args):return True if 'EXISTS' in sql else 1
 async def execute(self,*args):pass
 async def close(self,**kwargs):pass
class PublishRangeTests(unittest.IsolatedAsyncioTestCase):
 async def test_monthly_response_publishes_only_today_through_day_six(self):
  day=datetime.date(2030,1,10)
  schedules={(day+datetime.timedelta(days=n)).isoformat():{'cafes':{'c':{'themes':{}}}} for n in range(-1,9)}
  store=SimpleNamespace(data={'schedules':schedules,'themes':{}},writes=[])
  check={'checked_at':'2030-01-10T12:00:00+09:00','script':'test','status':'smoke_pass'}
  save=AsyncMock(return_value={})
  with patch.object(runner,'connect',AsyncMock(return_value=Connection())),patch.object(runner,'import_metadata',AsyncMock()),patch.object(runner,'save_cafe_date',save):
   await runner.publish(check,store,'c',6)
  self.assertEqual([call.args[2] for call in save.await_args_list],[(day+datetime.timedelta(days=n)).isoformat() for n in range(7)])
