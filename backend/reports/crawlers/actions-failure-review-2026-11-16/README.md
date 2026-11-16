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
