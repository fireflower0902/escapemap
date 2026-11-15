"""지점별 검증 기록을 검토용 Markdown으로 정리한다."""
import collections,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/crawlers/priority-review-2026-11-15'
def read(p):return json.loads(p.read_text())
def cell(x):return str('' if x is None else x).replace('|','/').replace('\n',' ')[:240]
def main():
 groups=read(OUT/'baseline.json');names={c['id']:c['name'] for rows in groups.values() for c in rows}
 lines=['# 전국 크롤러 우선 검토 — 2026-11-15','','## 검토 기준','','- 연결된 회색: 크롤러 설정은 있으나 해당 지점의 유효한 검증 기록이 없음.','- 미연결 회색: 지점에 매핑된 크롤러가 없음. 크롤링 불가능·폐업 확정이라는 뜻이 아님.','- 주황색: 오류·시간 초과·누락 등 확인 필요. 원인과 실행 범위를 확인한 뒤 판정.','- 오늘부터 2일 후까지 공개 예약 정보를 읽기 전용 메모리 DB에서 검사. 운영 Firestore에 쓰지 않음.','- 통과는 응답·파싱·데이터 형식 검사 결과이며 실제 예약 성공이나 모든 테마 완전성을 보증하지 않음.','- 표의 시간대는 조회한 날짜 전체의 합계이며 예약 가능과 마감 모두 포함.','','## 수정한 사항','','- 예약 현황 필드 누락, 마감 목록 조회 실패를 빈자리로 간주하던 경로 차단.','- 범위를 알 수 없는 과거 실패 기록을 전체 지점에 적용하지 않도록 수정.','- 지점 ID를 명시해 단독 검증 가능. 중첩된 검증 결과도 현황판에서 읽도록 수정.','- 마스터키·룸엘의 24~29시 심야 시간은 다음 날 시각으로 비교하며 원래 영업일·시간 표기 유지.','','## 예약 오표시 방지 검사','','| 수집기 | 결과 | 테마 | 시간대 | 사유 |','|---|---|---:|---:|---|']
 for r in read(OUT/'safety/summary.json'):
  lines.append('| '+' | '.join(map(cell,[r['script'],r['status'],r.get('themes_fetched',0),r.get('slots',0),r.get('error') or '; '.join(r.get('log_errors',[]))]))+' |')
 lines+=['','리버스 기존 공개 API에서 reserv_data가 빠졌으며 홈페이지 예약 링크는 sh.zeroworldesc.co.kr을 가리킴. 새 예약처의 지점 일치 및 파서 확인 전 빈자리 생성 보류. 오아시스 null 응답도 공식 의미 확인 전 빈 목록으로 해석하지 않음.']
 recoveries=[]
 for p in (OUT/'recovery').rglob('sync_*.json') if (OUT/'recovery').exists() else []:
  r=read(p);recoveries.append(r)
 for phase,title in [('orange','기존 주황색 지점'),('gray_connected','기존 연결된 회색 지점')]:
  p=OUT/phase/'summary.json';rows=read(p) if p.exists() else []
  for index,row in enumerate(rows):
   cid=row['requested_id']
   for r in recoveries:
    if cid in r.get('per_cafe',{}) and r.get('status')=='smoke_pass':
     counts=r['per_cafe'][cid];row=dict(row,status='smoke_pass',themes_fetched=counts['themes'],slots=counts['slots'],statuses=counts['statuses'],log_errors=[],error=None);break
   row['_id']=cid;rows[index]=row
  counts=collections.Counter(r['status'] for r in rows)
  lines+=['',f'## {title}','','검사 완료 '+str(len(rows))+'곳 / 기준 '+str(len(groups[phase]))+'곳. 결과: '+', '.join(f'{k} {v}곳' for k,v in counts.items())+'.']
  if phase=='orange':lines+=['','룸사 19곳은 공개 목록만 수집 가능한 것으로 앞서 확인되어 시간대 재시도에서 제외. 확인 필요 상태 유지.']
  lines+=['','| 카페 / 지점 | ID | 결과 | 테마 | 시간대 | 예약 가능 | 수집기 | 오류 / 참고 |','|---|---|---|---:|---:|---:|---|---|']
  for r in rows:
   reason=r.get('error') or '; '.join(r.get('log_errors',[])[:2]) or ('수집 결과 없음 / 파서·예약처 확인 필요' if not r.get('slots') else '')
   lines.append('| '+' | '.join(map(cell,[names.get(r['_id'],r['_id']),r['_id'],r['status'],r.get('themes_fetched',0),r.get('slots',0),r.get('statuses',{}).get('available',0),r['script'],reason]))+' |')
 lines+=['','## 미연결 40곳 — 예약처 예비 확인','','아래는 등록 URL의 응답 상태와 공개 링크 점검이다. 접속 실패만으로 폐업 판정하지 않으며, HTTP 응답만으로 정상 운영 판정하지 않는다. 지도·단축 URL은 공식 예약 URL 확보 대상으로 분류했다.','','| 카페 / 지점 | ID | 등록/도착 URL | 확인 결과 | 페이지 제목 | 공개 예약 링크 |','|---|---|---|---|---|---|']
 for r in read(OUT/'unconnected.json'):
  lines.append('| '+' | '.join(map(cell,[r['name'],r['id'],r['url'],r['result'],r.get('title'),', '.join(r.get('booking_links',[]))]))+' |')
 lines+=['','## 후속 작업','','1. DNS·404·500·503·접근 제한·테마 없음·시간대 없음으로 원인을 나눠 공식 예약처 재확인.','2. 미연결 목록은 주소·지점·공식 링크로 기존 등록과 중복 여부부터 확인 후 연결.','3. 룸사 및 접근 제한 사이트는 목록 정보와 실시간 예약 가능 여부를 분리 유지.','4. 이 검토 결과는 로컬 코드와 테스트 기록이며 배포·운영 스케줄 반영은 별도.','','최종 현황판 조회에서 Firestore 로딩 실패가 관측됨. 화면은 경고와 저장 수치 미확인 상태로 전환되며, 이 보고서의 수치는 운영 DB 저장량이 아니라 독립 검사 결과임.', '', '검증: 백엔드 회귀 테스트 41개, 프런트 현황판 테스트 9개, TypeScript 검사 통과. 기존 test_engines.py는 pytest 미설치로 unittest 전체 탐색 시 import 실패하여 위 41개 명시 실행과 구분한다.', '', '원본: priority-review-2026-11-15/ 하위 baseline.json, safety/, orange/, gray_connected/, recovery/, unconnected.json.']
 (OUT.parent/'priority-review-2026-11-15.md').write_text('\n'.join(lines)+'\n');print('wrote',OUT.parent/'priority-review-2026-11-15.md')
if __name__=='__main__':main()
