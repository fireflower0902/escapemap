"""기존 수집기의 문서 호출을 전용 PostgreSQL 테이블로 연결한다."""
import asyncio,copy,datetime,json,threading
from zoneinfo import ZoneInfo
from app.supabase_storage import connect,import_metadata,save_cafe_date

class Snapshot:
 def __init__(self,id,data):self.id=id;self._data=data;self.exists=data is not None
 def to_dict(self):return copy.deepcopy(self._data)

class Document:
 def __init__(self,store,name,id):self.store=store;self.name=name;self.id=str(id)
 def get(self):return Snapshot(self.id,self.store.get_document(self.name,self.id))
 def set(self,data,merge=False):self.store.set_document(self.name,self.id,data,merge)
 def update(self,data):self.set(data,True)

class Collection:
 def __init__(self,store,name,filters=()):self.store=store;self.name=name;self.filters=filters
 def document(self,id):return Document(self.store,self.name,id)
 def where(self,key,op,value):return Collection(self.store,self.name,(*self.filters,(key,op,value)))
 def stream(self):return iter(self.store.query(self.name,self.filters))
 def get(self):return list(self.stream())

class PostgresStore:
 backend='supabase'
 def __init__(self):
  self.loop=asyncio.new_event_loop();self.connection=None
  self.thread=threading.Thread(target=self.loop.run_forever,daemon=True);self.thread.start()
  self.lock=None
 def call(self,fn):
  async def execute():
   if self.lock is None:self.lock=asyncio.Lock()
   async with self.lock:
    if self.connection is None or self.connection.is_closed():self.connection=await connect()
    return await fn(self.connection)
  return asyncio.run_coroutine_threadsafe(execute(),self.loop).result(timeout=65)
 def collection(self,name):
  if name not in ('cafes','themes','schedules','cafe_hashes'):raise ValueError('크롤링 저장소에서 지원하지 않는 컬렉션')
  return Collection(self,name)
 def query(self,name,filters=()):
  if name not in ('cafes','themes'):raise ValueError('기본정보 조회 대상만 지원')
  allowed={'id','name','area','is_active','cafe_id'};clauses=[];args=[]
  for key,op,value in filters:
   if key not in allowed or (key=='cafe_id' and name!='themes') or (key=='area' and name!='cafes'):raise ValueError('지원하지 않는 조회 필드')
   args.append(value)
   if op=='==':clauses.append(f'{key}=${len(args)}')
   elif op=='in':clauses.append(f'{key}=ANY(${len(args)})')
   else:raise ValueError('지원하지 않는 조회 조건')
  where=' WHERE '+' AND '.join(clauses) if clauses else ''
  async def fetch(conn):
   rows=await conn.fetch('SELECT * FROM escape.'+name+where,*args);result=[]
   for r in rows:
    data=json.loads(r['metadata']) if isinstance(r['metadata'],str) else dict(r['metadata'])
    data.update({k:v for k,v in dict(r).items() if k not in ('metadata','updated_at')})
    result.append(Snapshot(r['id'],data))
   return result
  return self.call(fetch)
 def get_document(self,name,id):
  if name in ('cafes','themes'):
   rows=self.query(name,[('id','==',id)]);return rows[0].to_dict() if rows else None
  if name=='cafe_hashes':return {}
  if name=='schedules':
   async def fetch(conn):
    from app.config import settings
    from app.supabase_storage import read_schedule
    return await read_schedule(conn,id,settings.crawl_freshness_seconds)
   return self.call(fetch)
  raise ValueError('지원하지 않는 문서')
 def set_document(self,name,id,data,merge):
  if name=='cafe_hashes':return
  if name in ('cafes','themes'):
   old=self.get_document(name,id) if merge else None;record={**(old or {}),**data,'id':id}
   if name=='cafes':
    from app.areas import resolve_cafe_area
    record['area']=resolve_cafe_area(record.get('area'),record.get('address'))
   async def save(conn):
    if name=='cafes':await import_metadata(conn,[record],[])
    else:await import_metadata(conn,[],[record])
   self.call(save);return
  if name=='schedules':
   for cid,cafe in data['cafes'].items():self.save_schedule(id,cid,cafe['themes'],cafe['crawled_at'])
   return
  raise ValueError('지원하지 않는 문서')
 def save_schedule(self,day,cid,themes,when):
  if isinstance(when,str):when=datetime.datetime.fromisoformat(when)
  if not when.tzinfo:when=when.replace(tzinfo=ZoneInfo('Asia/Seoul'))
  return self.call(lambda conn:save_cafe_date(conn,cid,day,themes,when))
