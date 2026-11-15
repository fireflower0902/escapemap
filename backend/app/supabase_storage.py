"""크롤링 데이터 전용 PostgreSQL 저장소. 기존 SQLite/Firebase 인증과 독립."""
import hashlib,json,pathlib
import asyncpg
from app.config import settings

def tls_context():
    import ssl
    # 표준 CA 체인과 호스트명 검증. Supabase 공식 배포 루트 CA 사용.
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_verify_locations(cafile=str(pathlib.Path(__file__).resolve().parents[1]/'data/supabase-ca.crt'))
    return context

async def connect():
    # Session pooler: 캐시된 prepared statement와 다른 세션의 충돌을 피한다.
    return await asyncpg.connect(settings.supabase_database_url,ssl=tls_context(),timeout=20,command_timeout=45,statement_cache_size=0)

async def migrate(conn):
    async with conn.transaction():
        await conn.execute("SELECT pg_advisory_xact_lock(824712503)")
        await conn.execute('CREATE SCHEMA IF NOT EXISTS escape')
        await conn.execute('CREATE TABLE IF NOT EXISTS escape.schema_migrations (version text PRIMARY KEY, digest text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())')
        for path in sorted((pathlib.Path(__file__).resolve().parents[1]/'migrations').glob('*.sql')):
            sql=path.read_text();digest=hashlib.sha256(sql.encode()).hexdigest()
            previous=await conn.fetchval('SELECT digest FROM escape.schema_migrations WHERE version=$1',path.name)
            if previous:
                if previous!=digest:raise ValueError('이미 적용된 마이그레이션 파일이 변경되었습니다.')
                continue
            await conn.execute(sql)
            await conn.execute('INSERT INTO escape.schema_migrations(version,digest) VALUES($1,$2)',path.name,digest)

async def import_metadata(conn,cafes,themes):
    # 모든 기본정보를 하나의 트랜잭션으로 이전. ID 및 추가 메타데이터 보존.
    async with conn.transaction():
        await conn.executemany('''INSERT INTO escape.cafes(id,name,branch_name,address,area,is_active,website_url,engine,metadata)
 VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb) ON CONFLICT(id) DO UPDATE SET
 name=excluded.name,branch_name=excluded.branch_name,address=excluded.address,area=excluded.area,
 is_active=excluded.is_active,website_url=excluded.website_url,engine=excluded.engine,metadata=cafes.metadata||excluded.metadata,
 updated_at=now() WHERE (cafes.name,cafes.branch_name,cafes.address,cafes.area,cafes.is_active,cafes.website_url,cafes.engine,cafes.metadata)
 IS DISTINCT FROM (excluded.name,excluded.branch_name,excluded.address,excluded.area,excluded.is_active,excluded.website_url,excluded.engine,cafes.metadata||excluded.metadata)''',
            [(c['id'],c['name'],c.get('branch_name'),c['address'],c['area'],c.get('is_active') is not False,c.get('website_url'),c.get('engine'),json.dumps(c,ensure_ascii=False)) for c in cafes])
        await conn.executemany('''INSERT INTO escape.themes(id,cafe_id,name,is_active,metadata)
 VALUES($1,$2,$3,$4,$5::jsonb) ON CONFLICT(id) DO UPDATE SET cafe_id=excluded.cafe_id,name=excluded.name,is_active=excluded.is_active,metadata=themes.metadata||excluded.metadata,updated_at=now()
 WHERE (themes.cafe_id,themes.name,themes.is_active,themes.metadata) IS DISTINCT FROM (excluded.cafe_id,excluded.name,excluded.is_active,themes.metadata||excluded.metadata)''',
            [(t['id'],t['cafe_id'],t['name'],t.get('is_active') is not False,json.dumps(t,ensure_ascii=False)) for t in themes])


def normalize_slots(cafe_id,service_date,themes):
    """수집기의 영업일·24~29시 표기를 보존하며 모호한 상태는 거부한다."""
    import datetime,re
    from urllib.parse import urlsplit
    day=datetime.date.fromisoformat(str(service_date));rows=[];seen=set()
    for tid,theme in themes.items():
        for slot in theme['slots']:
            value=slot.get('time','')
            if not re.fullmatch(r'(?:[01]\d|2\d):[0-5]\d',value):raise ValueError('잘못된 예약 시간')
            hh,mm=map(int,value.split(':'));minute=hh*60+mm;key=(tid,minute)
            if key in seen:raise ValueError('중복 예약 시간')
            seen.add(key);status=slot.get('status');url=slot.get('booking_url')
            if status not in ('available','full','closed','unknown'):raise ValueError('알 수 없는 예약 상태')
            if status=='available' and (not url or urlsplit(url).scheme not in ('http','https') or not urlsplit(url).netloc):raise ValueError('예약 가능 링크 누락')
            rows.append((tid,cafe_id,day,minute,status,url))
    return rows

