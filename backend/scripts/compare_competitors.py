"""수집한 공개 카페/테마 이름을 우리 DB 스냅샷과 보수적으로 비교하고 Markdown 생성."""
from __future__ import annotations
import collections,datetime,difflib,json,pathlib,re,unicodedata
ROOT=pathlib.Path(__file__).resolve().parents[1]/'reports/competitors'
LABELS={'matched':'이름 일치','candidate':'이름 확인 필요','missing':'우리 목록에서 미발견','cafe_missing':'카페 연결 필요'}
SOURCES={'bbabang':'빠방','roomescape':'전방'}

def normalize(value):
 value=unicodedata.normalize('NFKC',value or '').lower()
 for text in ('방탈출카페','방탈출 카페','방탈출','주식회사','(주)'):
  value=value.replace(text,'')
 return re.sub(r'[^\w가-힣]+','',value,flags=re.UNICODE).replace('_','')

def full_name(cafe):
 return ' '.join(filter(None,[(cafe.get('name') or '').strip(),(cafe.get('branch_name') or '').strip()])) or f"이름 미등록 ({cafe['id']})"

def address(value):
 value=value or ''
 for a,b in [('서울특별시','서울'),('부산광역시','부산'),('대구광역시','대구'),('인천광역시','인천'),('광주광역시','광주'),('대전광역시','대전'),('울산광역시','울산'),('세종특별자치시','세종'),('경기도','경기'),('강원특별자치도','강원'),('강원도','강원'),('충청북도','충북'),('충청남도','충남'),('전북특별자치도','전북'),('전라북도','전북'),('전라남도','전남'),('경상북도','경북'),('경상남도','경남'),('제주특별자치도','제주')]:value=value.replace(a,b)
 return normalize(value)

def cafe_match(item,ours,index):
 key=normalize(item.get('name'))
 matches=index.get(key,[])
 if len(matches)==1:return {'status':'matched','our_id':matches[0]['id'],'our_name':full_name(matches[0]),'our_active':matches[0].get('is_active',True),'candidates':[]}
 candidates=[]
 for cafe in ours:
  name=full_name(cafe);score=difflib.SequenceMatcher(None,key,normalize(name)).ratio()
  same_address=bool(item.get('address') and cafe.get('address') and address(item['address'])==address(cafe['address']))
  if same_address:score=max(score,.95)
  if score>=.65:candidates.append({'id':cafe['id'],'name':name,'score':round(score,3),'address':cafe.get('address',''),'same_address':same_address})
 candidates=sorted(candidates,key=lambda x:x['score'],reverse=True)[:3]
 return {'status':'candidate' if candidates else 'missing','our_id':None,'our_name':None,'candidates':candidates}

def compare(source,ours):
 cafes=ours['cafes'];themes=ours['themes'];index=collections.defaultdict(list)
 for c in cafes:
  key=normalize(full_name(c));index[key].append(c)
  if c.get('branch_name'):
   alias=key[:-1] if key.endswith('점') else key+'점'
   if not any(x['id']==c['id'] for x in index[alias]):index[alias].append(c)
 for c in cafes:
  for alias in c.get('aliases') or []:
   key=normalize(alias)
   if key and not any(x['id']==c['id'] for x in index[key]):index[key].append(c)
 cafe_rows=[{**c,**cafe_match(c,cafes,index)} for c in source['cafes']]
 by_name=collections.defaultdict(list)
 for c in cafe_rows:by_name[normalize(c['name'])].append(c)
 themes_by_cafe=collections.defaultdict(list)
 for t in themes:themes_by_cafe[str(t['cafe_id'])].append(t)
 rows=[]
 for t in source['themes']:
  candidates=by_name.get(normalize(t.get('cafe_name')),[])
  m=candidates[0] if len(candidates)==1 else cafe_match({'name':t.get('cafe_name','')},cafes,index)
  row={**t,'our_id':None,'our_name':None,'candidates':[],'our_cafe_id':m.get('our_id'),'our_cafe_name':m.get('our_name')}
  if m['status']!='matched':row.update(status='cafe_missing',candidates=m.get('candidates',[]))
  else:
   pool=themes_by_cafe[m['our_id']]
   exact=[x for x in pool if normalize(x['name'])==normalize(t['name'])]
   if len(exact)==1:row.update(status='matched',our_id=exact[0]['id'],our_name=exact[0]['name'])
   else:
    options=sorted([{'id':x['id'],'name':x['name'],'score':round(difflib.SequenceMatcher(None,normalize(t['name']),normalize(x['name'])).ratio(),3)} for x in pool],key=lambda x:x['score'],reverse=True)
    row['candidates']=[x for x in options[:3] if x['score']>=.65]
    row['status']='candidate' if row['candidates'] else 'missing'
  rows.append(row)
 return {'source':source['source'],'coverage':source.get('coverage',{}),'collected_at':source.get('collected_at'),'cafes':cafe_rows,'themes':rows,
         'summary':{'cafes':dict(collections.Counter(x['status'] for x in cafe_rows)),'themes':dict(collections.Counter(x['status'] for x in rows))},
         'ours_not_observed_cafes':[{'id':c['id'],'name':full_name(c),'address':c.get('address','')} for c in cafes if c['id'] not in {x.get('our_id') for x in cafe_rows if x['status']=='matched'}]}

