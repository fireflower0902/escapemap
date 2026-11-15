# 방픽 Cloudflare 테스트 배포

- 테스트 Worker: `escapemap-preview`
- URL: https://escapemap-preview.reviewhyun.workers.dev
- 기존 `escapemap` Worker 및 Vercel 배포는 변경하지 않음.
- 웹앱: Next.js + OpenNext / DB: Supabase PostgreSQL의 private `escape` 스키마.
- Workers는 Hyperdrive 바인딩으로 DB 조회. 쿼리 캐시는 끄고 수집 성공·90분 신선도 검사를 유지.
- 크롤러와 개발 현황판의 Python 실행은 로컬 또는 GitHub Actions에서 수행. 공개 개발 API는 404.

## Cloudflare Git 빌드 설정

- Root directory: `frontend`
- Build command: `npm run build:cloudflare`
- Deploy command: `npm run deploy:cloudflare -- --env preview` (별도 테스트 Worker 배포)
- Node.js: 22 이상 (`node:util.parseEnv` 필요)
- 브랜치: `feat/cloudflare-bangpick`

Git 자동 배포는 해당 Worker의 이름과 Wrangler 환경의 이름을 맞춰 연결한다. 테스트 Worker `escapemap-preview`에 Git 연동을 설정하는 것을 권장한다. 기존 `escapemap` Worker에서 정식 배포할 때는 Deploy command를 `npm run deploy:cloudflare`로 설정할 수 있으나, 테스트 확인 후에 진행한다.

Hyperdrive ID는 `wrangler.jsonc`에 기록한다. DB 비밀번호는 Hyperdrive에 저장되며 소스에 기록하지 않는다. 로컬 `.env*` 파일은 빌드 중 임시로 제외하고 종료 시 복원한다. `NEXT_PUBLIC_*` 공개 설정만 빌드에 전달한다. Firebase 로그인 설정이 필요한 경우 해당 공개 환경변수를 Cloudflare 빌드 변수로 등록해야 한다. 예약 조회에는 Firebase 관리자 키가 필요 없다.

## 검증

2026-11-15: Workers 배포 및 강남 45개 카페·148개 테마, 부산 25개 카페·110개 테마 조회 200 확인. 강남 엑스케이프 지점은 실제 크롤러로 5개 테마·141개 슬롯(3일)을 갱신했다. 로컬 Workers의 직접 TLS 접속 오류는 Hyperdrive 사용으로 해결했다. 프론트엔드 21개·백엔드 unittest 52개 통과. 기존 외부사이트 통합 pytest 모듈은 pytest 미설치로 실행 대상에서 제외했다.

프론트엔드 `npm run test:teum`, `npm run test:dashboard`, `npm run test:supabase` 및 Workers 번들 빌드를 수행한다. 배포 후 `/api/search?date=YYYY-MM-DD&area=gangnam`가 200을 반환하고 `/api/dev/crawlers`가 404인지 확인한다. 시간표가 오래되면 카페·테마만 표시하고 이전 빈자리를 현재 예약 가능으로 표시하지 않는다.

## 크롤러 배포

GitHub Actions의 `SUPABASE_DATABASE_URL` Secret을 사용한다. 스케줄 워크플로는 main에 반영된 뒤 자동 실행된다. 테스트 브랜치 푸시만으로 main의 예약 크롤러가 전환되지는 않는다.

## Cloudflare 전용 운영 전환 (2026-11-15)

- main에 `vercel.json`의 `git.deploymentEnabled=false` 적용: Vercel Git 자동 배포 중지.
- 운영 Worker `escapemap`, main의 frontend 디렉터리에서 `npm run build:cloudflare`, `npm run deploy:cloudflare`.
- 정기 수집은 검증된 232개 지점을 `data/scheduled-crawlers.json`으로 관리. 매시 17분에 오늘~2일 후, 매일 00:43 KST에 오늘~14일 후 조회.
- 8개 분할, 동시 4개 작업, 작업당 2개 지점으로 수집량 제한. 실패 지점을 숨기지 않고 작업 실패 및 7일 보관 artifact에 기록.
- 지점별 실패는 다른 지점의 성공 결과를 취소하지 않음. 웹앱은 성공 및 90분 이내 수집 정보만 사용.
- Cloudflare Git 빌드 설정 API는 현재 OAuth 권한으로 403이므로 대시보드의 명령 설정 저장이 필요.

## 7일 운영 범위

오늘을 포함한 7일(오늘~6일 후)을 매시 7분·37분에 수집한다. CLI의 `--days 6`은 오늘을 포함하면 7일이다. 14일 확장 스케줄은 중지한다. 월 단위 API도 요청한 날짜 범위만 DB에 게시한다. GitHub artifact에는 분할 요약과 실패 지점 보고서만 7일 보관하여 중복 저장을 줄인다.

수집 이력 및 과거 시간표는 7일 이전 자료를 정리하고, Playwright 호환성을 위해 Ubuntu 24.04 러너를 사용한다.

## 수집 범위와 실행 분할 확대

미수집 173곳을 대상으로 기존 시간표 크롤러 연결 114곳을 지점별 재검증하고, 48곳의 7일치 저장을 추가 확인해 정기 대상은 280곳으로 확대했다. 목록 전용 19곳과 미연결 40곳은 별도 분류해 보고서에 남겼다. 클레버타운은 미래 날짜의 한정 테마 등록 누락을 수정했다.

작업은 12개 분할/동시 6개/작업당 2개 지점이며 같은 사이트의 동시 요청을 작업 내부에서 제한한다. 작업 제한은 13분이다. 최대 두 차례 실행을 기준으로 30분 내 처리 여유를 확보하는 구성이나 GitHub 러너 대기시간은 보장되지 않는다. 시간 제한에 걸리면 미완료 지점이 생길 수 있어 성공 여부와 저장 지점 수를 함께 확인해야 한다. 직전 232곳/8분할 실행은 27분 9초였고 215곳 성공, 17곳 로컬 보완이었다. 새 280곳 구성이 실제로 30분 내 완료되는지는 별도 실행 측정이 필요하다.
