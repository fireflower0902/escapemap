# 상세 검토 대상 28개 — 2026-11-21 3차

시작: 운영405개 / 정기310개 / 미편입95개. 수집기·예약처 상세 검토 후보28개를 대상으로 공식 화면, 기존 수집기, 웹 검색과 필요한 실제 브라우저 확인을 수행했다. 예약처 미확정 항목은 검색 범위를 명시하고 구현 가능 여부를 확정하지 않았다.

## 이번 실제 구현

|카페|변경|공개 시간표 저장|
|---|---|---|
|룸엘 신림점|공식 data-otherurl의 네이버 사업자164665로 전환. 상세 주소 수정.|4테마·157슬롯,7일|
|위센트 이머시브 홍대점(구 레다스퀘어)|공식 레다 메뉴가 연결한 wecent.kr 공개 GET availability 수집기 신규 구현. 상호·현행3층 주소 수정.|1테마·48슬롯,7일|

두 곳 모두 Supabase 저장 후 GitHub 읽기 전용 수집 검증 성공. 정기 대상312개, 미편입93개로 반영. 미해결26개의 현황판에는 보류 이유를 저장했다. 구현/조사한28개와 실제 정기편입2개를 구분한다.

## 확인한 원인과 남은 작업

- 네이버4곳: 실제 브라우저에서 로그인 페이지로 이동. 익명 GraphQL은 테마0개. 로그인 계정 사용 없이 보류.
- 비트포비아4곳: 공식 허브의 2026-08-31 가맹점 예약 서비스 종료 공지. 매장 폐업을 뜻하지 않음.
- 셜록3곳·레전드서현·싸인인계: 현재 공식 예약 지점 목록에서 해당 지점을 확인하지 못함. 다른 지점으로 치환하지 않음.
- REC: 외부 Bookeo 중첩 위젯 전용 어댑터는 여전히 추가 개발·검증이 필요하다. 구현 불가능으로 결론 내리지 않았다.
- 뉴케이스: 이미 수집 중인 공식 레코드와 동일 주소. 중복 수집 대신 레코드 통합 검토 대상이다.

## 검증

