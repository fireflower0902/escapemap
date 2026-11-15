# Supabase 전환 현황 — 2026-11-15

## 완료

- 카페 414곳·기존 테마 1,522개를 이전하고 기존 ID를 대조했다. 전국 초기 수집으로 테마가 추가되어 현재 1,594개다.
- 로컬 Next.js 검색·메인 미리보기·크롤러 현황판·경쟁사 비교 목록 조회를 Supabase로 연결했다.
- FastAPI 카페·검색·예약 API를 같은 저장소로 연결했다. Firebase 사용자 인증 및 기존 SQLite 사용자/알림 테이블은 유지한다.
- 기존 크롤러의 문서 호출을 PostgreSQL로 연결하는 공통 어댑터를 추가했다.
- 자동 수집용 지점별 실행기: 독립 메모리 검증 → 통과한 지점 결과만 트랜잭션 게시. 실패 지점은 기존 슬롯을 보존하고 실패 상태를 기록한다.
- 메타데이터는 기존 정보와 병합하고, 동일 시간표는 슬롯 변경 쓰기를 생략한다.
- 대표 실제 수집과 전국 초기 수집 완료: 최근 검증을 통과한 232곳, 총 25,009시간대(마감 포함). 주 대상은 오늘부터 2일 후까지이며 월간 API가 반환한 일부 추가 날짜도 포함한다.
- 최초 231곳 통과 후 ESC 평택점의 빈 드롭다운 항목 수집 오류를 수정해 232곳 모두 게시했다. 이 수치는 검증 가능한 대상의 초기 수집 결과이며 전체 카페 414곳의 크롤링 성공을 뜻하지 않는다.
- 서울 시간대·24~29시·역순 응답·예약 가능 링크 필수·실패 시 조회 제외·90분 이상 오래된 결과 조회 제외를 검증했다.
- Supabase 공식 대시보드 배포 CA를 사용해 Python/Node 모두 서버 인증서 및 호스트명을 검증한다.
- 환경변수·Firebase 인증 파일의 Git 추적을 해제했다. 로컬 파일은 유지하며 Git ignore 규칙을 수정했다.

## 배포: 아직 미실행

코드와 **로컬 환경** 전환 및 검증 통과 지점의 전국 초기 수집을 완료했다. Git push, 서비스 배포, GitHub Secrets 변경은 실행하지 않았다. 과거 Firestore 예약표를 현재 빈자리로 복사하지 않았다.

현재 전체 기본정보와 새로 수집한 232곳의 시간표를 조회할 수 있다. 미연결·수집 오류 지점은 확인 필요 상태로 남으며 예약 가능 여부를 추정하지 않는다.

배포에 필요한 설정:

1. GitHub 저장소 Settings → Secrets and variables → Actions → `SUPABASE_DATABASE_URL` 추가. 로컬 `backend/.env`의 같은 값을 사용한다. 채팅에 보내지 않는다.
2. 배포 서버(Next.js 및 Python)에 `CRAWL_STORAGE=supabase`, `SUPABASE_DATABASE_URL`, `CRAWL_FRESHNESS_SECONDS=5400`을 설정한다. `NEXT_PUBLIC_` 접두어를 사용하지 않는다.
3. 코드 배포 후 크롤링 워크플로를 수동 실행해 정기 수집을 가동하고 14일 범위를 갱신한다. 수정한 워크플로는 16개 job 및 기존 지점 분할을 유지하며 새 지점별 실행기를 사용한다.
4. 현황판 저장 수치와 지점별 검증 결과를 대조한다. 실패한 지점은 확인 필요 상태로 유지한다.

## 테이블 확인

Supabase Table Editor에서 스키마를 `public` 대신 **`escape`**로 선택한다.

- `cafes`: 카페·지점 기본정보
- `themes`: 기존 문자열 ID를 유지한 테마 기본정보
- `reservation_slots`: 테마·영업일·시작 분 단위 현재 상태
- `cafe_date_checks`: 마지막 시도/성공·실패 상태·결과 해시
- `crawl_runs`, `crawl_results`: 크롤러 실행과 지점별 결과
- `schema_migrations`: 적용된 마이그레이션 버전·해시

기본정보·수집 테이블은 RLS를 활성화하고 공개 Data API와 분리했다.

시간대는 영업일과 0~1799분(00:00~29:59)을 저장하고 실제 시작 일시를 서울 시간대로 계산한다. 동일 결과의 최신 확인 시각은 슬롯 자체의 `observed_at` 대신 `cafe_date_checks.last_success_at`을 사용한다. 수집 실패·90분 초과 결과는 공개 시간표에 넣지 않는다. 이미 지난 예약 가능 시간은 마감 상태로 표시한다.

## 실행 도구

백엔드 디렉터리 기준:

```sh
.venv/bin/python scripts/check_supabase_connection.py
.venv/bin/python scripts/migrate_to_supabase.py          # 검증만
.venv/bin/python scripts/migrate_to_supabase.py --apply  # 멱등 스키마/기본정보 이전
.venv/bin/python scripts/verify_supabase_storage.py     # 테스트 데이터는 롤백
.venv/bin/python scripts/run_supabase_crawler.py sync_public_extra_db --cafe-id official_plus --days 2
```

`--cafe-id`를 생략하면 해당 수집기에 등록된 지점을 각각 격리해 검증한다. `--start`/`--end`로 목록을 분할할 수 있다. 기존 마이그레이션 SQL은 변경하지 않고 새 번호 파일을 추가한다.

로컬 저장소 선택은 각 서버 환경변수의 `CRAWL_STORAGE`다. `firestore`로 되돌리면 기존 코드 경로를 사용할 수 있지만, 현재 Firestore의 읽기 쿼터 제한은 별개로 남아 있다. 이미 이전한 Supabase 데이터는 삭제하지 않는다.

## 검증 기록

- 백엔드 회귀 테스트 52개, 프런트 테스트 13개.
- 실제 PostgreSQL 트랜잭션 검사: 검사용 데이터 전체 롤백.
- 실제 Next.js API: 전국 405곳·강남 45곳, 현황판 414곳 및 DB 경고 없음. 잘못된 지역·날짜는 400.
- FastAPI 직접 호출: 전국 405곳 및 대표 수집 당시 예약 30시간대 조회. 전국 초기 수집 완료 후 Next.js 검색·현황판에서 오늘 6,125시간대 일치 확인.
- 프로덕션 빌드 검사. 빌드 결과는 개발 서버와 별도 `.next-verify/`에 생성.
- 원본: `migration.json`, `local-cutover.json`, `live-crawler-validation.json`, `storage-verification.json`, `initial-schedules.json`, `../crawlers/supabase/`.

공개 CA 원본: https://supabase-downloads.s3-ap-southeast-1.amazonaws.com/prod/ssl/prod-ca-2021.crt

배포 주소 근거: Supabase 공식 저장소 `apps/studio/hooks/custom-content/custom-content.json`의 `ssl:certificate_url`.
