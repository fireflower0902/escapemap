# 전국 크롤러 우선 검토 — 2026-11-15

## 검토 기준

- 연결된 회색: 크롤러 설정은 있으나 해당 지점의 유효한 검증 기록이 없음.
- 미연결 회색: 지점에 매핑된 크롤러가 없음. 크롤링 불가능·폐업 확정이라는 뜻이 아님.
- 주황색: 오류·시간 초과·누락 등 확인 필요. 원인과 실행 범위를 확인한 뒤 판정.
- 오늘부터 2일 후까지 공개 예약 정보를 읽기 전용 메모리 DB에서 검사. 운영 Firestore에 쓰지 않음.
- 통과는 응답·파싱·데이터 형식 검사 결과이며 실제 예약 성공이나 모든 테마 완전성을 보증하지 않음.
- 표의 시간대는 조회한 날짜 전체의 합계이며 예약 가능과 마감 모두 포함.

## 수정한 사항

- 예약 현황 필드 누락, 마감 목록 조회 실패를 빈자리로 간주하던 경로 차단.
- 범위를 알 수 없는 과거 실패 기록을 전체 지점에 적용하지 않도록 수정.
- 지점 ID를 명시해 단독 검증 가능. 중첩된 검증 결과도 현황판에서 읽도록 수정.
- 마스터키·룸엘의 24~29시 심야 시간은 다음 날 시각으로 비교하며 원래 영업일·시간 표기 유지.

## 예약 오표시 방지 검사

| 수집기 | 결과 | 테마 | 시간대 | 사유 |
|---|---|---:|---:|---|
| sync_oasisescape_db | error | 4 | 0 | RuntimeError: 마감 목록 조회 실패: tm=5, date=2026-11-16 |
| sync_rememberesc_db | smoke_pass | 10 | 273 |  |
| sync_reverseesc_db | error | 0 | 0 | ValueError: 테마/예약완료 목록 응답을 모두 확인하지 못했습니다. |
| sync_escapers_db | smoke_pass | 5 | 36 |  |
| sync_zeroworld_db | needs_review | 0 | 0 | [WARN] CSRF 획득 실패 https://www.zerohongdae.com: <urlopen error [Errno 61] Connection refused>; [WARN] 슬롯 조회 실패 https://www.zerohongdae.com 2026-11-15: <urlopen error [Errno 61] Connection refused> |

리버스 기존 공개 API에서 reserv_data가 빠졌으며 홈페이지 예약 링크는 sh.zeroworldesc.co.kr을 가리킴. 새 예약처의 지점 일치 및 파서 확인 전 빈자리 생성 보류. 오아시스 null 응답도 공식 의미 확인 전 빈 목록으로 해석하지 않음.

## 기존 주황색 지점

검사 완료 74곳 / 기준 93곳. 결과: needs_review 27곳, smoke_pass 46곳, error 1곳.

룸사 19곳은 공개 목록만 수집 가능한 것으로 앞서 확인되어 시간대 재시도에서 제외. 확인 필요 상태 유지.

