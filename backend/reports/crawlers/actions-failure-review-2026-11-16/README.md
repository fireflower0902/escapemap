# GitHub Actions 반복 실패 알림 점검 (2026-11-16)

실행: https://github.com/fireflower0902/escapemap/actions/runs/43853490850

- 대상 280곳, 정상 저장 257곳, 실패 23곳 (정상 저장률 91.8%).
- KST 2026-11-16 19:57:55 시작, 20:14:21 종료: 16분 26초.
- 이전 2026-11-15 22:15:33 실행: 16분 8초. 12분할, 작업 최대 6개, 작업당 카페 2개 병렬.
- 12개 작업 모두 완료. 개별 카페 실패 한 건도 작업 종료코드 1로 반환해 전체 실패 알림이 반복됐다.
- 전체 실행 실패여도 정상 검증된 257곳은 Supabase에 저장됐다. 실패한 카페를 정상 수집으로 처리하지 않는다.

## 알림 판정 수정

- 개별 사이트 접근 제한/파싱 오류: 경고로 기록. DB 실패 상태 및 원본 검증 보고서 유지.
- 전체 정상 저장률 90% 미만, DB 오류, 결과 누락/중복, 분류되지 않은 오류: 전체 실패 유지.
- 전국 수집 결과 집계 작업에서 정상/부분 실패/전체 장애와 카페별 사유를 Actions Summary에 표시.
- CLI 수동 검증은 기본 엄격 모드를 유지한다. 정기 수집에만 부분 실패 집계 모드를 사용한다.
- GitHub 전체 메일 알림 설정을 끄지 않는다. 실제 장애 알림은 유지한다.

## 실패 카페

| 수집기 | 카페 ID | 사유 |
|---|---|---|
| sync_secretgarden_db | official_secretgarden_4 | HTTP 403 |
| sync_secretgarden_db | official_secretgarden_5 | HTTP 403 |
| sync_secretgarden_db | official_secretgarden_12 | HTTP 403 |
| sync_xescape_db | 1772415237 | 공개 시간표 0건 |
| sync_secretgarden_db | official_secretgarden_3 | HTTP 403 |
| sync_escapers_db | 969459474 | 수집/검증 경고 |
| sync_escbangtalul_db | 1314964065 | 공개 시간표 0건 |
| sync_secretgarden_db | official_secretgarden_6 | HTTP 403 |
| sync_rememberesc_db | 475592733 | 수집/검증 경고 |
| sync_escbangtalul_db | 2024880532 | 공개 시간표 0건 |
| sync_murderparker_db | 1016102948 | 수집/검증 경고 |
| sync_rememberesc_db | 49858990 | 수집/검증 경고 |
| sync_zescape_db | 1713311920 | 수집/검증 경고 |
| sync_escbangtalul_db | 27559974 | 공개 시간표 0건 |
| sync_thetimeescape_db | 1233678979 | 공개 시간표 0건 |
| sync_roomlescape_db | 1735229345 | 공개 시간표 0건 |
| sync_dumbndumber_db | 203642029 | 수집/검증 경고 |
| sync_roomlescape_db | 596589943 | 공개 시간표 0건 |
| sync_dumbndumber_db | 28574930 | 수집/검증 경고 |
| sync_roomlescape_db | 782208965 | 공개 시간표 0건 |
| sync_secretgarden_db | official_secretgarden_10 | HTTP 403 |
| sync_secretgarden_db | official_secretgarden_11 | HTTP 403 |
| sync_xescape_db | 1654390566 | 공개 시간표 0건 |

## 수정 후 실제 실행 검증

- 실행: https://github.com/fireflower0902/escapemap/actions/runs/43875360037
- KST 2026-11-16 22:23:54 ~ 22:40:13, **16분 19초**.
- GitHub 전체 실행 **Success**. 수집 12개 작업과 집계 1개 작업 모두 정상 종료.
- 카페 결과는 **부분 실패**: 기존 대상 280곳 중 256곳 정상 저장, 24곳 사이트 수집 실패 (91.4%). 실패한 카페를 성공으로 바꾸지 않았다.
- 해당 실행은 알림 수정 커밋 07d8f9c 기준으로 실행됐다. 후속 추가한 두 카페는 로컬 실수집·DB 저장을 검증했고 다음 정기 실행부터 총 282곳 대상이다.
- 수집기 코드 오류/의존성 오류도 DB 오류와 함께 전체 실패로 분류하도록 보강했다.
- 검증: `python -m pytest tests --ignore=tests/test_engines.py -q`: 72 passed, 16 subtests passed. 기존 미완성 `test_engines.py`는 현재 없는 `KeyEscapeEngine` 클래스를 가져오는 기존 오류가 있어 제외했다.
- 테스트에는 기존 보고서 오인 방지, 엄격한 수동 실행, 사이트 경고 보존, 저장 오류/실행 오류/누락된 결과의 Fail 유지가 포함된다.
