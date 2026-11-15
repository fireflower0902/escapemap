"""실제 Postgres 제약과 트랜잭션을 검증. 테스트 데이터는 전부 롤백한다."""
import asyncio,datetime,json,pathlib,sys
from zoneinfo import ZoneInfo
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import asyncpg
from app.supabase_storage import connect,migrate,save_cafe_date,record_failure,read_schedule

async def main():
 conn=await connect()
 try:
  await migrate(conn)
  assert not await conn.fetchval("SELECT has_schema_privilege('anon','escape','USAGE')")
  transaction=conn.transaction();await transaction.start()
  try:
   cid='__rollback_storage_check__';tid=cid+'theme';day=datetime.date(2030,1,1);now=datetime.datetime.now(ZoneInfo('Asia/Seoul'))
   await conn.execute("INSERT INTO escape.cafes(id,name,address,area) VALUES($1,'검증용','서울 서초구','gangnam')",cid)
   await conn.execute("INSERT INTO escape.themes(id,cafe_id,name) VALUES($1,$2,'검증용')",tid,cid)
   themes={tid:{'slots':[{'time':'24:30','status':'available','booking_url':'https://example.com/reserve'}]}}
   assert (await save_cafe_date(conn,cid,day,themes,now))['changed']
   assert not (await save_cafe_date(conn,cid,day,themes,now))['changed']
   actual=await conn.fetchrow('SELECT starts_at,service_date FROM escape.reservation_slots WHERE theme_id=$1',tid)
   assert actual['starts_at'].astimezone(ZoneInfo('Asia/Seoul'))==datetime.datetime(2030,1,2,0,30,tzinfo=ZoneInfo('Asia/Seoul'))
   assert cid in (await read_schedule(conn,day,5400))['cafes']
   await record_failure(conn,cid,day,now+datetime.timedelta(seconds=1),'TestFailure')
   assert cid not in (await read_schedule(conn,day,5400))['cafes']
   assert await conn.fetchval('SELECT status FROM escape.reservation_slots WHERE theme_id=$1',tid)=='available'
   assert await conn.fetchval('SELECT status FROM escape.cafe_date_checks WHERE cafe_id=$1',cid)=='failed'
   assert (await save_cafe_date(conn,cid,day,themes,now))['ignored_older']
   try:
    async with conn.transaction():
     await conn.execute("INSERT INTO escape.reservation_slots(theme_id,cafe_id,service_date,start_minute,status,observed_at) VALUES($1,$2,$3,600,'available',$4)",tid,cid,day,now)
   except asyncpg.CheckViolationError:pass
   else:raise AssertionError('예약 가능 링크 제약 누락')
   await save_cafe_date(conn,cid,day,themes,now+datetime.timedelta(seconds=2))
   await conn.execute("UPDATE escape.cafe_date_checks SET last_success_at=now()-interval '2 hours' WHERE cafe_id=$1",cid)
   assert cid not in (await read_schedule(conn,day,5400))['cafes']
  finally:await transaction.rollback()
  assert not await conn.fetchval('SELECT EXISTS(SELECT 1 FROM escape.cafes WHERE id=$1)',cid)
  print('실제 DB 검증 통과: 심야 시간 · 중복 쓰기 · 실패 시 보존 · 역순 결과 차단 · 예약 링크 제약 · 테스트 롤백 · 비공개 스키마')
  (ROOT/'reports/supabase/storage-verification.json').write_text(json.dumps({'passed':True,'test_data_rolled_back':True,'checked_at':datetime.datetime.now().astimezone().isoformat()},indent=2)+'\n')
 finally:await conn.close(timeout=5)
if __name__=='__main__':
 try:asyncio.run(main())
 except Exception as error:print('DB 검증 실패:',type(error).__name__);raise SystemExit(1)