| 카페 / 지점 | ID | 결과 | 테마 | 시간대 | 예약 가능 | 수집기 | 오류 / 참고 |
|---|---|---|---:|---:|---:|---|---|
| 강남점  | 1551717206 | needs_review | 0 | 0 | 0 | sync_xcape_db | [WARN] GET /merchants 실패: HTTP Error 503: Service Unavailable: Back-end server is at capacity; [WARN] cafe 1551717206 Firestore 미존재 — 건너뜀 |
| 골든타임이스케이프 1호점 | 1875954710 | smoke_pass | 4 | 109 | 98 | sync_sinbiweb_db |  |
| 골든타임이스케이프 2호점 | 1591055284 | smoke_pass | 2 | 47 | 32 | sync_sinbiweb_db |  |
| 나의신방 신촌점 | 1521613397 | smoke_pass | 4 | 64 | 18 | sync_sinbiweb_db |  |
| 다이아에그 미스테리인점 | 348406652 | smoke_pass | 4 | 112 | 78 | sync_sinbiweb_db |  |
| 더메이즈 건대점 | 138006966 | needs_review | 0 | 0 | 0 | sync_themazegd_db | [WARN] GET http://www.themazegd.co.kr/bbs/ajax.get_room.php?date=2026-11-15 실패: HTTP Error 404: Not Found; [WARN] GET http://www.themazegd.co.kr/bbs/ajax.get_room.php?date=2026-11-16 실패: HTTP Error 404: Not Found |
| 더코드  | 680681357 | needs_review | 10 | 160 | 0 | sync_thecode_db | [WARN] GET http://www.thecode-escape.com/sub/code_sub03.html?chois_date=2026-11-15&r_thema=esc_09 실패: HTTP Error 500: Internal Server Error; [WARN] GET http://www.thecode-escape.com/sub/code_sub03.html?chois_date=2026-11-15&r_thema=esc_10 실 |
| 더트랩 수유점 | 911063716 | needs_review | 0 | 0 | 0 | sync_thetrapsy_db | 수집 결과 없음 / 파서·예약처 확인 필요 |
| 둠이스케이프 1호점 | 997136500 | needs_review | 0 | 0 | 0 | sync_sinbiweb_db | 수집 결과 없음 / 파서·예약처 확인 필요 |
| 둠이스케이프 2호점 | 1321479252 | needs_review | 0 | 0 | 0 | sync_sinbiweb_db | 수집 결과 없음 / 파서·예약처 확인 필요 |
| 둠이스케이프 DTH점 | 892126854 | needs_review | 0 | 0 | 0 | sync_sinbiweb_db | 수집 결과 없음 / 파서·예약처 확인 필요 |
| 디코드이스케이프 전주점 | 2055691742 | smoke_pass | 8 | 232 | 205 | sync_sinbiweb_db |  |
| 라비린스이스케이프  | 1568417037 | needs_review | 7 | 170 | 133 | sync_sinbiweb_db | [WARN] 세션 획득 실패: <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1081)> |
| 라스트이스케이프 강남점 | 225341934 | needs_review | 0 | 0 | 0 | sync_lastescape_db | [WARN] POST 실패 (date=2026-11-15): <urlopen error [Errno 8] nodename nor servname provided, or not known>; [WARN] POST 실패 (date=2026-11-16): <urlopen error [Errno 8] nodename nor servname provided, or not known> |
| 레다스퀘어 홍대점 | 28201117 | needs_review | 1 | 0 | 0 | sync_ledasquare_db | 수집 결과 없음 / 파서·예약처 확인 필요 |
| 레전드이스케이프 서현점 | 1968639091 | needs_review | 0 | 0 | 0 | sync_sinbiweb_db | 수집 결과 없음 / 파서·예약처 확인 필요 |
| 레전드이스케이프 이천점 | 636394528 | smoke_pass | 5 | 118 | 103 | sync_sinbiweb_db |  |
| 메타이스케이프  | 444802506 | smoke_pass | 4 | 94 | 91 | sync_sinbiweb_db |  |
| 미스터리룸이스케이프 강남점 | 27367643 | needs_review | 0 | 0 | 0 | sync_mysteryroom_db | [WARN] 페이지 로드 실패 a=27 2026-11-15: <urlopen error [Errno 8] nodename nor servname provided, or not known> |
| 방탈출브이 삼덕점 | 858962026 | needs_review | 0 | 0 | 0 | sync_vescape_db | [WARN] GET http://www.v-escape.co.kr/sub/sub03_1.html?R_JIJEM=S1&R_THEMA=A&chois_date=2026-11-15 실패: <urlopen error [Errno 8] nodename nor servname provided, or not known>; [WARN] GET http://www.v-escape.co.kr/sub/sub03_1.html?R_JIJEM=S1&R_ |
| 버스티드  | 1092766492 | smoke_pass | 5 | 92 | 76 | sync_sinbiweb_db |  |
| 비트포비아 명동점 | 1183396756 | error | 0 | 0 | 0 | sync_xphobia_db | RuntimeError: 비트포비아 API 조회 실패: /reservation/ck_no1.php |
| 상상의문 부평점 | 1387240933 | smoke_pass | 4 | 93 | 63 | sync_sinbiweb_db |  |
| 상상의문 분당서현점 | 505122419 | smoke_pass | 6 | 136 | 104 | sync_sinbiweb_db |  |
| 상상의문 수원2호점 | 1121229740 | smoke_pass | 6 | 147 | 101 | sync_sinbiweb_db |  |
| 상상의문 수원점 | 776353707 | smoke_pass | 6 | 159 | 125 | sync_sinbiweb_db |  |
| 셜록홈즈 김포구래점 | 743084847 | smoke_pass | 5 | 131 | 127 | sync_sherlock_db |  |
| 셜록홈즈 노량진점 | 8143798 | needs_review | 0 | 0 | 0 | sync_sherlock_db | 수집 결과 없음 / 파서·예약처 확인 필요 |
| 셜록홈즈 노원점 | 1367009941 | smoke_pass | 6 | 144 | 144 | sync_sherlock_db |  |
| 셜록홈즈 대전은행점 | 472522287 | smoke_pass | 3 | 75 | 56 | sync_sherlock_db |  |
| 셜록홈즈 대학로점 | 270131531 | smoke_pass | 5 | 135 | 123 | sync_sherlock_db |  |
| 셜록홈즈 미사점 | 1954089927 | smoke_pass | 4 | 99 | 93 | sync_sherlock_db |  |
| 셜록홈즈 부산기장정관점 | 2200000001 | needs_review | 0 | 0 | 0 | sync_sherlock_db | 수집 결과 없음 / 파서·예약처 확인 필요 |
| 셜록홈즈 부산아트몰링점 | 1049164175 | smoke_pass | 5 | 99 | 96 | sync_sherlock_db |  |
| 셜록홈즈 부천중동점 | 1620988252 | smoke_pass | 4 | 97 | 93 | sync_sherlock_db |  |
| 셜록홈즈 부평2호점 | 399640253 | smoke_pass | 6 | 177 | 149 | sync_sherlock_db |  |
| 셜록홈즈 부평점 | 2127065864 | smoke_pass | 6 | 156 | 147 | sync_sherlock_db |  |
| 셜록홈즈 분당야탑점 | 1396409942 | needs_review | 0 | 0 | 0 | sync_sherlock_db | 수집 결과 없음 / 파서·예약처 확인 필요 |
| 셜록홈즈 서현점 | 816654453 | smoke_pass | 4 | 97 | 88 | sync_sherlock_db |  |
| 셜록홈즈 성신여대점 | 10098327 | smoke_pass | 4 | 100 | 96 | sync_sherlock_db |  |
| 셜록홈즈 수원역점 | 716398207 | smoke_pass | 7 | 197 | 182 | sync_sherlock_db |  |
| 셜록홈즈 수원인계점 | 1166453549 | smoke_pass | 7 | 221 | 188 | sync_sherlock_db |  |
| 셜록홈즈 수지구청점 | 582885260 | smoke_pass | 5 | 117 | 112 | sync_sherlock_db |  |
| 셜록홈즈 안양범계점 | 1888259527 | smoke_pass | 6 | 186 | 149 | sync_sherlock_db |  |
| 셜록홈즈 용인동백점 | 2021007589 | smoke_pass | 8 | 186 | 178 | sync_sherlock_db |  |
| 셜록홈즈 원주점 | 588118043 | smoke_pass | 5 | 110 | 96 | sync_sherlock_db |  |
| 셜록홈즈 잠실1호점 | 466116790 | smoke_pass | 7 | 182 | 162 | sync_sherlock_db |  |
| 셜록홈즈 잠실새내점 | 45777628 | smoke_pass | 3 | 73 | 63 | sync_sherlock_db |  |
| 셜록홈즈 종각점 | 462553617 | smoke_pass | 5 | 110 | 106 | sync_sherlock_db |  |
| 셜록홈즈 천안1호점 | 27583768 | smoke_pass | 5 | 141 | 129 | sync_sherlock_db |  |
| 셜록홈즈 천안2호점 | 908334376 | smoke_pass | 4 | 111 | 94 | sync_sherlock_db |  |
| 셜록홈즈 평택점 | 728789378 | smoke_pass | 5 | 145 | 140 | sync_sherlock_db |  |
| 스피키지  | 1825220691 | smoke_pass | 2 | 39 | 39 | sync_sinbiweb_db |  |
| 시크릿코드 홍대직영점 | 280887856 | needs_review | 0 | 0 | 0 | sync_secretcode_db | [WARN] GET http://www.secret-code.co.kr/sub_02/sub02_1.html?JIJEM=S3&chois_date=2026-11-15 실패: <urlopen error [Errno 8] nodename nor servname provided, or not known>; [WARN] GET http://www.secret-code.co.kr/sub_02/sub02_1.html?JIJEM=S3&choi |
| 어클락이스케이프  | 1425246210 | smoke_pass | 7 | 203 | 180 | sync_sinbiweb_db |  |
| 에필로그  | 458997744 | smoke_pass | 5 | 109 | 68 | sync_sinbiweb_db |  |
| 엑소더스 강남1호점 | 103606910 | needs_review | 0 | 0 | 0 | sync_sinbiweb_db | 수집 결과 없음 / 파서·예약처 확인 필요 |
| 제주방탈출 제원점 | 1554942559 | smoke_pass | 5 | 120 | 119 | sync_sinbiweb_db |  |
| 지니어스이스케이프  | 1394599334 | needs_review | 5 | 0 | 0 | sync_geniusescape_db | [WARN] POST http://www.geniusescape.kr/sub/03_1_1.html (A/2026-11-15) 실패: HTTP Error 403: Forbidden; [WARN] POST http://www.geniusescape.kr/sub/03_1_1.html (B/2026-11-15) 실패: HTTP Error 403: Forbidden |
| 코난방탈출 구로디지털단지역점 | 1757443413 | needs_review | 0 | 0 | 0 | sync_conanescape_db | [WARN] POST http://conanescape.kr/sub/sub03_01.php 실패: <urlopen error [Errno 8] nodename nor servname provided, or not known>; [WARN] POST http://conanescape.kr/sub/sub03_01.php 실패: <urlopen error [Errno 8] nodename nor servname provided, o |
| 코드헌터 강남점 | 1213158520 | smoke_pass | 3 | 61 | 55 | sync_sinbiweb_db |  |
| 콜드케이스 인하대점 | 455356224 | smoke_pass | 5 | 140 | 121 | sync_sinbiweb_db |  |
| 큐방탈출카페 일산점 | 351145232 | smoke_pass | 10 | 190 | 190 | sync_sinbiweb_db |  |
| 큐브이스케이프 홍대점 | 27413260 | needs_review | 0 | 0 | 0 | sync_cubeescape_db | 수집 결과 없음 / 파서·예약처 확인 필요 |
| 탈출브라더스 영등포점 | 1045036053 | smoke_pass | 6 | 138 | 133 | sync_sinbiweb_db |  |
| 플레이더월드 강남점 | 841734382 | needs_review | 0 | 0 | 0 | sync_playtheworld_etc_db | [WARN] GET /v2/shops/m86eCeH4SoNCqVVX 실패: HTTP Error 500: Internal Server Error |
| 플레이더월드 대전은행점 | 1224388097 | needs_review | 0 | 0 | 0 | sync_playtheworld_etc_db | [WARN] GET /v2/shops/U9cZjMPWeVZbij6X 실패: HTTP Error 500: Internal Server Error |
| 플레이더월드 동성로점 | 76631654 | needs_review | 0 | 0 | 0 | sync_playtheworld_etc_db | [WARN] GET /v2/shops/bF9P9ARTDcgrbcDR 실패: HTTP Error 500: Internal Server Error |
| 플레이더월드 부평점 | 1637776603 | needs_review | 0 | 0 | 0 | sync_playtheworld_etc_db | [WARN] GET /v2/shops/fsGEtW3EXJiFXVCZ 실패: HTTP Error 500: Internal Server Error |
| 플레이더월드 평택점 | 767938268 | needs_review | 0 | 0 | 0 | sync_playtheworld_etc_db | [WARN] GET /v2/shops/eerYSTbbLAQnqZv3 실패: HTTP Error 500: Internal Server Error |
| 해피앤딩 홍대점 | 1541961243 | smoke_pass | 4 | 120 | 108 | sync_sinbiweb_db |  |
| 호텔레토 성수점 | 1168819420 | needs_review | 0 | 0 | 0 | sync_sinbiweb_db | 수집 결과 없음 / 파서·예약처 확인 필요 |
| 황금열쇠 건대점 | 1271584354 | smoke_pass | 2 | 56 | 33 | sync_sinbiweb_db |  |
| 황금열쇠 동성로점 | 1958696909 | smoke_pass | 5 | 119 | 100 | sync_sinbiweb_db |  |