def cell(v):return str(v if v is not None else '—').replace('|','\\|').replace('\r',' ').replace('\n',' ')
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+['| '+' | '.join(cell(v) for v in r)+' |' for r in rows])
def write_md(filename,title,headers,rows,note=''):
 (ROOT/filename).write_text('# '+title+'\n\n'+note+'\n\n'+table(headers,rows)+'\n')

def main():
 ours=json.loads((ROOT/'ours.json').read_text());results=[]
 for source,label in SOURCES.items():
  file=ROOT/(source+'.json')
  if not file.exists():continue
  data=json.loads(file.read_text());result=compare(data,ours);results.append(result)
  write_md(source+'-cafes.md',label+' 카페 전체 수집 목록',['번호','카페명','주소','조회 지역','우리 목록 비교','우리 카페 / 확인 후보'],[(i+1,x['name'],x.get('address',''),x.get('region') or x.get('source_region',''),LABELS[x['status']],x.get('our_name') or ' / '.join(c['name'] for c in x['candidates'])) for i,x in enumerate(result['cafes'])],f"수집 {data.get('collected_at','')} · {len(result['cafes'])}개. 조회한 공개 목록 기준이며 공식 전체 DB를 뜻하지 않습니다.")
  write_md(source+'-themes.md',label+' 테마 전체 수집 목록',['번호','카페명','테마명','지역','수집 필터','우리 목록 비교','우리 테마 / 확인 후보'],[(i+1,x.get('cafe_name',''),x['name'],x.get('region') or x.get('source_region',''),{'active_filter':'영업 중 기본 필터','additional_no_active_filter':'상태 필터 해제 추가분'}.get(x.get('scope'),'공개 전국 목록'),LABELS[x['status']],x.get('our_name') or ' / '.join(c['name'] for c in x['candidates'])) for i,x in enumerate(result['themes'])],f"수집 {data.get('collected_at','')} · {len(result['themes'])}개. 테마는 연결된 동일 카페 안에서만 이름을 비교합니다.")
 summary={'generated_at':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(),'ours_collected_at':ours.get('collected_at'),'ours_cafes':len(ours['cafes']),'ours_themes':len(ours['themes']),'results':results}
 (ROOT/'comparison.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
 write_md('ours-cafes.md','우리 DB 카페 전체 목록',['ID','카페명','주소','활성 여부'],[(c['id'],full_name(c),c.get('address',''),c.get('is_active',True)) for c in ours['cafes']],f"읽기 전용 DB 스냅샷 {ours.get('collected_at','')}")
 cafenames={c['id']:full_name(c) for c in ours['cafes']}
 write_md('ours-themes.md','우리 DB 테마 전체 목록',['ID','카페명','테마명','활성 여부'],[(t['id'],cafenames.get(t['cafe_id'],t['cafe_id']),t['name'],t.get('is_active',True)) for t in ours['themes']],f"읽기 전용 DB 스냅샷 {ours.get('collected_at','')}")
 for kind in ('cafes','themes'):
  rows=[(SOURCES[r['source']],x.get('cafe_name',''),x['name'],LABELS[x['status']],x.get('our_name') or ' / '.join(c['name'] for c in x['candidates'])) for r in results for x in r[kind] if x['status']!='matched']
  write_md('check-'+kind+'.md','카페 비교 확인 목록' if kind=='cafes' else '테마 비교 확인 목록',['사이트','소속 카페','카페명 / 테마명','판정','확인 후보'],rows,'미발견은 이번 스냅샷에서 이름이 일치하지 않았다는 뜻입니다. 누락 확정·폐업 판정이 아닙니다.')
 lines=['# 경쟁사 카페·테마 목록 비교','',f"생성: {summary['generated_at']}",'',f"우리 DB: 카페 {len(ours['cafes'])}곳 · 테마 {len(ours['themes'])}개. 비활성 카페도 포함합니다.",'','## 비교 결과','',table(['사이트','카페 수','카페 이름 일치','카페 확인 필요','테마 수','테마 이름 일치','테마 확인 필요'],[(SOURCES[r['source']],len(r['cafes']),r['summary']['cafes'].get('matched',0),len(r['cafes'])-r['summary']['cafes'].get('matched',0),len(r['themes']),r['summary']['themes'].get('matched',0),len(r['themes'])-r['summary']['themes'].get('matched',0)) for r in results]),'','## 전체 목록 파일','','- [우리 카페 목록](ours-cafes.md) · [우리 테마 목록](ours-themes.md)','- [빠방 카페 목록](bbabang-cafes.md) · [빠방 테마 목록](bbabang-themes.md)','- [전방 카페 목록](roomescape-cafes.md) · [전방 테마 목록](roomescape-themes.md)','- [카페 확인 목록](check-cafes.md) · [테마 확인 목록](check-themes.md)','','## 비교 기준','','- Unicode·대소문자·띄어쓰기·기호와 일반적인 방탈출 표기를 정리해 이름을 대조합니다. 지점 번호는 유지하고, 우리 DB의 지점 필드가 있는 경우 끝의 점 표기 유무를 대조합니다.','- 유사한 이름이나 주소 일치는 확인 후보로 남기며 자동으로 합치지 않습니다. 공식 지점 안내로 수동 확인한 별칭만 기존 카페 ID에 연결합니다.','- 테마는 이름이 연결된 동일 카페 안에서만 대조합니다. 카페 연결이 불분명하면 테마를 누락으로 확정하지 않습니다.','- 경쟁사에 없는 우리 항목은 수집 범위가 다를 수 있어 부재를 확정하지 않습니다.','- 경쟁사 목록을 우리 운영 DB에 자동 추가하지 않았습니다.','','## 수집 범위와 확인할 항목','']
 for r in results:
  lines+=['### '+SOURCES[r['source']],'',f"수집 시각: {r.get('collected_at')}",'', '공개 UI에서 확인한 고유 카페명·테마명 목록입니다. 아래 수집 범위와 필터를 함께 확인하세요.','']
  cov=r['coverage']
  if r['source']=='bbabang':
   lines += ['기본 영업 중 필터 테마 **1,947개**, 상태 필터 해제 후 추가 확인 **121개**, 합계 **2,068개**입니다. 추가분에는 이전·비운영 테마가 섞일 수 있습니다. 지역 화면 합계 1,955와 고유 이름쌍의 집계 기준이 달라 완전 수집을 보장하지 않습니다.', '', '아래 지역 표는 최초 순회 기록입니다. 이후 정렬 변경 추가 수집 결과는 전체 목록에 반영되어 있으며 이 표의 합계와 다릅니다.', '']
  if cov.get('regions'):
   lines+=[table(['지역','화면 기준 테마 수','읽은 테마 수','카페 수','건수 일치'],[(x['name'],x['expectedThemes'],x['themes'],x['cafes'],x.get('expectedMatched',False)) for x in cov['regions']]),'']
  else:lines+=['```json',json.dumps(cov,ensure_ascii=False,indent=2),'```','']
 if (ROOT/'official-verification.md').exists():lines+=['## 공식 사이트 검증·반영 내역','','[공식 검증 목록·출처·DB 반영·남은 검증 후보](official-verification.md)','','신규 등록과 예약 시간대 크롤링 검증은 별도 상태로 관리합니다.','','[기존 오류 재점검·복구 보고서](crawler-recovery-2026-11-15.md) · [누락 후보 웹검색 출처](research-index.md)','']
 lines+=['## 다시 비교하기','','`backend`에서 `uv run python scripts/compare_competitors.py`를 실행하면 JSON과 Markdown 목록을 재생성합니다.','','개발 화면: `http://localhost:3000/dev/comparison`','', '원본: [빠방](https://bbabang.net/#home), [전방 카페](https://www.roomescape.co.kr/cafe), [전방 테마](https://www.roomescape.co.kr/theme)']
 (ROOT/'README.md').write_text('\n'.join(lines)+'\n')
 print(json.dumps([{ 'source':r['source'],'cafes':len(r['cafes']),'themes':len(r['themes']),'summary':r['summary']} for r in results],ensure_ascii=False))
if __name__=='__main__':main()