async def save_cafe_date(conn,cafe_id,service_date,themes,observed_at):
    import datetime
    rows=normalize_slots(cafe_id,service_date,themes);day=datetime.date.fromisoformat(str(service_date))
    digest=hashlib.sha256(json.dumps(sorted(rows,key=lambda r:(r[0],r[3])),default=str,ensure_ascii=False).encode()).hexdigest()
    async with conn.transaction():
        await conn.execute('SELECT pg_advisory_xact_lock(hashtextextended($1,0))',cafe_id+':'+str(day))
        previous=await conn.fetchrow('SELECT content_hash,last_attempt_at FROM escape.cafe_date_checks WHERE cafe_id=$1 AND service_date=$2 FOR UPDATE',cafe_id,day)
        if previous and previous['last_attempt_at']>observed_at:return {'changed':False,'ignored_older':True,'slots':len(rows)}
        changed=not previous or previous['content_hash']!=digest
        if changed:
            await conn.executemany('''INSERT INTO escape.reservation_slots(theme_id,cafe_id,service_date,start_minute,status,booking_url,observed_at)
 VALUES($1,$2,$3,$4,$5,$6,$7) ON CONFLICT(theme_id,service_date,start_minute) DO UPDATE SET
 status=excluded.status,booking_url=excluded.booking_url,observed_at=excluded.observed_at
 WHERE (reservation_slots.status,reservation_slots.booking_url) IS DISTINCT FROM (excluded.status,excluded.booking_url)''',[(*r,observed_at) for r in rows])
            keys=json.dumps([{'theme_id':r[0],'start_minute':r[3]} for r in rows])
            await conn.execute('''DELETE FROM escape.reservation_slots s WHERE cafe_id=$1 AND service_date=$2 AND NOT EXISTS
 (SELECT 1 FROM jsonb_to_recordset($3::jsonb) AS n(theme_id text,start_minute integer) WHERE n.theme_id=s.theme_id AND n.start_minute=s.start_minute)''',cafe_id,day,keys)
        await conn.execute('''INSERT INTO escape.cafe_date_checks(cafe_id,service_date,status,last_attempt_at,last_success_at,content_hash)
 VALUES($1,$2,'success',$3,$3,$4) ON CONFLICT(cafe_id,service_date) DO UPDATE SET status='success',last_attempt_at=excluded.last_attempt_at,last_success_at=excluded.last_success_at,content_hash=excluded.content_hash,error=NULL''',cafe_id,day,observed_at,digest)
    return {'changed':changed,'ignored_older':False,'slots':len(rows)}

async def record_failure(conn,cafe_id,service_date,observed_at,error_kind):
    """수집 실패는 이전 정상 슬롯을 덮어쓰지 않으며 최신 검사 상태만 갱신한다."""
    import datetime
    async with conn.transaction():
        day=datetime.date.fromisoformat(str(service_date))
        await conn.execute('SELECT pg_advisory_xact_lock(hashtextextended($1,0))',cafe_id+':'+str(day))
        await conn.execute('''INSERT INTO escape.cafe_date_checks(cafe_id,service_date,status,last_attempt_at,error)
 VALUES($1,$2,'failed',$3,$4) ON CONFLICT(cafe_id,service_date) DO UPDATE SET
 status='failed',last_attempt_at=excluded.last_attempt_at,error=excluded.error
 WHERE cafe_date_checks.last_attempt_at <= excluded.last_attempt_at''',cafe_id,day,observed_at,error_kind)

async def read_schedule(conn,service_date,freshness_seconds):
    import datetime
    day=datetime.date.fromisoformat(str(service_date))
    rows=await conn.fetch('''SELECT s.*,c.last_success_at FROM escape.reservation_slots s
 JOIN escape.cafe_date_checks c ON c.cafe_id=s.cafe_id AND c.service_date=s.service_date
 WHERE s.service_date=$1 AND c.status='success' AND c.last_success_at >= now()-($2 * interval '1 second')''',day,freshness_seconds)
    cafes={}
    for r in rows:
        cafe=cafes.setdefault(r['cafe_id'],{'themes':{},'crawled_at':r['last_success_at'].isoformat()})
        theme=cafe['themes'].setdefault(r['theme_id'],{'slots':[]});minute=r['start_minute']
        status='closed' if r['status']=='available' and r['starts_at']<=datetime.datetime.now(datetime.timezone.utc) else r['status']
        theme['slots'].append({'time':f'{minute//60:02d}:{minute%60:02d}','status':status,'booking_url':r['booking_url']})
    return {'cafes':cafes}