## 기존 연결된 회색 지점

검사 완료 157곳 / 기준 157곳. 결과: needs_review 34곳, smoke_pass 122곳, error 1곳.

| 카페 / 지점 | ID | 결과 | 테마 | 시간대 | 예약 가능 | 수집기 | 오류 / 참고 |
|---|---|---|---:|---:|---:|---|---|
| 개꿀이스케이프  | 212176813 | needs_review | 0 | 0 | 0 | sync_playtheworld_etc_db | [WARN] GET /v2/shops/XEcM52tKWqDCUFCG 실패: HTTP Error 500: Internal Server Error |
| 건대2호  | 361428621 | needs_review | 0 | 0 | 0 | sync_xcape_db | [WARN] GET /merchants 실패: HTTP Error 503: Service Unavailable: Back-end server is at capacity; [WARN] GET /reservations 실패: HTTP Error 503: Service Unavailable: Back-end server is at capacity |
| 건대점  | 27354377 | needs_review | 0 | 0 | 0 | sync_xcape_db | [WARN] GET /merchants 실패: HTTP Error 503: Service Unavailable: Back-end server is at capacity; [WARN] cafe 27354377 Firestore 미존재 — 건너뜀 |
| 겟어웨이방탈출카페  | 1871864524 | smoke_pass | 4 | 76 | 56 | sync_escapetop_db |  |
| 괴담저장소 한강대점 | 617331855 | smoke_pass | 4 | 36 | 14 | sync_escapetop_db |  |
| 구미랑방탈출카페  | 202030183 | smoke_pass | 4 | 88 | 83 | sync_escapetop_db |  |
| 꿈소풍 안산1호점 | 1767938917 | smoke_pass | 7 | 148 | 143 | sync_dreampicnic_db |  |
| 나비잠 1호점 | 713424921 | smoke_pass | 5 | 125 | 82 | sync_escapetop_db |  |
| 나비잠 2호점 | 704757588 | smoke_pass | 3 | 73 | 51 | sync_escapetop_db |  |
| 넥스트에디션 건대 보네르관 | 1108129560 | smoke_pass | 1 | 31 | 26 | sync_nextedition_db |  |
| 넥스트에디션 건대2호점 | 287949141 | smoke_pass | 7 | 195 | 145 | sync_nextedition_db |  |
| 넥스트에디션 부천점 | 1678997732 | smoke_pass | 4 | 116 | 112 | sync_nextedition_db |  |
| 넥스트에디션 분당서현점 | 635335984 | smoke_pass | 6 | 132 | 106 | sync_nextedition_db |  |
| 넥스트에디션 신림점 | 1224056973 | smoke_pass | 5 | 146 | 137 | sync_nextedition_db |  |
| 넥스트에디션 잠실점 | 1460924995 | smoke_pass | 4 | 102 | 97 | sync_nextedition_db |  |
| 단편선 방탈출 성수점 | 259983085 | smoke_pass | 4 | 103 | 46 | sync_dpsnnn_db |  |
| 더락이스케이프 경성대점 | 1502372343 | smoke_pass | 5 | 105 | 104 | sync_escapetop_db |  |
| 더락이스케이프 부산대점 | 1448469234 | smoke_pass | 5 | 120 | 116 | sync_escapetop_db |  |
| 더락이스케이프 하단점 | 1023995566 | smoke_pass | 5 | 115 | 109 | sync_escapetop_db |  |
| 더리얼방탈출카페 순천점 | 902256384 | smoke_pass | 3 | 75 | 0 | sync_escapetop_db |  |
| 더와이방탈출카페  | 332798783 | smoke_pass | 7 | 202 | 201 | sync_escapetop_db |  |
| 더챕터 홍대점 | 1611418578 | smoke_pass | 2 | 59 | 15 | sync_escapetop_db |  |
| 더패닉방탈출카페  | 1266197087 | smoke_pass | 5 | 295 | 295 | sync_escapetop_db |  |
| 덤앤더머 방탈출카페 서면점 | 28574930 | smoke_pass | 6 | 162 | 162 | sync_dumbndumber_db |  |
| 도어이스케이프 대전유성 NC백화점 | 1836271694 | smoke_pass | 6 | 180 | 164 | sync_doorescape_db |  |
| 도어이스케이프 부평점 | 1460830485 | smoke_pass | 3 | 81 | 62 | sync_doorescape_db |  |
| 도어이스케이프 신논현 레드점 | 765336936 | smoke_pass | 3 | 65 | 57 | sync_doorescape_db |  |
| 도어이스케이프 신논현 블루점 | 2058736611 | smoke_pass | 2 | 35 | 32 | sync_doorescape_db |  |
| 도어이스케이프 안산점 | 27609271 | smoke_pass | 6 | 156 | 149 | sync_doorescape_db |  |
| 도어이스케이프 이수역점 | 190103388 | smoke_pass | 4 | 90 | 83 | sync_doorescape_db |  |
| 도어이스케이프 홍대점 | 153136502 | smoke_pass | 2 | 53 | 34 | sync_doorescape_db |  |
| 러시아워방탈출 3호점 | 2102768222 | smoke_pass | 3 | 64 | 34 | sync_escapetop_db |  |
| 러시아워방탈출 로드맨션 | 942247508 | smoke_pass | 3 | 72 | 48 | sync_escapetop_db |  |
| 루트이스케이프 수원점 | 857573680 | smoke_pass | 4 | 116 | 116 | sync_movieescape_db |  |
| 루트이스케이프 안산점 | 1609773844 | smoke_pass | 5 | 128 | 128 | sync_movieescape_db |  |
| 루트이스케이프 평택점 | 136198096 | smoke_pass | 5 | 144 | 144 | sync_movieescape_db |  |
| 루팡방탈출카페 1호점 | 1574310774 | smoke_pass | 5 | 130 | 124 | sync_escapetop_db |  |
| 루팡방탈출카페 본점 | 2011481622 | smoke_pass | 6 | 156 | 154 | sync_escapetop_db |  |
| 룸엘이스케이프 당곡점 | 1735229345 | smoke_pass | 1 | 25 | 25 | sync_roomlescape_db |  |
| 룸엘이스케이프 신림2호점 | 782208965 | smoke_pass | 1 | 29 | 26 | sync_roomlescape_db |  |
| 룸엘이스케이프 신림점 | 628138029 | needs_review | 4 | 0 | 0 | sync_roomlescape_db | 수집 결과 없음 / 파서·예약처 확인 필요 |
| 룸익스케이프 인디고블루점 | 690123759 | needs_review | 0 | 0 | 0 | sync_playtheworld_etc_db | [WARN] GET /v2/shops/mpu5Jvr5DzANeHRL 실패: HTTP Error 500: Internal Server Error |
| 룸즈에이 광주수완2호점 | 1544141348 | needs_review | 0 | 0 | 0 | sync_playtheworld_etc_db | [WARN] GET /v2/shops/N22seZPUEfSe1jKQ 실패: HTTP Error 500: Internal Server Error |
| 룸즈에이 부평점 | 802938757 | needs_review | 0 | 0 | 0 | sync_playtheworld_etc_db | [WARN] GET /v2/shops/HUSqfLY6kenWuw5q 실패: HTTP Error 500: Internal Server Error |
| 리얼월드 커넥트현대 청주점 | 1488706210 | smoke_pass | 2 | 76 | 76 | sync_escapetop_db |  |
| 마스터키 건대점 | 671151862 | smoke_pass | 3 | 87 | 84 | sync_masterkey_db |  |
| 마스터키 궁동직영점 | 27495854 | smoke_pass | 5 | 125 | 118 | sync_masterkey_db |  |
| 마스터키 노바홍대점 | 1987907479 | smoke_pass | 2 | 47 | 46 | sync_masterkey_db |  |
| 마스터키 동성로2호점 | 2039293420 | smoke_pass | 4 | 125 | 125 | sync_masterkey_db |  |
| 마스터키 동탄프레임점 | 1834906043 | smoke_pass | 4 | 107 | 100 | sync_masterkey_db |  |
| 마스터키 은행직영점 | 27523824 | smoke_pass | 5 | 125 | 110 | sync_masterkey_db |  |
| 마스터키 익산점 | 1727885052 | smoke_pass | 6 | 179 | 179 | sync_masterkey_db |  |
| 마스터키 전주고사점 | 1292714537 | smoke_pass | 8 | 249 | 249 | sync_masterkey_db |  |
| 마스터키 평택점 | 1850589033 | smoke_pass | 6 | 156 | 0 | sync_masterkey_db |  |
| 마스터키프라임 신촌퍼플릭 | 97734177 | smoke_pass | 3 | 86 | 86 | sync_masterkey_db |  |
| 마스터키 프라임청주점 | 164781377 | smoke_pass | 5 | 108 | 104 | sync_masterkey_db |  |
| 마스터키 홍대상수점 | 751793807 | smoke_pass | 6 | 169 | 169 | sync_masterkey_db |  |
| 마스터키 화정점 | 870806933 | smoke_pass | 6 | 129 | 126 | sync_masterkey_db |  |
| 마피아카페 대구동성로점 | 1443757324 | smoke_pass | 1 | 53 | 52 | sync_mafiacafe_db |  |
| 머더파커 건대1호점 | 1016102948 | smoke_pass | 6 | 165 | 136 | sync_murderparker_db |  |
| 머더파커 건대2호점 | 1862264503 | smoke_pass | 3 | 75 | 68 | sync_murderparker_db |  |
| 머더파커 광주점 | 3373516 | smoke_pass | 5 | 139 | 136 | sync_murderparker_db |  |
| 머더파커 대구1호점 | 1788375645 | smoke_pass | 5 | 114 | 113 | sync_murderparker_db |  |
| 머더파커 대구2호점 | 1450292038 | smoke_pass | 4 | 90 | 57 | sync_murderparker_db |  |
| 머더파커 부산점 | 1250945647 | smoke_pass | 5 | 130 | 119 | sync_murderparker_db |  |
| 머더파커 양산점 | 583591672 | smoke_pass | 5 | 115 | 115 | sync_murderparker_db |  |
| 머더파커 익산점 | 130115446 | smoke_pass | 4 | 92 | 76 | sync_murderparker_db |  |
| 머더파커 잠실점 | 1796437751 | smoke_pass | 3 | 78 | 67 | sync_murderparker_db |  |
| 머더파커 전주2호점 | 605934214 | smoke_pass | 3 | 55 | 49 | sync_murderparker_db |  |
| 머더파커 전주3호점 | 399727939 | smoke_pass | 6 | 145 | 130 | sync_murderparker_db |  |
| 머더파커 홍대1호점 | 1604521778 | smoke_pass | 5 | 124 | 110 | sync_murderparker_db |  |
| 머더파커 WOW 홍대점 | 64956517 | smoke_pass | 4 | 78 | 69 | sync_murderparker_db |  |
| 미스터리담  | 1436082735 | needs_review | 0 | 0 | 0 | sync_escapetop_db | 수집 결과 없음 / 파서·예약처 확인 필요 |
| 미스터리룸이스케이프 홍대2호점 | 727312827 | needs_review | 0 | 0 | 0 | sync_mysteryroom_db | [WARN] 페이지 로드 실패 a=44 2026-11-15: <urlopen error [Errno 8] nodename nor servname provided, or not known> |
| 방탈출브이 공평점 | 1254330051 | needs_review | 0 | 0 | 0 | sync_vescape_db | [WARN] GET http://www.v-escape.co.kr/sub/sub03_1.html?R_JIJEM=S2&R_THEMA=A&chois_date=2026-11-15 실패: <urlopen error [Errno 8] nodename nor servname provided, or not known>; [WARN] GET http://www.v-escape.co.kr/sub/sub03_1.html?R_JIJEM=S2&R_ |
| 방탈출추리존  | 2138163704 | smoke_pass | 5 | 105 | 104 | sync_escapetop_db |  |
| 브레이크아웃이스케이프 해운대본점 | 170158027 | smoke_pass | 8 | 229 | 220 | sync_escapetop_db |  |
| 브레이크아웃이스케이프 홍대점 | 451924760 | smoke_pass | 5 | 118 | 90 | sync_escapetop_db |  |
| 브레인이스케이프 광주점 | 1459848720 | smoke_pass | 6 | 165 | 159 | sync_escapetop_db |  |
| 비트포비아 대학로점 | 1432484184 | error | 0 | 0 | 0 | sync_xphobia_db | RuntimeError: 비트포비아 API 조회 실패: /reservation/ck_no1.php |
| 서울이스케이프룸 대구동성로점 | 892545149 | smoke_pass | 8 | 213 | 163 | sync_seoulescaperoom_db |  |
| 서울이스케이프룸 부산서면점 | 310013350 | smoke_pass | 5 | 142 | 139 | sync_seoulescaperoom_db |  |
| 서울이스케이프룸 인천부평점 | 427897815 | smoke_pass | 1 | 32 | 4 | sync_seoulescaperoom_db |  |
| 수원방탈출연구소  | 1458988059 | smoke_pass | 4 | 39 | 36 | sync_escapetop_db |  |
| 수원점  | 1599918263 | needs_review | 0 | 0 | 0 | sync_xcape_db | [WARN] GET /merchants 실패: HTTP Error 503: Service Unavailable: Back-end server is at capacity; [WARN] GET /reservations 실패: HTTP Error 503: Service Unavailable: Back-end server is at capacity |
| 숨바꼭질 2호점 | 923379950 | smoke_pass | 4 | 60 | 33 | sync_escapetop_db |  |
| 숨바꼭질 3호점 | 632336157 | smoke_pass | 2 | 40 | 22 | sync_escapetop_db |  |
| 시그널헌터 광교중앙점 | 215947527 | smoke_pass | 5 | 126 | 117 | sync_escapetop_db |  |
| 시크릿도어 군포산본점 | 163640808 | smoke_pass | 2 | 36 | 36 | sync_escapetop_db |  |
| 싸인이스케이프 강남시티점 | 1245109855 | smoke_pass | 2 | 35 | 25 | sync_signescape_db |  |
| 싸인이스케이프 상수점 | 2400000001 | smoke_pass | 1 | 19 | 10 | sync_signescape_db |  |
| 싸인이스케이프 성대역점 | 570522076 | smoke_pass | 3 | 63 | 61 | sync_signescape_db |  |
| 싸인이스케이프 인계시티점 | 115701517 | needs_review | 0 | 0 | 0 | sync_signescape_db | [WARN] GET http://www.signescape.com/sub/sub03_1.html?R_JIJEM=S1&chois_date=2026-11-15&R_THEMA=A 실패: HTTP Error 500: Internal Server Error; [WARN] GET http://www.signescape.com/sub/sub03_1.html?R_JIJEM=S1&chois_date=2026-11-15&R_THEMA=B 실패: |
| 씨이스케이프  | 657876723 | smoke_pass | 1 | 17 | 15 | sync_escapetop_db |  |
| 어디든가게  | 570199530 | smoke_pass | 12 | 770 | 770 | sync_escapetop_db |  |
| 에베레스트이스케이프  | 164116124 | smoke_pass | 1 | 18 | 17 | sync_escapetop_db |  |
| 에피소드방탈출 강남점 | 1277196871 | smoke_pass | 3 | 75 | 70 | sync_escapetop_db |  |
| 에피소드방탈출 분당점 | 1411698841 | smoke_pass | 5 | 131 | 126 | sync_escapetop_db |  |
| 엑스이스케이프 홍대상상마당점 | 1654390566 | smoke_pass | 4 | 146 | 146 | sync_xescape_db |  |
| 오늘의한페이지 방탈출카페  | 2012633570 | needs_review | 0 | 0 | 0 | sync_playtheworld_etc_db | [WARN] GET /v2/shops/rjwaaAh3mVPbCdHA 실패: HTTP Error 500: Internal Server Error |
| 오늘탈출 고양점 | 300855776 | needs_review | 0 | 0 | 0 | sync_escapetop_db | 수집 결과 없음 / 파서·예약처 확인 필요 |
| 원타임방탈출카페 전주신시가지점 | 625095198 | smoke_pass | 5 | 151 | 133 | sync_escapetop_db |  |
| 월투월방탈출  | 763904207 | needs_review | 0 | 0 | 0 | sync_escapetop_db | 수집 결과 없음 / 파서·예약처 확인 필요 |
| 이스케이프샾  | 1000900386 | needs_review | 0 | 0 | 0 | sync_playtheworld_etc_db | [WARN] GET /v2/shops/Jmas3Q5kHnfxQhFZ 실패: HTTP Error 500: Internal Server Error |
| 이스케이프샾 건대점 | 2016521022 | needs_review | 0 | 0 | 0 | sync_playtheworld_etc_db | [WARN] GET /v2/shops/tS5DajzuHqnhrnjH 실패: HTTP Error 500: Internal Server Error |
| 이스케이프월드  | 901719185 | smoke_pass | 3 | 20 | 11 | sync_escapetop_db |  |
| 이스케이프탑 대전점 | 1973717836 | smoke_pass | 6 | 159 | 147 | sync_escapetop_db |  |
| 이스케이프탑 부산점 | 665041653 | smoke_pass | 7 | 174 | 164 | sync_escapetop_db |  |
| 이스케이프탑 수원점 | 836762242 | smoke_pass | 8 | 198 | 192 | sync_escapetop_db |  |
| 이스케이프탑 울산점 | 284779798 | smoke_pass | 8 | 198 | 191 | sync_escapetop_db |  |
| 이스케이프탑 창원점 | 1097124167 | smoke_pass | 7 | 174 | 166 | sync_escapetop_db |  |
| 인스테이지방탈출  | 1415278100 | smoke_pass | 1 | 18 | 8 | sync_escapetop_db |  |
| 제로월드 롯데월드점 | 890251040 | needs_review | 0 | 0 | 0 | sync_zeroworld_db | [WARN] CSRF 획득 실패 https://zerolotteworld.com: <urlopen error [Errno 8] nodename nor servname provided, or not known>; [WARN] 슬롯 조회 실패 https://zerolotteworld.com 2026-11-15: <urlopen error [Errno 8] nodename nor servname provided, or not kno |
| 지구별방탈출 대구점 | 7690632 | smoke_pass | 1 | 7 | 0 | sync_jigobyeol_db |  |
| 지구별방탈출 홍대라스트시티점 | 399012410 | smoke_pass | 8 | 67 | 6 | sync_jigobyeol_db |  |
| 찰리이스케이프  | 1682203426 | smoke_pass | 2 | 11 | 6 | sync_escapetop_db |  |
| 체셔캣방탈출카페  | 1831030495 | needs_review | 0 | 0 | 0 | sync_escapetop_db | 수집 결과 없음 / 파서·예약처 확인 필요 |
| 카타르시스이스케이프 서면점 | 1358303820 | smoke_pass | 3 | 86 | 84 | sync_escapetop_db |  |
| 카페 1542251042  | 1542251042 | needs_review | 0 | 0 | 0 | sync_playtheworld_etc_db | [WARN] GET /v2/shops/p8j31JZAgRCJWnUc 실패: HTTP Error 500: Internal Server Error; [WARN] cafe 1542251042 Firestore 미존재 — 건너뜀 |
| 카페 27329834  | 27329834 | needs_review | 0 | 0 | 0 | sync_playtheworld_etc_db | [WARN] GET /v2/shops/Z5dmpFTTqzaSqaa4 실패: HTTP Error 500: Internal Server Error; [WARN] cafe 27329834 Firestore 미존재 — 건너뜀 |
| 카페 912842418  | 912842418 | needs_review | 0 | 0 | 0 | sync_playtheworld_etc_db | [WARN] GET /v2/shops/vG4SZyg8jem2YYuo 실패: HTTP Error 500: Internal Server Error; [WARN] cafe 912842418 Firestore 미존재 — 건너뜀 |
| 코드미스터리  | 1865048385 | smoke_pass | 5 | 135 | 95 | sync_escapetop_db |  |
| 큐브이스케이프 대구점 | 2100000004 | needs_review | 0 | 0 | 0 | sync_cubeescape_db | 수집 결과 없음 / 파서·예약처 확인 필요 |
| 큐브이스케이프 대전둔산점 | 167846502 | needs_review | 0 | 0 | 0 | sync_cubeescape_db | 수집 결과 없음 / 파서·예약처 확인 필요 |
| 큐브이스케이프 수유점 | 4331171 | needs_review | 0 | 0 | 0 | sync_cubeescape_db | 수집 결과 없음 / 파서·예약처 확인 필요 |
| 큐브이스케이프 인천점 | 27564986 | needs_review | 0 | 0 | 0 | sync_cubeescape_db | 수집 결과 없음 / 파서·예약처 확인 필요 |
| 큐브이스케이프 잠실점 | 2100000001 | needs_review | 0 | 0 | 0 | sync_cubeescape_db | 수집 결과 없음 / 파서·예약처 확인 필요 |
| 큐브이스케이프 전주점 | 27522878 | needs_review | 0 | 0 | 0 | sync_cubeescape_db | 수집 결과 없음 / 파서·예약처 확인 필요 |
| 큐브이스케이프 천호점 | 1857201893 | needs_review | 0 | 0 | 0 | sync_cubeescape_db | 수집 결과 없음 / 파서·예약처 확인 필요 |
| 크라임씬카페 퍼즐팩토리 성수점 | 2022859547 | smoke_pass | 4 | 76 | 27 | sync_puzzlefactory_db |  |
| 키이스케이프 강남 더오름  | 400448256 | smoke_pass | 2 | 54 | 28 | sync_keyescape_db |  |
| 키이스케이프 로그인1  | 99889048 | smoke_pass | 2 | 66 | 7 | sync_keyescape_db |  |
| 키이스케이프 로그인2  | 320987184 | smoke_pass | 3 | 90 | 28 | sync_keyescape_db |  |
| 키이스케이프 메모리컴퍼니  | 459642234 | smoke_pass | 3 | 96 | 0 | sync_keyescape_db |  |
| 키이스케이프 스테이션  | 298789057 | smoke_pass | 3 | 138 | 16 | sync_keyescape_db |  |
| 키이스케이프 부산점 | 1637143499 | smoke_pass | 5 | 85 | 80 | sync_keyescape_db |  |
| 키이스케이프 우주라이크점 | 916422770 | smoke_pass | 2 | 57 | 26 | sync_keyescape_db |  |
| 키이스케이프 전주점 | 48992610 | smoke_pass | 4 | 128 | 110 | sync_keyescape_db |  |
| 키이스케이프 홍대점 | 200411443 | smoke_pass | 3 | 75 | 48 | sync_keyescape_db |  |
| 타임이스케이프 창원점 | 27607543 | smoke_pass | 6 | 165 | 164 | sync_escapetop_db |  |
| 트랩코리아 삼산점 | 27575809 | smoke_pass | 4 | 84 | 83 | sync_escapetop_db |  |
| 판타지아방탈출카페  | 100018735 | smoke_pass | 3 | 56 | 49 | sync_escapetop_db |  |
| 플레이포인트랩 해운대 블루오션스테이션점 | 1559912469 | smoke_pass | 6 | 146 | 116 | sync_masterkey_db |  |
| 플레이포인트랩 두정점 | 2030700012 | smoke_pass | 6 | 170 | 152 | sync_masterkey_db |  |
| 플레이포인트랩 부산서면오리진점 | 1397923384 | smoke_pass | 3 | 72 | 59 | sync_masterkey_db |  |
| 플레이포인트랩 서면점 | 886826713 | smoke_pass | 4 | 93 | 72 | sync_masterkey_db |  |
| 플레이포인트랩 잠실점 | 967129600 | smoke_pass | 6 | 141 | 141 | sync_masterkey_db |  |
| 플레이포인트랩 홍대점 | 1462418270 | smoke_pass | 3 | 93 | 91 | sync_masterkey_db |  |
| 필더블랭크  | 1719351380 | needs_review | 0 | 0 | 0 | sync_escapetop_db | 수집 결과 없음 / 파서·예약처 확인 필요 |
| 하이드앤시크 쌈지길점 | 1944665207 | needs_review | 0 | 0 | 0 | sync_escapetop_db | 수집 결과 없음 / 파서·예약처 확인 필요 |
| 하이드앤시크 홍대점 | 554838835 | needs_review | 0 | 0 | 0 | sync_escapetop_db | 수집 결과 없음 / 파서·예약처 확인 필요 |
| 하일이스케이프  | 1124781432 | smoke_pass | 4 | 97 | 95 | sync_escapetop_db |  |
| 후즈데어  | 1872221698 | smoke_pass | 3 | 126 | 1 | sync_keyescape_db |  |
| ESC방탈출카페 천안점 | 27559974 | smoke_pass | 5 | 140 | 135 | sync_escbangtalul_db |  |
| ESC방탈출카페 평택점 | 1314964065 | smoke_pass | 6 | 121 | 94 | sync_escbangtalul_db |  |
| gateoftime 광주점 | 1393764461 | needs_review | 9 | 0 | 0 | sync_playtheworld_etc_db | [WARN] GET /v2/shops/YybEYe16XjtuRV7S 실패: HTTP Error 500: Internal Server Error |
| gateoftime 대구동성로점 | 929019886 | needs_review | 5 | 0 | 0 | sync_playtheworld_etc_db | [WARN] GET /v2/shops/HiJhoQFf8ThapVG3 실패: HTTP Error 500: Internal Server Error |