- [룸엘 GitHub](https://github.com/fireflower0902/escapemap/actions/runs/44906028519)
- [위센트 GitHub](https://github.com/fireflower0902/escapemap/actions/runs/44906743858)
- 회귀107개 + subtest16개 통과. 종전과 동일하게 호환되지 않는 기존 test_engines.py 제외.
- 위센트는 휴무·예약완료·지난시간·오픈전과 예약가능을 구별하고 날짜/지점/테마/상태가 불명확하면 저장을 거부한다.

## 28개 개별 결과

|카페ID|카페/지점|결과|근거/추가 필요 사항|
|---|---|---|---|
|115701517|싸인이스케이프 인계시티점|branch_not_listed|공식 예약 탭은 S2·S5·S6·S7이며 기존 인계시티 S1은 없음. S2 성대역 시간표를 인계시티에 붙이지 않음. [공식/참조](http://www.signescape.com/sub/sub03_1.html)|
|1183396756|비트포비아 명동점|booking_service_ended|공식 허브에 가맹점 온라인 예약 서비스가 2026-08-31 종료됐다고 공지. 매장 폐업을 뜻하지 않으며 대체 지점 예약처 확인 필요. [공식/참조](https://xphobia.net/)|
|1231888375|리버스이스케이프 향남점|source_api_unavailable|홈·예약 화면과 공식 reservation.js는 열리지만, JS에서 호출하는 GET /service/get_data는 연결 종료. 예약 완료 피드가 없어 빈자리 추정 금지. [공식/참조](http://reverseesc.com/reservation.html) [공식/참조](http://reverseesc.com/static/js/reservation.js)|
|1252080396|할리갈리인더룸방탈출시즌2|official_source_unconfirmed|검색으로 네이버 단축 링크 GV2ktDvG를 찾았고 place37589034로 연결 확인. 현재 공식 시간표 사업자 ID는 확정하지 못함. [공식/참조](https://naver.me/GV2ktDvG)|
|1396409942|셜록홈즈 분당야탑점|branch_not_listed|공식 현행 예약 메뉴에서 해당 지점명·번호를 확인하지 못했고, 해당 지점 재검증도 테마0개. 다른 지점으로 임의 치환하지 않음. [공식/참조](https://sherlock-holmes.co.kr/reservation/)|
|1432484184|비트포비아 대학로점|booking_service_ended|공식 허브에 가맹점 온라인 예약 서비스가 2026-08-31 종료됐다고 공지. 매장 폐업을 뜻하지 않으며 대체 지점 예약처 확인 필요. [공식/참조](https://xphobia.net/)|
|1436082735|미스터리담|source_requires_login|공개 GraphQL 재검증은 테마0개. 실제 브라우저 접속은 nid.naver.com 로그인으로 이동. 익명 정기 수집은 보류. [공식/참조](https://booking.naver.com/)|
|1516889516|방탈출 뉴케이스|duplicate_record|서울 광진구 아차산로191은 이미 정기 수집 중인 official_xcape_nc(뉴케이스 건대3호점)와 일치. 별도 중복 수집 추가 없이 레코드 통합 검토 대상. [공식/참조](https://xcape.kr/booking/nc)|
|1647497159|비트포비아 신림점|booking_service_ended|공식 허브에 가맹점 온라인 예약 서비스가 2026-08-31 종료됐다고 공지. 매장 폐업을 뜻하지 않으며 대체 지점 예약처 확인 필요. [공식/참조](https://xphobia.net/)|
|1719351380|필더블랭크|source_requires_login|공개 GraphQL 재검증은 테마0개. 실제 브라우저 접속은 nid.naver.com 로그인으로 이동. 익명 정기 수집은 보류. [공식/참조](https://booking.naver.com/)|
|1772504569|리버스이스케이프 안산점|source_api_unavailable|홈·예약 화면과 공식 reservation.js는 열리지만, JS에서 호출하는 GET /service/get_data는 연결 종료. 예약 완료 피드가 없어 빈자리 추정 금지. [공식/참조](http://reverseesc.com/reservation.html) [공식/참조](http://reverseesc.com/static/js/reservation.js)|
|1831030495|체셔캣방탈출카페|source_requires_login|공개 GraphQL 재검증은 테마0개. 실제 브라우저 접속은 nid.naver.com 로그인으로 이동. 익명 정기 수집은 보류. [공식/참조](https://booking.naver.com/)|
|1968639091|레전드이스케이프 서현점|branch_not_listed|공식 예약 지점 선택에는 이천점(2)만 존재. 기존 서현점(1) 공개 시간표 미확인. [공식/참조](http://legendescape.com/layout/res/home.php?go=rev.make)|
|212176813|개꿀이스케이프|permission_required|공식 사이트의 허가된 요청 외 크롤링 금지 안내가 있음. 인증 조작이나 차단 우회 없이 자동 편입 보류. [공식/참조](https://doghoneyescape.com/)|
|2200000001|셜록홈즈 부산기장정관점|branch_not_listed|공식 현행 예약 메뉴에서 해당 지점명·번호를 확인하지 못했고, 해당 지점 재검증도 테마0개. 다른 지점으로 임의 치환하지 않음. [공식/참조](https://sherlock-holmes.co.kr/reservation/)|
|255097329|방탈출카페 일상탈출 안양일번가점|official_source_unconfirmed|검색 결과에서 동일 주소의 현행 구인 공고는 확인했으나 공식 공개 시간표 링크는 미확정. 운영 중이라는 추정만으로 수집 성공 처리하지 않음. [공식/참조](https://www.albamon.com/jobs/detail/120302851)|
|27369058|리얼이스케이프챌린지|external_widget|공식 예약은 Bookeo 중첩 외부 위젯. 실제 브라우저에서도 시간표가 접근성 DOM에 노출되지 않음. 전용 위젯 읽기 어댑터의 추가 구현·검증 필요(구현 불가능으로 확정하지 않음). [공식/참조](https://www.rec-escape.com/book-now)|
|28201117|레다스퀘어 홍대점|implemented|레다 공식 아바타 예약 링크가 wecent.kr로 전환. 위센트 공개 availability GET 수집기를 새로 구현해 1테마·48슬롯 Supabase 저장 및 GitHub 검증 성공. [공식/참조](https://ledasquare.com/layout/res/home.php?go=rev.make) [공식/참조](https://wecent.kr/reservation)|
|431508316|카오스이스케이프|no_slots_published|확인한 날짜 공식 6테마의 마감 셀에는 시각이 없음. 마감 시각을 위치로 추정하지 않음. 가용 링크가 나오는 날짜와 별도 전체 시간표 제공 여부 확인 필요. [공식/참조](http://chaosesc.co.kr/2019/bbs/board.php?bo_table=reservation&select=2026-11-23)|
|461296797|고한 시티써커스|consent_gate|정선군 공식 예약처를 찾았으나 시간표 선택 단계는 개인정보 수집·이용 동의 전에는 반환되지 않음. 안내된 운영시간을 실제 가용 시간대로 생성하지 않음. [공식/참조](https://www.jeongseon.go.kr/mystery/booking/reservation)|
|628138029|룸엘이스케이프 신림점|implemented|공식 테마 목록의 data-otherurl이 네이버 164665로 전환됨. 4개 테마·157슬롯 Supabase 저장 및 GitHub 검증 성공. [공식/참조](http://www.roomlescape.com/rev.theme.list.php) [공식/참조](https://booking.naver.com/booking/12/bizes/164665)|
|680681357|더코드|source_api_unavailable|기존 공식 도메인은 이번 상세 요청에서 연결/DNS 실패. 현재 예약 가능한 테마 코드를 검증하지 못함. [공식/참조](http://www.thecode-escape.com/sub/code_sub03.html)|
|763904207|월투월방탈출|source_requires_login|공개 GraphQL 재검증은 테마0개. 실제 브라우저 접속은 nid.naver.com 로그인으로 이동. 익명 정기 수집은 보류. [공식/참조](https://booking.naver.com/)|
|79137052|페르소나|official_source_unconfirmed|광주 문화전당로35번길2 기록은 검색되지만 공식 현행 예약처를 확보하지 못함. 이름이 같은 다른 지역 매장으로 치환하지 않음. |
|8143798|셜록홈즈 노량진점|branch_not_listed|공식 현행 예약 메뉴에서 해당 지점명·번호를 확인하지 못했고, 해당 지점 재검증도 테마0개. 다른 지점으로 임의 치환하지 않음. [공식/참조](https://sherlock-holmes.co.kr/reservation/)|
|888192913|미션브레이크 CGV용산아이파크몰점|remote_access_denied|비트포비아 공식 허브가 연결한 CGV 미션브레이크 예약 페이지는 HTTP403 및 비정상 접속 제한 안내. 우회하지 않고 보류. [공식/참조](https://cgv.co.kr/act/actvt/00004)|
|911063716|더트랩 수유점|official_source_unconfirmed|공식 자체 예약 목록은 네이버 예약 이용 안내로 전환. 공개 홈페이지/검색에서 현재 네이버 사업자 ID를 확정하지 못함. [공식/참조](http://www.thetrapsy.co.kr/re/)|
|997297045|비트포비아 동성로점|booking_service_ended|공식 허브에 가맹점 온라인 예약 서비스가 2026-08-31 종료됐다고 공지. 매장 폐업을 뜻하지 않으며 대체 지점 예약처 확인 필요. [공식/참조](https://xphobia.net/)|

완료는 현재 확인 가능한 두 곳의 편입과28개 사유 분류를 뜻한다. 남은26개가 모두 해결되었거나 모두 수집 불가능하다는 뜻이 아니다.
