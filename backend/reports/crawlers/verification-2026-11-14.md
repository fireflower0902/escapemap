# 2026-11-14 전국 크롤러 점검

크롤러 67개를 각각 실행했습니다. 판정: 조회·파싱 통과 44개, 추가 확인 22개, 실행 오류 1개.

운영 Firestore 대신 메모리에 저장하는 실제 사이트 조회 테스트입니다. 대부분 대표 지점의 오늘·내일을 확인했고, xdungeon은 9개 지점 전체, escapecity는 4개 지점 전체, sinbiweb은 설정 30곳 전체를 조회했습니다. 마피아는 월 단위, 지구별은 오늘만 조회합니다.

테마·시간대 수는 각 테스트 실행의 합계입니다. 통과는 원본 UI와 전체 슬롯 대조, 미등록 지점 탐지 또는 원격 Firestore 쓰기 성공을 뜻하지 않습니다.

## 수정 사항

- 전국 지역 선택, 지역 분류, 검색 API, 자동 크롤링 설정의 서울 제한을 해제했습니다.
- 이스케이프시티의 숨겨진 여러 테마가 한 테마로 섞이는 파서를 수정했습니다. 4개 지점에서 18개 테마·174개 시간대 검증을 통과했습니다.
- 더코드·제트방탈출의 24:00 이후 시간에 의한 크래시를 수정했습니다. 더코드는 일부 테마 API HTTP 500이 별도로 남아 있습니다.
- xphobia 구형 API의 조회 실패가 예약 가능으로 해석되지 않도록 예외를 전파합니다. 기존 예약 API는 새 사이트로 이동되어 별도 재연동이 필요합니다.
- .env의 SKIP_META_WRITES가 실제 쓰기 헬퍼에 적용되도록 설정 경로를 통일했습니다.

## 개별 실행 결과