## 미연결 40곳 — 예약처 예비 확인

아래는 등록 URL의 응답 상태와 공개 링크 점검이다. 접속 실패만으로 폐업 판정하지 않으며, HTTP 응답만으로 정상 운영 판정하지 않는다. 지도·단축 URL은 공식 예약 URL 확보 대상으로 분류했다.

| 카페 / 지점 | ID | 등록/도착 URL | 확인 결과 | 페이지 제목 | 공개 예약 링크 |
|---|---|---|---|---|---|
| 강릉방탈출카페  | 1501825629 | http://place.map.kakao.com/1501825629 | 공식 예약 URL 확인 필요 |  |  |
| 고한 시티써커스  | 461296797 | http://place.map.kakao.com/461296797 | 공식 예약 URL 확인 필요 |  |  |
| 광주방탈출카페 식스센스  | 786094598 | http://place.map.kakao.com/786094598 | 공식 예약 URL 확인 필요 |  |  |
| 다락방방탈출카페 청주직영점 | 964420524 | http://place.map.kakao.com/964420524 | 공식 예약 URL 확인 필요 |  |  |
| 다락방 안양점 | 442981346 | http://www.darockesc.com/ | 접속 확인 실패: URLError |  |  |
| 더도어즈이스케이프  | 302959300 | http://www.thedoorsescape.com/ | 공개 페이지 응답 확인; 운영·예약 파서 별도 검증 필요 |  |  |
| 도파민방탈출  | 1900192470 | http://place.map.kakao.com/1900192470 | 공식 예약 URL 확인 필요 |  |  |
| 두잇이스케이프  | 716654663 | http://place.map.kakao.com/716654663 | 공식 예약 URL 확인 필요 |  |  |
| 드림이스케이프  | 40766168 | http://place.map.kakao.com/40766168 | 공식 예약 URL 확인 필요 |  |  |
| 레드런 천안점 | 77278349 | http://place.map.kakao.com/77278349 | 공식 예약 URL 확인 필요 |  |  |
| 레드런 천호점 | 1331705130 | https://naver.me/xbjXQceE | 공식 예약 URL 확인 필요 |  |  |
| 리얼이스케이프챌린지  | 27369058 | http://www.rec-escape.com/ | 공개 페이지 응답 확인; 운영·예약 파서 별도 검증 필요 | 리얼 이스케이프 첼린지 |  |
| 리즌방탈출  | 776644226 | http://place.map.kakao.com/776644226 | 공식 예약 URL 확인 필요 |  |  |
| 미션브레이크 CGV용산아이파크몰점 | 888192913 | https://www.xphobia.net/ | 접속 확인 실패: URLError |  |  |
| 방탈출 뉴케이스  | 1516889516 | http://place.map.kakao.com/1516889516 | 공식 예약 URL 확인 필요 |  |  |
| 방탈출 미로  | 1560724472 | http://place.map.kakao.com/1560724472 | 공식 예약 URL 확인 필요 |  |  |
| 방탈출고  | 1992606174 | http://place.map.kakao.com/1992606174 | 공식 예약 URL 확인 필요 |  |  |
| 방탈출카페 일상탈출 안양일번가점 | 255097329 | http://place.map.kakao.com/255097329 | 공식 예약 URL 확인 필요 |  |  |
| 브레이크아웃 광안  | 1495650283 | https://busan.breakoutescapegame.com/en/ | 접속 확인 실패: URLError |  |  |
| 비트포비아 동성로점 | 997297045 | https://www.xphobia.net/ | 접속 확인 실패: URLError |  |  |
| 비트포비아 신림점 | 1647497159 | https://www.xphobia.net/ | 접속 확인 실패: URLError |  |  |
| 스키피지  | 367178846 | https://speakeasyescape.co.kr/ | 접속 확인 실패: URLError |  |  |
| 시그널헌터 가로수길점 | 401872428 | https://www.signalhunter.co.kr/ | 접속 확인 실패: URLError |  |  |
| 시그널헌터 동탄점 | 1945917235 | http://signalhunter.co.kr/ | 공개 페이지 응답 확인; 운영·예약 파서 별도 검증 필요 |  |  |
| 신나는방탈출  | 1019017181 | http://place.map.kakao.com/1019017181 | 공식 예약 URL 확인 필요 |  |  |
| 안흥여관  | 2143447304 | http://place.map.kakao.com/2143447304 | 공식 예약 URL 확인 필요 |  |  |
| 알카트래즈방탈출카페  | 660859780 | http://alcatraz.co.kr/ | 공개 페이지 응답 확인; 운영·예약 파서 별도 검증 필요 | 알카트라즈 방탈출카페 임시 페이지 |  |
| 어메이즈드 3호점 | 2138418097 | https://amazed.co.kr/ | 접속 확인 실패: URLError |  |  |
| 언리미티드 이스케이프  | 166623372 | http://unlimited-escape.com/ | 접속 확인 실패: URLError |  |  |
| 위드방탈출카페  | 2000674643 | http://withescaper.com/ | 접속 확인 실패: URLError |  |  |
| 이스케이프존 강대점 | 230738333 | http://www.cc-escapezone.co.kr/kr/main.php | 공개 페이지 응답 확인; 운영·예약 파서 별도 검증 필요 | 이스케이프존 | http://www.cc-escapezone.co.kr/kr/webpage.php |
| 카오스이스케이프  | 431508316 | http://chaosesc.co.kr/ | 공개 페이지 응답 확인; 운영·예약 파서 별도 검증 필요 | 카오스이스케이프-방탈출카페 |  |
| 코드나인방탈출카페  | 1741880444 | http://place.map.kakao.com/1741880444 | 공식 예약 URL 확인 필요 |  |  |
| 코드이스케이프 가로수길점 | 522639283 | http://www.code-escape-garosu.com/ | 공개 페이지 응답 확인; 운영·예약 파서 별도 검증 필요 | 코드이스케이프 가로수길2 |  |
| 키즈인더룸 평촌점 | 52252534 | https://kidsintheroom.com/ | 접속 확인 실패: URLError |  |  |
| 파노라마 부산  | 422613765 | https://naver.me/FutFZ0bm | 공식 예약 URL 확인 필요 |  |  |
| 파라박스  | 123477337 | https://parabox.kr/ | 접속 확인 실패: URLError |  |  |
| 페르소나  | 79137052 | http://place.map.kakao.com/79137052 | 공식 예약 URL 확인 필요 |  |  |
| 플레이더월드 건대점 | 746135486 | https://playthe.world/ | 접속 확인 실패: URLError |  |  |
| 할리갈리인더룸방탈출시즌2  | 1252080396 | http://place.map.kakao.com/1252080396 | 공식 예약 URL 확인 필요 |  |  |

## 후속 작업

1. DNS·404·500·503·접근 제한·테마 없음·시간대 없음으로 원인을 나눠 공식 예약처 재확인.
2. 미연결 목록은 주소·지점·공식 링크로 기존 등록과 중복 여부부터 확인 후 연결.
3. 룸사 및 접근 제한 사이트는 목록 정보와 실시간 예약 가능 여부를 분리 유지.
4. 이 검토 결과는 로컬 코드와 테스트 기록이며 배포·운영 스케줄 반영은 별도.

최종 현황판 조회에서 Firestore 로딩 실패가 관측됨. 화면은 경고와 저장 수치 미확인 상태로 전환되며, 이 보고서의 수치는 운영 DB 저장량이 아니라 독립 검사 결과임.

검증: 백엔드 회귀 테스트 41개, 프런트 현황판 테스트 9개, TypeScript 검사 통과. 기존 test_engines.py는 pytest 미설치로 unittest 전체 탐색 시 import 실패하여 위 41개 명시 실행과 구분한다.

원본: priority-review-2026-11-15/ 하위 baseline.json, safety/, orange/, gray_connected/, recovery/, unconnected.json.
