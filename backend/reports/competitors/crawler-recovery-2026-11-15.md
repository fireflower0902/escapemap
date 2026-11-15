# 전국 카페 추가 및 크롤링 재검증

갱신: 2026-11-15T11:49:15.755750+09:00

## DB 반영 결과

| 항목 | 이번 작업 전 | 현재 | 증가 |
|---|---|---|---|
| 등록 카페 | 365 | 411 | 46 |
| 등록 테마 | 1170 | 1522 | 352 |

비활성·이전 등록 항목도 포함한 동일 기준의 전체 DB 수입니다. 신규 등록은 공식 주소·지점/테마 목록으로 확인한 항목이며, 경쟁사 이름만으로 추가하지 않았습니다.

이전 작업 21곳을 포함한 공식 검증 등록 67곳 중, 실제 조회·파싱 검증 통과 48곳, 검토 필요 19곳입니다. 룸즈에이 신규 19곳은 공식 목록/테마 확인을 마쳤지만 시간대 검증은 보류입니다.

## 신규/공식 검증 지점별 수집 현황

| 카페 | DB 테마 | 테스트 테마 | 테스트 시간대 | 조회 날짜 | 결과 |
|---|---|---|---|---|---|
| 셜록홈즈 광명철산점 | 6 | 6 | 120 | 2026-11-15, 2026-11-16 | smoke_pass |
| 셜록홈즈 구리점 | 5 | 5 | 75 | 2026-11-15, 2026-11-16 | smoke_pass |
| 셜록홈즈 구월인천점 | 6 | 6 | 96 | 2026-11-15, 2026-11-16 | smoke_pass |
| 셜록홈즈 군산수송점 | 5 | 5 | 104 | 2026-11-15, 2026-11-16 | smoke_pass |
| 셜록홈즈 뉴부천점 | 5 | 5 | 91 | 2026-11-15, 2026-11-16 | smoke_pass |
| 셜록홈즈 뉴안양점 | 5 | 5 | 75 | 2026-11-15, 2026-11-16 | smoke_pass |
| 셜록홈즈 대구동성로점 | 4 | 4 | 68 | 2026-11-15, 2026-11-16 | smoke_pass |
| 셜록홈즈 대전둔산점 | 5 | 5 | 95 | 2026-11-15, 2026-11-16 | smoke_pass |
| 셜록홈즈 동탄점 | 6 | 6 | 94 | 2026-11-15, 2026-11-16 | smoke_pass |
| 셜록홈즈 송도트리플점 | 7 | 7 | 134 | 2026-11-15, 2026-11-16 | smoke_pass |
| 셜록홈즈 수원역2호점 | 8 | 8 | 154 | 2026-11-15, 2026-11-16 | smoke_pass |
| 셜록홈즈 아산점 | 6 | 6 | 106 | 2026-11-15, 2026-11-16 | smoke_pass |
| 셜록홈즈 안산점 | 6 | 6 | 109 | 2026-11-15, 2026-11-16 | smoke_pass |
| 셜록홈즈 여수점 | 7 | 7 | 119 | 2026-11-15, 2026-11-16 | smoke_pass |
| 셜록홈즈 용인역북점 | 5 | 5 | 90 | 2026-11-15, 2026-11-16 | smoke_pass |
| 셜록홈즈 의정부점 | 4 | 4 | 64 | 2026-11-15, 2026-11-16 | smoke_pass |
| 셜록홈즈 청주점 | 5 | 5 | 95 | 2026-11-15, 2026-11-16 | smoke_pass |
| 상상락원 잠실점 | 10 | 10 | 140 | 2026-11-15, 2026-11-16 | smoke_pass |
| 상상락원 익산 원광대점 | 10 | 10 | 153 | 2026-11-15, 2026-11-16 | smoke_pass |
| 상상락원 전주객사점 | 10 | 10 | 150 | 2026-11-15, 2026-11-16 | smoke_pass |
| 상상락원 전주 한옥마을점 | 6 | 6 | 84 | 2026-11-15, 2026-11-16 | smoke_pass |
| 비밀의화원 서면점 | 7 | 7 | 162 | 2026-11-15, 2026-11-16 | smoke_pass |
| 비밀의화원 대학로점 | 6 | 6 | 108 | 2026-11-15, 2026-11-16 | smoke_pass |
| 비밀의화원 건대점 | 6 | 6 | 110 | 2026-11-15, 2026-11-16 | smoke_pass |
| 비밀의화원 동성로점 | 7 | 7 | 146 | 2026-11-15, 2026-11-16 | smoke_pass |
| 비밀의화원 광주점 | 7 | 7 | 116 | 2026-11-15, 2026-11-16 | smoke_pass |
| 비밀의화원 시네마틱 혜화점 | 5 | 5 | 82 | 2026-11-15, 2026-11-16 | smoke_pass |
| 비밀의화원 전주점 | 3 | 3 | 42 | 2026-11-15, 2026-11-16 | smoke_pass |
| 엑스케이프 건대1호점 | 4 | 4 | 80 | 2026-11-15, 2026-11-16 | smoke_pass |
| 엑스크라임 건대2호점 | 5 | 5 | 94 | 2026-11-15, 2026-11-16 | smoke_pass |
| 뉴케이스 건대3호점 | 3 | 3 | 60 | 2026-11-15, 2026-11-16 | smoke_pass |
| 엑스케이프 강남점 | 5 | 5 | 94 | 2026-11-15, 2026-11-16 | smoke_pass |
| 엑스케이프 수원점 | 5 | 5 | 106 | 2026-11-15, 2026-11-16 | smoke_pass |
| 포인트나인 강남점 | 4 | 4 | 60 | 2026-11-15, 2026-11-16 | smoke_pass |
| 포인트나인 건대점 | 3 | 3 | 63 | 2026-11-15, 2026-11-16 | smoke_pass |
| 포인트나인 홍대점 | 2 | 2 | 66 | 2026-11-15, 2026-11-16 | smoke_pass |
| 제로월드 김포본점 | 11 | 11 | 169 | 2026-11-15, 2026-11-16 | smoke_pass |
| 제로월드 다이브 건대점 | 3 | 3 | 60 | 2026-11-15, 2026-11-16 | smoke_pass |
| 플레이33 홍대점 | 1 | 1 | 28 | 2026-11-15, 2026-11-16 | smoke_pass |
| 플레이33 대전점 | 5 | 5 | 106 | 2026-11-15, 2026-11-16 | smoke_pass |
| 플레이33 수원점 | 1 | 1 | 23 | 2026-11-15, 2026-11-16 | smoke_pass |
| 코드케이 강남점 | 15 | 15 | 300 | 2026-11-15, 2026-11-16 | smoke_pass |
| 코드케이 홍대점 | 2 | 2 | 30 | 2026-11-15, 2026-11-16 | smoke_pass |
| 위욜 | 3 | 3 | 46 | 2026-11-15, 2026-11-16 | smoke_pass |
| 돌로이스케이프 | 4 | 4 | 54 | 2026-11-15, 2026-11-16 | smoke_pass |
| 이룸에이트 | 6 | 6 | 120 | 2026-11-15, 2026-11-16 | smoke_pass |
| 룸즈에이 강남점 | 5 | 5 | 0 |  | needs_review |
| 룸즈에이 대학로점 | 5 | 5 | 0 |  | needs_review |
| 룸즈에이 안양범계점 | 3 | 3 | 0 |  | needs_review |
| 룸즈에이 일산 웨스턴돔점 | 5 | 5 | 0 |  | needs_review |
| 룸즈에이 의정부점 | 5 | 5 | 0 |  | needs_review |
| 룸즈에이 수원역점 | 4 | 4 | 0 |  | needs_review |
| 룸즈에이 수원역 2호점 | 4 | 4 | 0 |  | needs_review |
| 룸즈에이 대전둔산점 | 6 | 6 | 0 |  | needs_review |
| 룸즈에이 대전은행점 | 4 | 4 | 0 |  | needs_review |
| 룸즈에이 부산남포점 | 6 | 6 | 0 |  | needs_review |
| 룸즈에이 부산서면점 | 6 | 6 | 0 |  | needs_review |
| 룸즈에이 광주수완점 | 7 | 7 | 0 |  | needs_review |
| 룸즈에이 광주상무점 | 9 | 9 | 0 |  | needs_review |
| 룸즈에이 대구동성로점 | 5 | 5 | 0 |  | needs_review |
| 룸즈에이 동성로2호점 | 6 | 6 | 0 |  | needs_review |
| 룸즈에이 동성로 아카데미점 | 5 | 5 | 0 |  | needs_review |
| 룸즈에이 대구스테이지점 | 5 | 5 | 0 |  | needs_review |
| 룸즈에이 포항점 | 4 | 4 | 0 |  | needs_review |
| 룸즈에이 부평 2호점 | 4 | 4 | 0 |  | needs_review |
| 플러스이스케이프 | 1 | 1 | 5 | 2026-11-15, 2026-11-16 | smoke_pass |
| 익스플로리아이스케이프 수원점 | 2 | 2 | 32 | 2026-11-15, 2026-11-16 | smoke_pass |