| 크롤러 | 판정 | 테마 | 시간대 | 확인 사항 |
|---|---|---:|---:|---|
| `sync_aliceescape_db` | 조회·파싱 통과 | 9 | 94 | 시간대 수집 및 형식 검사 통과 |
| `sync_clevertown_db` | 조회·파싱 통과 | 4 | 23 | 시간대 수집 및 형식 검사 통과 |
| `sync_codek_db` | 추가 확인 | 0 | 0 | 응답에서 시간대가 수집되지 않음. 미오픈·구조 변경 등 구분 필요 |
| `sync_conanescape_db` | 추가 확인 | 0 | 0 | [WARN] POST http://conanescape.kr/sub/sub03_01.php 실패: <urlopen error [Errno 8] nodename nor servname provided, or not known> / [WARN] POST http://conanescape.kr/sub/sub03_01.php 실패: <urlopen error [E |
| `sync_cubeescape_db` | 추가 확인 | 0 | 0 | 응답에서 시간대가 수집되지 않음. 미오픈·구조 변경 등 구분 필요 |
| `sync_deepthinker_db` | 추가 확인 | 1 | 13 | [WARN] availableDates 파싱 실패: HTTP Error 404: Not Found |
| `sync_doorescape_db` | 조회·파싱 통과 | 4 | 37 | 시간대 수집 및 형식 검사 통과 |
| `sync_dpsnnn_db` | 조회·파싱 통과 | 2 | 20 | 시간대 수집 및 형식 검사 통과 |
| `sync_dreampicnic_db` | 조회·파싱 통과 | 6 | 69 | 시간대 수집 및 형식 검사 통과 |
| `sync_dumbndumber_db` | 조회·파싱 통과 | 6 | 76 | 시간대 수집 및 형식 검사 통과 |
| `sync_escapecity_db` | 조회·파싱 통과 | 18 | 174 | 시간대 수집 및 형식 검사 통과 |
| `sync_escapedetective_db` | 조회·파싱 통과 | 4 | 36 | 시간대 수집 및 형식 검사 통과 |
| `sync_escapehouse_db` | 조회·파싱 통과 | 8 | 102 | 시간대 수집 및 형식 검사 통과 |
| `sync_escapers_db` | 조회·파싱 통과 | 5 | 45 | 시간대 수집 및 형식 검사 통과 |
| `sync_escapetop_db` | 조회·파싱 통과 | 5 | 49 | 시간대 수집 및 형식 검사 통과 |
| `sync_escbangtalul_db` | 조회·파싱 통과 | 6 | 66 | 시간대 수집 및 형식 검사 통과 |
| `sync_fantastrick_db` | 추가 확인 | 3 | 0 | 응답에서 시간대가 수집되지 않음. 미오픈·구조 변경 등 구분 필요 |
| `sync_frankantique_db` | 조회·파싱 통과 | 3 | 30 | 시간대 수집 및 형식 검사 통과 |
| `sync_geniusescape_db` | 추가 확인 | 5 | 0 | [WARN] POST http://www.geniusescape.kr/sub/03_1_1.html (A/2026-11-14) 실패: HTTP Error 403: Forbidden / [WARN] POST http://www.geniusescape.kr/sub/03_1_1.html (B/2026-11-14) 실패: HTTP Error 403: Forbidde |
| `sync_horrorswitch_db` | 조회·파싱 통과 | 1 | 42 | 시간대 수집 및 형식 검사 통과 |
| `sync_jigobyeol_db` | 조회·파싱 통과 | 6 | 9 | 시간대 수집 및 형식 검사 통과 |
| `sync_keyescape_db` | 조회·파싱 통과 | 3 | 60 | 시간대 수집 및 형식 검사 통과 |
| `sync_lastescape_db` | 추가 확인 | 0 | 0 | [WARN] POST 실패 (date=2026-11-14): <urlopen error [Errno 8] nodename nor servname provided, or not known> / [WARN] POST 실패 (date=2026-11-15): <urlopen error [Errno 8] nodename nor servname provided, or |
| `sync_ledasquare_db` | 추가 확인 | 0 | 0 | 응답에서 시간대가 수집되지 않음. 미오픈·구조 변경 등 구분 필요 |
| `sync_mafiacafe_db` | 조회·파싱 통과 | 1 | 37 | 시간대 수집 및 형식 검사 통과 |
| `sync_masterkey_db` | 조회·파싱 통과 | 6 | 53 | 시간대 수집 및 형식 검사 통과 |
| `sync_movieescape_cokr_db` | 추가 확인 | 4 | 0 | 응답에서 시간대가 수집되지 않음. 미오픈·구조 변경 등 구분 필요 |
| `sync_movieescape_db` | 조회·파싱 통과 | 4 | 36 | 시간대 수집 및 형식 검사 통과 |
| `sync_murderparker_db` | 조회·파싱 통과 | 3 | 26 | 시간대 수집 및 형식 검사 통과 |
| `sync_mysteryroom_db` | 추가 확인 | 0 | 0 | [WARN] 페이지 로드 실패 a=27 2026-11-14: <urlopen error [Errno 8] nodename nor servname provided, or not known> |
| `sync_nextedition_db` | 조회·파싱 통과 | 6 | 71 | 시간대 수집 및 형식 검사 통과 |
| `sync_no1escape_db` | 조회·파싱 통과 | 4 | 38 | 시간대 수집 및 형식 검사 통과 |
| `sync_oasisescape_db` | 조회·파싱 통과 | 4 | 33 | 시간대 수집 및 형식 검사 통과 |
| `sync_orangetb_db` | 추가 확인 | 0 | 0 | [ERROR] 테마 파싱 실패 |
| `sync_panicescape_db` | 조회·파싱 통과 | 3 | 20 | 시간대 수집 및 형식 검사 통과 |
| `sync_play33_db` | 추가 확인 | 2 | 0 | 응답에서 시간대가 수집되지 않음. 미오픈·구조 변경 등 구분 필요 |
| `sync_playescape_db` | 조회·파싱 통과 | 6 | 60 | 시간대 수집 및 형식 검사 통과 |
| `sync_playtheworld_etc_db` | 추가 확인 | 0 | 0 | [WARN] GET /v2/shops/m86eCeH4SoNCqVVX 실패: HTTP Error 500: Internal Server Error / [WARN] GET /v2/shops/eerYSTbbLAQnqZv3 실패: HTTP Error 500: Internal Server Error |
| `sync_puzzlefactory_db` | 조회·파싱 통과 | 4 | 30 | 시간대 수집 및 형식 검사 통과 |
| `sync_rabbithole_db` | 추가 확인 | 1 | 0 | 응답에서 시간대가 수집되지 않음. 미오픈·구조 변경 등 구분 필요 |
| `sync_rememberesc_db` | 조회·파싱 통과 | 10 | 119 | 시간대 수집 및 형식 검사 통과 |
| `sync_reverseesc_db` | 조회·파싱 통과 | 7 | 69 | 시간대 수집 및 형식 검사 통과 |
| `sync_roomescape_db` | 조회·파싱 통과 | 5 | 53 | 시간대 수집 및 형식 검사 통과 |
| `sync_roomlescape_db` | 조회·파싱 통과 | 2 | 22 | 시간대 수집 및 형식 검사 통과 |
| `sync_secretcode_db` | 추가 확인 | 0 | 0 | [WARN] GET http://www.secret-code.co.kr/sub_02/sub02_1.html?JIJEM=S3&chois_date=2026-11-14 실패: <urlopen error [Errno 8] nodename nor servname provided, or not known> / [WARN] GET http://www.secret-cod |
| `sync_seoulesc_db` | 조회·파싱 통과 | 1 | 14 | 시간대 수집 및 형식 검사 통과 |
| `sync_seoulescaperoom_db` | 조회·파싱 통과 | 1 | 14 | 시간대 수집 및 형식 검사 통과 |
| `sync_sherlock_db` | 조회·파싱 통과 | 3 | 32 | 시간대 수집 및 형식 검사 통과 |
| `sync_showroom404_db` | 조회·파싱 통과 | 4 | 49 | 시간대 수집 및 형식 검사 통과 |
| `sync_signescape_db` | 조회·파싱 통과 | 3 | 27 | 시간대 수집 및 형식 검사 통과 |
| `sync_sinbiweb_db` | 추가 확인 | 119 | 1162 | [WARN] 세션 획득 실패: <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1081)> |
| `sync_studioesc_db` | 조회·파싱 통과 | 2 | 20 | 시간대 수집 및 형식 검사 통과 |
| `sync_teraspace_db` | 조회·파싱 통과 | 2 | 20 | 시간대 수집 및 형식 검사 통과 |
| `sync_thecode_db` | 추가 확인 | 10 | 104 | [WARN] GET http://www.thecode-escape.com/sub/code_sub03.html?chois_date=2026-11-14&r_thema=esc_09 실패: HTTP Error 500: Internal Server Error / [WARN] GET http://www.thecode-escape.com/sub/code_sub03.ht |
| `sync_themazegd_db` | 추가 확인 | 0 | 0 | [WARN] GET http://www.themazegd.co.kr/bbs/ajax.get_room.php?date=2026-11-14 실패: HTTP Error 404: Not Found / [WARN] GET http://www.themazegd.co.kr/bbs/ajax.get_room.php?date=2026-11-15 실패: HTTP Error 4 |
| `sync_theqescape_db` | 조회·파싱 통과 | 5 | 75 | 시간대 수집 및 형식 검사 통과 |
| `sync_thetimeescape_db` | 조회·파싱 통과 | 6 | 66 | 시간대 수집 및 형식 검사 통과 |
| `sync_thetrapsy_db` | 추가 확인 | 0 | 0 | 응답에서 시간대가 수집되지 않음. 미오픈·구조 변경 등 구분 필요 |
| `sync_trickescape_db` | 조회·파싱 통과 | 4 | 4 | 시간대 수집 및 형식 검사 통과 |
| `sync_ttescape_db` | 조회·파싱 통과 | 3 | 6 | 시간대 수집 및 형식 검사 통과 |
| `sync_vescape_db` | 추가 확인 | 0 | 0 | [WARN] GET http://www.v-escape.co.kr/sub/sub03_1.html?R_JIJEM=S1&R_THEMA=A&chois_date=2026-11-14 실패: <urlopen error [Errno 8] nodename nor servname provided, or not known> / [WARN] GET http://www.v-es |
| `sync_xcape_db` | 추가 확인 | 0 | 0 | [WARN] GET /merchants 실패: HTTP Error 503: Service Unavailable: Back-end server is at capacity / [WARN] cafe 1551717206 Firestore 미존재 — 건너뜀 |
| `sync_xdungeon_db` | 조회·파싱 통과 | 32 | 698 | 시간대 수집 및 형식 검사 통과 |
| `sync_xescape_db` | 조회·파싱 통과 | 8 | 113 | 시간대 수집 및 형식 검사 통과 |
| `sync_xphobia_db` | 실행 오류 | 0 | 0 | RuntimeError: 비트포비아 API 조회 실패: /reservation/ck_no1.php |
| `sync_zeroworld_db` | 추가 확인 | 0 | 0 | [WARN] CSRF 획득 실패 https://www.zerohongdae.com: <urlopen error [Errno 61] Connection refused> / [WARN] 슬롯 조회 실패 https://www.zerohongdae.com 2026-11-14: <urlopen error [Errno 61] Connection refused> |
| `sync_zescape_db` | 조회·파싱 통과 | 9 | 133 | 시간대 수집 및 형식 검사 통과 |

## 다음 확인 순서

1. xphobia 예약 API 이전 구조 확인.
2. codek, cubeescape, fantastrick 등 HTTP 응답은 있으나 시간대 0개인 사이트의 원본 화면 대조.
3. DNS/연결 실패 사이트의 현재 공식 도메인과 영업 여부 확인.
4. 403·500·503을 반환한 사이트의 접근 방식 및 재현성 확인.
5. 대표 지점만 통과한 브랜드의 나머지 지점 확대 검증.

개발 현황판: `/dev/crawlers`. `README.md`의 실행 방법으로 재검증할 수 있습니다. 새 결과는 현황판에 자동 반영되며 이 보고서는 이번 작업 시점의 스냅샷입니다.
