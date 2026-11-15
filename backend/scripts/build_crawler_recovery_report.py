"""공식 검증·수집 오류 재점검·검색 출처를 Markdown으로 정리 (네트워크/DB 쓰기 없음)."""
import json,pathlib,datetime,collections,sys
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.compare_competitors import table,full_name
P=ROOT/'reports/competitors'
def load(name):return json.loads((P/name).read_text())
def latest():
 result={}
 for p in (ROOT/'reports/crawlers').rglob('*.json'):
  try:data=json.loads(p.read_text())
  except (ValueError,OSError):continue
  for r in data if isinstance(data,list) else [data]:
   if isinstance(r,dict) and r.get('script') and r.get('checked_at','')>result.get(r['script'],{}).get('checked_at',''):result[r['script']]=dict(r,report=str(p.relative_to(ROOT)))
 return result

def main():
 ours=load('ours.json');manifest=load('verified-additions.json');checks=manifest.get('crawler_checks',{});last=latest();audit={r['script']:r for r in load('website-audit-2026-11-15.json')};at=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat();notes={
 'sync_deepthinker_db':'공식 /reservation/ 경로로 수정. CA 번들 경로를 실제 실행과 검증기에 공통 적용.',
 'sync_rabbithole_db':'변경된 테마 ID를 공식 선택 상자에서 조회. 신규 행운만물상도 수집.',
 'sync_play33_db':'공식 선택 상자의 현재 테마 ID 사용. 홍대·대전·수원 지점 추가.',
 'sync_orangetb_db':'onclick 속성의 공백·세미콜론 변경을 DOM으로 파싱. 두 지점 검증.',
 'sync_codek_db':'R_JIJEM=S2 지점 지정 수정, UTF-8 및 CQ 블록별 파싱. 강남·홍대 추가.',
 'sync_fantastrick_db':'폐기된 WordPress 경로 대신 공식 /api/slots 사용. 시간의 영속성 추가.',
 'sync_movieescape_cokr_db':'공식 날짜별 /theme/YYYY-MM-DD/ 구조와 마감 표기 반영.',
 'sync_zeroworld_db':'기존 홍대·강남은 sync_zeroworld_current_db에서 새 공식 시스템으로 복구. 기존 롯데월드 사이트는 접속/운영 확인 필요.',
 'sync_xcape_db':'개편 공식 5개 지점은 sync_xcape_current_db에서 별도 검증. 구 Playtheworld 연동을 현 지점 정상으로 간주하지 않음.',
 'sync_xphobia_db':'공식 사이트가 브랜드 허브로 개편되어 구 지점 API 미복구. 미확인 원거리 날짜를 예약 가능으로 추정하던 동작 제거.',
 'sync_ledasquare_db':'중첩 테마 제목 파서 수정. 공식 테마 조회 성공, 오늘·내일 시간표 응답은 비어 있어 미오픈/운영 일정 추가 확인 필요.',
 'sync_secretcode_db':'기존 공식 도메인 접속 실패. 검색에서 현재 공식 예약처 확인 불충분. 폐업으로 확정하지 않음.',
 'sync_conanescape_db':'기존 도메인 DNS/접속 실패. 검색에서 현재 공식 예약처 확인 불충분. 폐업으로 확정하지 않음.',
 'sync_lastescape_db':'기존 도메인 접속 실패. 현재 공식 예약처 확인 불충분. 폐업으로 확정하지 않음.',
 'sync_vescape_db':'기존 도메인 접속 실패. 현재 공식 예약처 확인 불충분. 폐업으로 확정하지 않음.',
 'sync_geniusescape_db':'공식 사이트 HTTP 403. 접근 제한을 우회하지 않으며 시간대 확인 필요.',
 'sync_playtheworld_etc_db':'기존 공개 API 조회에서 500 오류. 등록 플랫폼은 403 응답. 현재 연동/업체별 예약처 확인 필요.',
 'sync_sinbiweb_db':'전 지점 전체 조회 재검증. 정상 수집 지점과 일부 인증서/빈 응답 지점을 분리. 신규 10곳은 별도 선택 범위 검증.',
 'sync_thecode_db':'일부 테마 조회에서 상위 서버 HTTP 500. 정상 수집분과 서버 실패분 구분 필요.',
 'sync_cubeescape_db':'현재 도메인은 확인되지만 기존 시간표 파싱은 0건. 인증서/현재 예약 화면 구조 확인 필요.',
 'sync_themazegd_db':'기존 AJAX 경로 404. 홈페이지 존재만으로 시간표 정상으로 판단하지 않음. 현재 예약 경로 확인 필요.',
 'sync_thetrapsy_db':'기존 /re/l/ 응답은 잘못된 정보 경고. 현재 공개 화면 요청 파라미터 확인 필요.',
 'sync_mysteryroom_db':'기존 등록 도메인 접속 실패. 현재 공식 예약처 추가 확인 필요.',
 }
 names=load('verification-queue.json');research=sorted((P/'research').glob('batch-*.json'));queries=sum(len(json.loads(p.read_text())['queries']) for p in research)
 status=collections.Counter(c.get('status','untested') for c in checks.values());new_count=len(ours['cafes'])-365
 lines=['# 전국 카페 추가 및 크롤링 재검증','',f'갱신: {at}','','## DB 반영 결과','',table(['항목','이번 작업 전','현재','증가'],[('등록 카페',365,len(ours['cafes']),new_count),('등록 테마',1170,len(ours['themes']),len(ours['themes'])-1170)]),'','비활성·이전 등록 항목도 포함한 동일 기준의 전체 DB 수입니다. 신규 등록은 공식 주소·지점/테마 목록으로 확인한 항목이며, 경쟁사 이름만으로 추가하지 않았습니다.','',f"이전 작업 21곳을 포함한 공식 검증 등록 {len(manifest['cafes'])}곳 중, 실제 조회·파싱 검증 통과 {status.get('smoke_pass',0)}곳, 검토 필요 {sum(status.values())-status.get('smoke_pass',0)}곳입니다. 룸즈에이 신규 19곳은 공식 목록/테마 확인을 마쳤지만 시간대 검증은 보류입니다.",'','## 신규/공식 검증 지점별 수집 현황','',table(['카페','DB 테마','테스트 테마','테스트 시간대','조회 날짜','결과'],[(full_name(c),c.get('stored_themes',len(c['themes'])),checks.get(c['id'],{}).get('themes','—'),checks.get(c['id'],{}).get('slots','—'),', '.join(checks.get(c['id'],{}).get('dates',[])),checks.get(c['id'],{}).get('status','미검증')) for c in manifest['cafes']]),'','테스트 시간대 수는 표시된 날짜의 합계입니다. 조회·파싱 검증 통과는 모든 미래 날짜의 빈자리나 예약 성사를 보장하지 않습니다. 실제 DB에 오늘·내일 예약표를 반영했고, 저장 수치는 개발 현황판에서 테스트 수치와 따로 볼 수 있습니다.','','## 기존 오류 사이트 재점검','', '아래 결과는 각 실행의 범위 기준입니다. 대표 1개 지점의 통과를 전국 지점 전체 통과로 해석하지 않습니다.','']
 rows=[]
 for name in json.loads((ROOT/'reports/crawlers/recheck-targets-2026-11-15.json').read_text())+['sync_sinbiweb_db']:
  r=last.get(name,{});sites=audit.get(name,{}).get('websites',[]);proof=' / '.join(f"[{s['url']}]({s['url']}) ({s.get('status',s.get('error','미확인'))})" for s in sites)
  rows.append((name,r.get('status','미실행'),str(r.get('themes_fetched','—'))+' / '+str(r.get('slots','—')),r.get('scope',''),notes.get(name,'공식 페이지/요청 구조 추가 확인 필요.'),proof))
 lines += [table(['크롤러','최근 실행','테마/시간대','실행 범위','검토·수정 내역','공식 사이트 확인'],rows),'','### Sinbiweb 전 지점 검사에서 남은 항목','']
 full=ROOT/'reports/crawlers/final-2026-11-15-sinbiweb/sync_sinbiweb_db.json'
 if full.exists():
  d=json.loads(full.read_text());meta={c['id']:c for c in ours['cafes']}
  lines += [f"전체 실행: {d.get('themes_fetched',0)}테마 · {d.get('slots',0)}시간대, 상태 {d.get('status')}.",'',table(['ID','카페','테스트 테마/시간대'],[(cid,full_name(meta.get(cid,{'id':cid})),f"{v['themes']} / {v['slots']}") for cid,v in d.get('per_cafe',{}).items() if not v['slots']]),'', 'HTTP 오류·인증서 검증 실패·빈 예약표는 구분해서 확인해야 하며, 사이트가 없어졌거나 예약이 모두 찼다고 단정하지 않습니다.','']
 lines += ['## 룸즈에이 시간대 검증 보류','','- 공식 공개 지점 목록: [룸즈에이](https://roomsa.co.kr/locations), [공개 목록 조회](https://roomsa.co.kr/api/booking/stores).','- 공식 전국 21개 지점·108개 테마를 확인했고, 기존 등록 2곳을 제외한 19곳·98개 테마를 신규 반영했습니다.','- 정상 브라우저에서 예약 화면 보호 메시지가 표시되어 시간대는 미검증입니다. 목록 수집기는 시간대나 예약 가능 여부를 추정하지 않습니다.','','## 검색 및 중복 처리','',f'미검증 후보 {queries}개에 대해 웹검색을 수행하고 출처 링크를 보관했습니다. 검색 결과에 나타났다는 이유만으로 운영 확인 완료로 표시하지 않습니다.','',f"아직 공식 지점 연결/운영 확인이 필요한 이름 후보: {sum(q['status']=='unverified' for q in names)}개. 동일 카페의 이름 차이가 포함되어 실제 누락 카페 수와 다릅니다.",'','- [전체 후보 검색 출처](research-index.md)','- [공식 근거·반영 내역](official-verification.md)','- [경쟁사 비교 요약](README.md)','', '공식 지점 안내로 확인한 별칭은 verified-aliases.json에 근거와 함께 기록했습니다. 같은 주소의 다른 브랜드나 비슷한 이름만으로 연결하지 않습니다.','','## 실행 및 검증','','- 실제 사이트 테스트는 Firestore 대신 메모리 DB에 수행합니다. 테스트 자체는 운영 예약표를 쓰지 않습니다.','- 검증된 지점만 별도 실제 동기화로 카페·테마·오늘/내일 예약표를 반영했습니다.','- 신규 크롤러와 수정한 실행 설정은 로컬 코드에 반영했으며 GitHub 배포/실행은 하지 않았습니다.','- 비트포비아의 미확인 원거리 날짜를 전체 예약 가능으로 만들던 동작을 제거했습니다.','- Python CA 번들 경로를 설정해 실제 실행과 테스트의 TLS 기본 설정 차이를 보완했습니다.','','검색 출처의 임시 서명 URL은 자동 승인 검토에서 저장이 차단되어 제외했습니다. 공개 조사 링크는 쿼리·해시를 제거해 보관했습니다.','']
 (P/'crawler-recovery-2026-11-15.md').write_text('\n'.join(lines))
 index=['# 누락 후보 웹검색 출처','',f'검색 대상 {queries}개 · 검색 묶음 {len(research)}개. 한 묶음은 최대 네 카페명으로 검색한 결과입니다.','', '링크는 동일 검색 묶음에서 반환된 후보 출처입니다. 각 카페의 공식 운영 확인 완료를 뜻하지 않습니다. 임시 서명 URL은 제외했고 쿼리·해시는 제거했습니다.','','| 검색 카페명 | 검색 결과 후보 | 원본 목록 |','|---|---|---|']
 from scripts.compare_competitors import cell
 for path in research:
  d=json.loads(path.read_text());urls=' · '.join(f"[{s['title'].replace('|','/').replace('[','').replace(']','')}]({s['url']})" for s in d['sources'][:8]);index.append('| '+cell(' / '.join(d['queries']))+' | '+urls+' | ['+path.name+'](research/'+path.name+') |')
 (P/'research-index.md').write_text('\n'.join(index)+'\n');print('recovery report and research index written')
if __name__=='__main__':main()