테스트 시간대 수는 표시된 날짜의 합계입니다. 조회·파싱 검증 통과는 모든 미래 날짜의 빈자리나 예약 성사를 보장하지 않습니다. 실제 DB에 오늘·내일 예약표를 반영했고, 저장 수치는 개발 현황판에서 테스트 수치와 따로 볼 수 있습니다.

## 기존 오류 사이트 재점검

아래 결과는 각 실행의 범위 기준입니다. 대표 1개 지점의 통과를 전국 지점 전체 통과로 해석하지 않습니다.

| 크롤러 | 최근 실행 | 테마/시간대 | 실행 범위 | 검토·수정 내역 | 공식 사이트 확인 |
|---|---|---|---|---|---|
| sync_rabbithole_db | smoke_pass | 2 / 31 | first configured branch / today + 1 day(s) | 변경된 테마 ID를 공식 선택 상자에서 조회. 신규 행운만물상도 수집. | [https://www.rabbitholeescape.co.kr](https://www.rabbitholeescape.co.kr) (200) |
| sync_thecode_db | needs_review | 10 / 168 | first configured branch / today + 1 day(s) | 일부 테마 조회에서 상위 서버 HTTP 500. 정상 수집분과 서버 실패분 구분 필요. | [http://www.thecode-escape.com](http://www.thecode-escape.com) (200) |
| sync_ledasquare_db | needs_review | 1 / 0 | first configured branch / today + 1 day(s) | 중첩 테마 제목 파서 수정. 공식 테마 조회 성공, 오늘·내일 시간표 응답은 비어 있어 미오픈/운영 일정 추가 확인 필요. | [https://ledasquare.com](https://ledasquare.com) (200) |
| sync_cubeescape_db | needs_review | 0 / 0 | first configured branch / today + 1 day(s) | 현재 도메인은 확인되지만 기존 시간표 파싱은 0건. 인증서/현재 예약 화면 구조 확인 필요. |  |
| sync_secretcode_db | needs_review | 0 / 0 | first configured branch / today + 1 day(s) | 기존 공식 도메인 접속 실패. 검색에서 현재 공식 예약처 확인 불충분. 폐업으로 확정하지 않음. | [http://www.secret-code.co.kr](http://www.secret-code.co.kr) (ConnectionError) |
| sync_codek_db | smoke_pass | 22 / 410 | all configured branches / today + 1 day(s) | R_JIJEM=S2 지점 지정 수정, UTF-8 및 CQ 블록별 파싱. 강남·홍대 추가. | [http://codek5678.cafe24.com](http://codek5678.cafe24.com) (200) / [http://www.code-k.co.kr](http://www.code-k.co.kr) (200) |
| sync_conanescape_db | needs_review | 0 / 0 | first configured branch / today + 1 day(s) | 기존 도메인 DNS/접속 실패. 검색에서 현재 공식 예약처 확인 불충분. 폐업으로 확정하지 않음. | [http://conanescape.kr](http://conanescape.kr) (ConnectionError) |
| sync_deepthinker_db | smoke_pass | 1 / 25 | first configured branch / today + 1 day(s) | 공식 /reservation/ 경로로 수정. CA 번들 경로를 실제 실행과 검증기에 공통 적용. | [https://deepthinker.co.kr](https://deepthinker.co.kr) (200) |
| sync_fantastrick_db | smoke_pass | 4 / 58 | first configured branch / today + 1 day(s) | 폐기된 WordPress 경로 대신 공식 /api/slots 사용. 시간의 영속성 추가. | [https://fantastrick.co.kr](https://fantastrick.co.kr) (200) |
| sync_geniusescape_db | needs_review | 5 / 0 | first configured branch / today + 1 day(s) | 공식 사이트 HTTP 403. 접근 제한을 우회하지 않으며 시간대 확인 필요. | [http://www.geniusescape.kr](http://www.geniusescape.kr) (403) |
| sync_lastescape_db | needs_review | 0 / 0 | first configured branch / today + 1 day(s) | 기존 도메인 접속 실패. 현재 공식 예약처 확인 불충분. 폐업으로 확정하지 않음. | [http://lastescape.co.kr](http://lastescape.co.kr) (ConnectionError) |
| sync_movieescape_cokr_db | smoke_pass | 4 / 70 | first configured branch / today + 1 day(s) | 공식 날짜별 /theme/YYYY-MM-DD/ 구조와 마감 표기 반영. | [https://movieescape.co.kr](https://movieescape.co.kr) (200) |
| sync_mysteryroom_db | needs_review | 0 / 0 | first configured branch / today + 1 day(s) | 기존 등록 도메인 접속 실패. 현재 공식 예약처 추가 확인 필요. | [http://mysteryroomescape.com](http://mysteryroomescape.com) (ConnectionError) |
| sync_orangetb_db | smoke_pass | 24 / 408 | all configured branches / today + 1 day(s) | onclick 속성의 공백·세미콜론 변경을 DOM으로 파싱. 두 지점 검증. | [http://orangetb.com](http://orangetb.com) (200) |
| sync_play33_db | smoke_pass | 10 / 212 | all configured branches / today + 1 day(s) | 공식 선택 상자의 현재 테마 ID 사용. 홍대·대전·수원 지점 추가. | [https://play33.kr](https://play33.kr) (200) |
| sync_playtheworld_etc_db | needs_review | 0 / 0 | first configured branch / today + 1 day(s) | 기존 공개 API 조회에서 500 오류. 등록 플랫폼은 403 응답. 현재 연동/업체별 예약처 확인 필요. | [https://macro.playthe.world](https://macro.playthe.world) (403) |
| sync_themazegd_db | needs_review | 0 / 0 | first configured branch / today + 1 day(s) | 기존 AJAX 경로 404. 홈페이지 존재만으로 시간표 정상으로 판단하지 않음. 현재 예약 경로 확인 필요. | [http://www.themazegd.co.kr](http://www.themazegd.co.kr) (200) |
| sync_thetrapsy_db | needs_review | 0 / 0 | first configured branch / today + 1 day(s) | 기존 /re/l/ 응답은 잘못된 정보 경고. 현재 공개 화면 요청 파라미터 확인 필요. | [http://www.thetrapsy.co.kr](http://www.thetrapsy.co.kr) (200) |
| sync_vescape_db | needs_review | 0 / 0 | first configured branch / today + 1 day(s) | 기존 도메인 접속 실패. 현재 공식 예약처 확인 불충분. 폐업으로 확정하지 않음. | [http://www.v-escape.co.kr](http://www.v-escape.co.kr) (ConnectionError) |
| sync_xcape_db | needs_review | 0 / 0 | first configured branch / today + 1 day(s) | 개편 공식 5개 지점은 sync_xcape_current_db에서 별도 검증. 구 Playtheworld 연동을 현 지점 정상으로 간주하지 않음. | [https://api.xcape-apps.com](https://api.xcape-apps.com) (503) / [https://xcape.co.kr](https://xcape.co.kr) (200) |
| sync_xphobia_db | error | 0 / 0 | first configured branch / today + 1 day(s) | 공식 사이트가 브랜드 허브로 개편되어 구 지점 API 미복구. 미확인 원거리 날짜를 예약 가능으로 추정하던 동작 제거. | [https://www.xphobia.net](https://www.xphobia.net) (200) |
| sync_zeroworld_db | needs_review | 0 / 0 | first configured branch / today + 1 day(s) | 기존 홍대·강남은 sync_zeroworld_current_db에서 새 공식 시스템으로 복구. 기존 롯데월드 사이트는 접속/운영 확인 필요. | [https://www.zerohongdae.com](https://www.zerohongdae.com) (ConnectionError) / [https://zerogangnam.com](https://zerogangnam.com) (ConnectionError) / [https://zerolotteworld.com](https://zerolotteworld.com) (ConnectionError) |
| sync_sinbiweb_db | smoke_pass | 58 / 936 | selected cafe IDs: official_sslone_4, official_sslone_2, official_sslone_1, official_sslone_5, official_pointnine_1, official_pointnine_5, official_pointnine_6, official_weyol, official_dolo, official_eroom8 / today + 1 day(s) | 전 지점 전체 조회 재검증. 정상 수집 지점과 일부 인증서/빈 응답 지점을 분리. 신규 10곳은 별도 선택 범위 검증. | [http://busted.kr](http://busted.kr) (200) / [http://cold-case.co.kr](http://cold-case.co.kr) (200) / [http://dcodeescape.co.kr](http://dcodeescape.co.kr) (200) |

### Sinbiweb 전 지점 검사에서 남은 항목

전체 실행: 177테마 · 2851시간대, 상태 needs_review.

| ID | 카페 | 테스트 테마/시간대 |
|---|---|---|
| 103606910 | 엑소더스 강남1호점 | 0 / 0 |
| 1168819420 | 호텔레토 성수점 | 0 / 0 |
| 997136500 | 둠이스케이프 1호점 | 0 / 0 |
| 1321479252 | 둠이스케이프 2호점 | 0 / 0 |
| 892126854 | 둠이스케이프 DTH점 | 0 / 0 |
| 1968639091 | 레전드이스케이프 서현점 | 0 / 0 |

HTTP 오류·인증서 검증 실패·빈 예약표는 구분해서 확인해야 하며, 사이트가 없어졌거나 예약이 모두 찼다고 단정하지 않습니다.

## 룸즈에이 시간대 검증 보류

- 공식 공개 지점 목록: [룸즈에이](https://roomsa.co.kr/locations), [공개 목록 조회](https://roomsa.co.kr/api/booking/stores).
- 공식 전국 21개 지점·108개 테마를 확인했고, 기존 등록 2곳을 제외한 19곳·98개 테마를 신규 반영했습니다.
- 정상 브라우저에서 예약 화면 보호 메시지가 표시되어 시간대는 미검증입니다. 목록 수집기는 시간대나 예약 가능 여부를 추정하지 않습니다.

## 검색 및 중복 처리

미검증 후보 261개에 대해 웹검색을 수행하고 출처 링크를 보관했습니다. 검색 결과에 나타났다는 이유만으로 운영 확인 완료로 표시하지 않습니다.

아직 공식 지점 연결/운영 확인이 필요한 이름 후보: 225개. 동일 카페의 이름 차이가 포함되어 실제 누락 카페 수와 다릅니다.

- [전체 후보 검색 출처](research-index.md)
- [공식 근거·반영 내역](official-verification.md)
- [경쟁사 비교 요약](README.md)

공식 지점 안내로 확인한 별칭은 verified-aliases.json에 근거와 함께 기록했습니다. 같은 주소의 다른 브랜드나 비슷한 이름만으로 연결하지 않습니다.

## 실행 및 검증

- 실제 사이트 테스트는 Firestore 대신 메모리 DB에 수행합니다. 테스트 자체는 운영 예약표를 쓰지 않습니다.
- 검증된 지점만 별도 실제 동기화로 카페·테마·오늘/내일 예약표를 반영했습니다.
- 신규 크롤러와 수정한 실행 설정은 로컬 코드에 반영했으며 GitHub 배포/실행은 하지 않았습니다.
- 비트포비아의 미확인 원거리 날짜를 전체 예약 가능으로 만들던 동작을 제거했습니다.
- Python CA 번들 경로를 설정해 실제 실행과 테스트의 TLS 기본 설정 차이를 보완했습니다.

검색 출처의 임시 서명 URL은 자동 승인 검토에서 저장이 차단되어 제외했습니다. 공개 조사 링크는 쿼리·해시를 제거해 보관했습니다.
