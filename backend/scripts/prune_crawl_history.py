"""예약 현황에 필요 없는 7일 이전 수집 이력만 정리한다."""
import asyncio,datetime,pathlib,sys
from zoneinfo import ZoneInfo
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.supabase_storage import connect
async def main():
 conn=await connect()
 try:
  cutoff=datetime.datetime.now(ZoneInfo('Asia/Seoul')).date()-datetime.timedelta(days=7)
  async with conn.transaction():
   removed_results=await conn.execute("DELETE FROM escape.crawl_results WHERE run_id IN (SELECT id FROM escape.crawl_runs WHERE started_at < now()-interval '7 days')")
   removed_runs=await conn.execute("DELETE FROM escape.crawl_runs WHERE started_at < now()-interval '7 days'")
   removed_slots=await conn.execute('DELETE FROM escape.reservation_slots WHERE service_date < $1',cutoff)
   removed_checks=await conn.execute('DELETE FROM escape.cafe_date_checks WHERE service_date < $1',cutoff)
  print('Old history cleanup:',cutoff,removed_results,removed_runs,removed_slots,removed_checks)
 finally:await conn.close(timeout=5)
if __name__=='__main__':
 try:asyncio.run(main())
 except Exception as error:print('History cleanup failed:',type(error).__name__);raise SystemExit(1)
