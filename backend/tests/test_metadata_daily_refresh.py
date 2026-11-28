from types import SimpleNamespace
from unittest.mock import AsyncMock,patch

import pytest
from scripts import run_supabase_crawler as runner

class Transaction:
 async def __aenter__(self):return self
 async def __aexit__(self,*args):return False

@pytest.mark.asyncio
@pytest.mark.parametrize('previous,expected_ids,mode', [
    ('2030-01-10',['new'],'new_themes_only'),
    ('2030-01-09',['old','new'],'daily'),
])
async def test_daily_details_preserve_existing_cafe_and_discover_new_themes(previous,expected_ids,mode):
    conn=SimpleNamespace(transaction=lambda:Transaction(),fetchval=AsyncMock(return_value=1),
        fetchrow=AsyncMock(return_value={'refreshed_day':previous}),
        fetch=AsyncMock(return_value=[{'id':'old'}]),execute=AsyncMock(),close=AsyncMock())
    store=SimpleNamespace(data={'cafes':{'c':{'name':'old cafe name'}},'themes':{'old':{'name':'old','cafe_id':'c'},'new':{'name':'new','cafe_id':'c'}},'schedules':{}},writes=[('themes','old'),('themes','new')])
    check={'checked_at':'2030-01-10T12:00:00+09:00','script':'example','status':'smoke_pass'}
    metadata=AsyncMock()
    with patch.object(runner,'connect',AsyncMock(return_value=conn)),patch.object(runner,'import_metadata',metadata):
        await runner.publish(check,store,'c',6)
    args=metadata.await_args.args
    assert args[1]==[]
    assert sorted(t['id'] for t in args[2])==sorted(expected_ids)
    assert check['metadata_refresh']==mode
    updates=[call for call in conn.execute.await_args_list if 'UPDATE escape.cafes' in call.args[0]]
    assert len(updates)==int(mode=='daily')
