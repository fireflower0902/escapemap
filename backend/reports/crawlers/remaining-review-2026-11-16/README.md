# 정기 수집 외 123개 카페 후속 검토

점검 시작: 2026-11-16, 반영: 2026-11-17 (KST). 운영 등록 405곳 / 점검 전 정기 수집 282곳.

## 현재 결과

- 기존 연결 수집기 62곳을 개별 재검증하고, 미연결 항목의 공식 예약처·상호·주소·접근 상태를 대조했다.
- **44곳의 수집기를 추가·수정하고 로컬에서 7일 범위 저장 검증**: 222개 테마 / 12,457개 관측 시간대.
- **GitHub에서도 신규 35곳 정상 저장 확인.** 큐브 8곳은 GitHub HTTP 403, 어메이즈드 1곳은 GitHub에서 공식 달력 없는 응답으로 자동 수집 보류.
- 기존 정기 대상에서도 HTTP 403이 확인된 10곳을 같은 기준으로 보류했다.
- **현재 자동 정기 대상: 282 + 신규 35 - 기존 보류 10 = 307곳.** 로컬에서 구현/수집을 확인한 326곳과 구분한다.
- 나머지 기존 미해결 79개 항목과 GitHub 보류 19곳을 유지·표시한다. 삭제·폐업 처리나 빈자리 추정은 하지 않았다.

## 구현 내용

- 네이버 예약 16곳: 공식 상호·주소 대조, 실제 예약 유형 6/12에 맞는 링크 사용.
- 개편된 Reserv 공개 API 13곳: 구 API 500 응답을 새 지점 키/공개 시간표 API로 전환.
- 큐브 8곳: 공식 예약 화면 세션, 시간 범위/상태 태그, 미래 날짜 한정 테마 수정. GitHub 403은 즉시 중단.
- 둠 3곳·라비린스·호텔레토: DOM/24시 이후 시간/세션/HTTPS 주소 이동 수정.
- 어메이즈드 부평3호점·엑소더스 강남1호점의 현재 공식 공개 시간표 수집기 추가.
- DB engine·공식 예약 URL·현황판용 디렉터리 갱신. 시간의문/이스케이프샵 공식 상호 정정.
- 현황판에서 로컬 검증 통과와 별도로 자동 수집 보류 사유 표시. 카페 ID와 기존 데이터는 보존.
- 예약 신청·선점·취소 없이 공개 조회만 수행.

## GitHub 확장 검증

- 실행: https://github.com/fireflower0902/escapemap/actions/runs/43892931835
- KST 2026-11-17 00:07:06 ~ 00:27:22, **20분 16초**.
- 확장 시험 대상 326곳 중 290곳 정상 저장, 36곳 실패. 정상 저장률 90% 미만을 감지해 최종 집계는 Fail. 수집 12개 작업은 정상 종료.
- 이 결과를 근거로 위의 접근 제한/비정상 응답 19곳을 자동 대상에서 보류했다. 정상 저장률 기준을 낮추거나 실패를 성공으로 바꾸지 않았다.

## 상태별 개수 (점검한 123곳)

| 상태 | 개수 |
|---|---:|
| 정기 수집 추가 | 35 |
| 중복 후보 | 5 |
| 기존 수집기 미해결 | 19 |
| 예약처/파서 추가 확인 | 12 |
| 도메인/연결 확인 필요 | 14 |
| 업종 확인 필요 | 2 |
| 보호된 예약 화면 | 21 |
| 예약처 불일치 | 1 |
| 공개 시간표 미확인 | 1 |
| 온라인 시간표 미제공 | 1 |
| 로컬 통과 / GitHub 보류 | 9 |
| 리뉴얼 안내 | 1 |
| 접근 제한 | 2 |

## 수집기를 개선한 44곳

| 카페/지점 | 지역 | 수집기 | 테마 | 관측 시간대 | GitHub |
|---|---|---|---:|---:|---|
| 시간의문 광주점 | gwangju | sync_reserv_public_db | 9 | 588 | 저장 통과 |
| 시간의문 대구동성로점 | daegu | sync_reserv_public_db | 5 | 308 | 저장 통과 |
| 강릉방탈출카페  | gangwon | sync_escapetop_db | 5 | 210 | 저장 통과 |
| 광주방탈출카페 식스센스  | gwangju | sync_escapetop_db | 5 | 248 | 저장 통과 |
| 다락방방탈출카페 청주직영점 | chungbuk | sync_escapetop_db | 4 | 240 | 저장 통과 |
| 더메이즈 건대점 | konkuk | sync_reserv_public_db | 5 | 315 | 저장 통과 |
| 도파민방탈출  | gyeonggi | sync_escapetop_db | 4 | 176 | 저장 통과 |
| 두잇이스케이프  | gyeonggi | sync_escapetop_db | 5 | 230 | 저장 통과 |
| 둠이스케이프 1호점 | incheon | sync_sinbiweb_db | 4 | 204 | 저장 통과 |
| 둠이스케이프 2호점 | incheon | sync_sinbiweb_db | 4 | 188 | 저장 통과 |
| 둠이스케이프 DTH점 | incheon | sync_sinbiweb_db | 4 | 204 | 저장 통과 |
| 드림이스케이프  | konkuk | sync_escapetop_db | 4 | 225 | 저장 통과 |
| 라비린스이스케이프  | gyeonggi | sync_sinbiweb_db | 7 | 354 | 저장 통과 |
| 룸익스케이프 신촌 블랙점 | sinchon | sync_reserv_public_db | 4 | 193 | 저장 통과 |
| 룸익스케이프 신촌 올리브점 | sinchon | sync_reserv_public_db | 2 | 158 | 저장 통과 |
| 룸익스케이프 신촌 화이트점 | sinchon | sync_reserv_public_db | 5 | 261 | 저장 통과 |
| 룸익스케이프 인디고블루점 | sinchon | sync_reserv_public_db | 3 | 168 | 저장 통과 |
| 방탈출 미로  | seoul_other | sync_escapetop_db | 6 | 303 | 저장 통과 |
| 방탈출고  | incheon | sync_escapetop_db | 6 | 270 | 저장 통과 |
| 시그널헌터 가로수길점 | gangnam | sync_escapetop_db | 4 | 210 | 저장 통과 |
| 시그널헌터 동탄점 | gyeonggi | sync_escapetop_db | 5 | 262 | 저장 통과 |
| 신나는방탈출  | busan | sync_escapetop_db | 3 | 132 | 저장 통과 |
| 어메이즈드 3호점 | incheon | sync_amazed_db | 1 | 98 | 자동 보류 |
| 엑소더스 강남1호점 | gangnam | sync_exodus_current_db | 2 | 101 | 저장 통과 |
| 오늘의한페이지 방탈출카페  | gangnam | sync_reserv_public_db | 3 | 203 | 저장 통과 |
| 이스케이프샵 건대점 | konkuk | sync_reserv_public_db | 10 | 658 | 저장 통과 |
| 이스케이프샵  | gangnam | sync_reserv_public_db | 5 | 343 | 저장 통과 |
| 코드나인방탈출카페  | chungnam | sync_escapetop_db | 4 | 176 | 저장 통과 |
| 큐브이스케이프 대구점 | daegu | sync_cubeescape_db | 10 | 640 | 자동 보류 |
| 큐브이스케이프 대전둔산점 | daejeon | sync_cubeescape_db | 6 | 376 | 자동 보류 |
| 큐브이스케이프 수유점 | seoul_other | sync_cubeescape_db | 9 | 293 | 자동 보류 |
| 큐브이스케이프 인천점 | incheon | sync_cubeescape_db | 5 | 310 | 자동 보류 |
| 큐브이스케이프 잠실점 | jamsil | sync_cubeescape_db | 6 | 324 | 자동 보류 |
| 큐브이스케이프 전주점 | jeonbuk | sync_cubeescape_db | 8 | 458 | 자동 보류 |
| 큐브이스케이프 천호점 | jamsil | sync_cubeescape_db | 7 | 406 | 자동 보류 |
| 큐브이스케이프 홍대점 | hongdae | sync_cubeescape_db | 9 | 512 | 자동 보류 |
| 파노라마 부산  | busan | sync_escapetop_db | 1 | 53 | 저장 통과 |
| 플레이더월드 강남점 | gangnam | sync_escapetop_db | 5 | 154 | 저장 통과 |
| 플레이더월드 건대점 | konkuk | sync_escapetop_db | 5 | 300 | 저장 통과 |
| 플레이더월드 대전은행점 | daejeon | sync_escapetop_db | 7 | 528 | 저장 통과 |
| 플레이더월드 동성로점 | daegu | sync_reserv_public_db | 4 | 308 | 저장 통과 |
| 플레이더월드 부평점 | incheon | sync_reserv_public_db | 5 | 343 | 저장 통과 |
| 플레이더월드 평택점 | gyeonggi | sync_reserv_public_db | 6 | 378 | 저장 통과 |
| 호텔레토 성수점 | seongsu | sync_sinbiweb_db | 1 | 48 | 저장 통과 |

## 기존 미해결 79개 항목

| 카페/지점 | 지역 | 상태 | 근거·다음 검토 |
|---|---|---|---|
| 강남점  | gangnam | 기존 수집 카페와 중복 후보 | 현재 수집 ID official_xcape_gn와 주소/공식 사이트 대조 대상. 삭제·중복 수집 안 함 |
| 개꿀이스케이프  | gangnam | 기존 수집기 재구현/추가 확인 필요 | [WARN] GET /v2/shops/XEcM52tKWqDCUFCG 실패: HTTP Error 500: Internal Server Error |
| 건대2호  | konkuk | 기존 수집 카페와 중복 후보 | 현재 수집 ID official_xcape_xr와 주소/공식 사이트 대조 대상. 삭제·중복 수집 안 함 |
| 건대점  | konkuk | 기존 수집 카페와 중복 후보 | 현재 수집 ID official_xcape_xc와 주소/공식 사이트 대조 대상. 삭제·중복 수집 안 함 |
| 고한 시티써커스  | gangwon | 공식 시간표·예약처 추가 확인 필요 | 사이트/소개 목록 확인만으로 시간표 수집 성공으로 처리하지 않음 |
| 다락방 안양점 | gyeonggi | 공식 도메인 접속 확인 불가 | ConnectionError — 폐업으로 단정하지 않음 |
| 더코드  | gwangju | 기존 수집기 재구현/추가 확인 필요 | [WARN] GET http://www.thecode-escape.com/sub/code_sub03.html?chois_date=2026-11-16&r_thema=esc_09 실패: HTTP Error 500: Internal Server Error; [WARN] GET http://www.thecode-escape.com/sub/code_sub03.html?chois_date=2026-11 |
| 더트랩 수유점 | seoul_other | 기존 수집기 재구현/추가 확인 필요 | 공식 응답은 있으나 검증된 요청 기간 시간표가 없음 |
| 라스트이스케이프 강남점 | gangnam | 공식 도메인 접속 확인 불가 | ConnectionError — 폐업으로 단정하지 않음 |
| 레다스퀘어 홍대점 | hongdae | 기존 수집기 재구현/추가 확인 필요 | 공식 응답은 있으나 검증된 요청 기간 시간표가 없음 |
| 레드런 천안점 | chungnam | 업종·예약 방식 재확인 필요 | 레드런은 발판게임 정보가 함께 검색됨. 방탈출 카페로 확정/타임 생성 안 함 |
| 레드런 천호점 | jamsil | 업종·예약 방식 재확인 필요 | 레드런은 발판게임 정보가 함께 검색됨. 방탈출 카페로 확정/타임 생성 안 함 |
| 레전드이스케이프 서현점 | gyeonggi | 기존 수집기 재구현/추가 확인 필요 | 공식 응답은 있으나 검증된 요청 기간 시간표가 없음 |
| 룸엘이스케이프 신림점 | sinlim | 기존 수집기 재구현/추가 확인 필요 | 공식 응답은 있으나 검증된 요청 기간 시간표가 없음 |
| 룸즈에이 강남점 | gangnam | 예약 화면 보호 / 목록만 수집 | 공통 공식 예약 화면의 보호 안내. 시간대 생성/보호 우회 안 함 |
| 룸즈에이 광주상무점 | gwangju | 예약 화면 보호 / 목록만 수집 | 공통 공식 예약 화면의 보호 안내. 시간대 생성/보호 우회 안 함 |
| 룸즈에이 광주수완2호점 | gwangju | 예약 화면 보호 / 목록만 수집 | 공통 공식 예약 화면의 보호 안내. 시간대 생성/보호 우회 안 함 |
| 룸즈에이 광주수완점 | gwangju | 예약 화면 보호 / 목록만 수집 | 공통 공식 예약 화면의 보호 안내. 시간대 생성/보호 우회 안 함 |
| 룸즈에이 대구동성로점 | daegu | 예약 화면 보호 / 목록만 수집 | 공통 공식 예약 화면의 보호 안내. 시간대 생성/보호 우회 안 함 |
| 룸즈에이 대구스테이지점 | daegu | 예약 화면 보호 / 목록만 수집 | 공통 공식 예약 화면의 보호 안내. 시간대 생성/보호 우회 안 함 |
| 룸즈에이 대전둔산점 | daejeon | 예약 화면 보호 / 목록만 수집 | 공통 공식 예약 화면의 보호 안내. 시간대 생성/보호 우회 안 함 |
| 룸즈에이 대전은행점 | daejeon | 예약 화면 보호 / 목록만 수집 | 공통 공식 예약 화면의 보호 안내. 시간대 생성/보호 우회 안 함 |
| 룸즈에이 대학로점 | myeongdong | 예약 화면 보호 / 목록만 수집 | 공통 공식 예약 화면의 보호 안내. 시간대 생성/보호 우회 안 함 |
| 룸즈에이 동성로 아카데미점 | daegu | 예약 화면 보호 / 목록만 수집 | 공통 공식 예약 화면의 보호 안내. 시간대 생성/보호 우회 안 함 |
| 룸즈에이 동성로2호점 | daegu | 예약 화면 보호 / 목록만 수집 | 공통 공식 예약 화면의 보호 안내. 시간대 생성/보호 우회 안 함 |
| 룸즈에이 부산남포점 | busan | 예약 화면 보호 / 목록만 수집 | 공통 공식 예약 화면의 보호 안내. 시간대 생성/보호 우회 안 함 |
| 룸즈에이 부산서면점 | busan | 예약 화면 보호 / 목록만 수집 | 공통 공식 예약 화면의 보호 안내. 시간대 생성/보호 우회 안 함 |
| 룸즈에이 부평 2호점 | incheon | 예약 화면 보호 / 목록만 수집 | 공통 공식 예약 화면의 보호 안내. 시간대 생성/보호 우회 안 함 |
| 룸즈에이 부평점 | incheon | 예약 화면 보호 / 목록만 수집 | 공통 공식 예약 화면의 보호 안내. 시간대 생성/보호 우회 안 함 |
| 룸즈에이 수원역 2호점 | gyeonggi | 예약 화면 보호 / 목록만 수집 | 공통 공식 예약 화면의 보호 안내. 시간대 생성/보호 우회 안 함 |
| 룸즈에이 수원역점 | gyeonggi | 예약 화면 보호 / 목록만 수집 | 공통 공식 예약 화면의 보호 안내. 시간대 생성/보호 우회 안 함 |
| 룸즈에이 안양범계점 | gyeonggi | 예약 화면 보호 / 목록만 수집 | 공통 공식 예약 화면의 보호 안내. 시간대 생성/보호 우회 안 함 |
| 룸즈에이 의정부점 | gyeonggi | 예약 화면 보호 / 목록만 수집 | 공통 공식 예약 화면의 보호 안내. 시간대 생성/보호 우회 안 함 |
| 룸즈에이 일산 웨스턴돔점 | gyeonggi | 예약 화면 보호 / 목록만 수집 | 공통 공식 예약 화면의 보호 안내. 시간대 생성/보호 우회 안 함 |
| 룸즈에이 포항점 | gyeongbuk | 예약 화면 보호 / 목록만 수집 | 공통 공식 예약 화면의 보호 안내. 시간대 생성/보호 우회 안 함 |
| 리버스이스케이프 안산점 | gyeonggi | 기존 수집기 재구현/추가 확인 필요 | ValueError: 테마/예약완료 목록 응답을 모두 확인하지 못했습니다. |
| 리버스이스케이프 향남점 | gyeonggi | 기존 수집기 재구현/추가 확인 필요 | ValueError: 테마/예약완료 목록 응답을 모두 확인하지 못했습니다. |
| 리얼이스케이프챌린지  | hongdae | 공식 시간표·예약처 추가 확인 필요 | 사이트/소개 목록 확인만으로 시간표 수집 성공으로 처리하지 않음 |
| 리즌방탈출  | incheon | 공식 시간표·예약처 추가 확인 필요 | 사이트/소개 목록 확인만으로 시간표 수집 성공으로 처리하지 않음 |
| 미션브레이크 CGV용산아이파크몰점 | itaewon | 공식 시간표·예약처 추가 확인 필요 | 사이트/소개 목록 확인만으로 시간표 수집 성공으로 처리하지 않음 |
| 미스터리담  | gyeonggi | 기존 수집기 재구현/추가 확인 필요 | 공식 응답은 있으나 검증된 요청 기간 시간표가 없음 |
| 미스터리룸이스케이프 강남점 | gangnam | 공식 도메인 접속 확인 불가 | ConnectionError — 폐업으로 단정하지 않음 |
| 미스터리룸이스케이프 홍대2호점 | hongdae | 공식 도메인 접속 확인 불가 | ConnectionError — 폐업으로 단정하지 않음 |
| 방탈출 뉴케이스  | konkuk | 공식 시간표·예약처 추가 확인 필요 | 사이트/소개 목록 확인만으로 시간표 수집 성공으로 처리하지 않음 |
| 방탈출브이 공평점 | daegu | 공식 도메인 접속 확인 불가 | ConnectionError — 폐업으로 단정하지 않음 |
| 방탈출브이 삼덕점 | daegu | 공식 도메인 접속 확인 불가 | ConnectionError — 폐업으로 단정하지 않음 |
| 방탈출카페 일상탈출 안양일번가점 | gyeonggi | 공식 시간표·예약처 추가 확인 필요 | 사이트/소개 목록 확인만으로 시간표 수집 성공으로 처리하지 않음 |
| 브레이크아웃 광안  | busan | 예약처 지점 불일치 | 등록은 광안이나 제공 예약처 27519 공식 주소는 해운대. 타 지점 시간표 연결 안 함 |
| 비트포비아 대학로점 | myeongdong | 기존 수집기 재구현/추가 확인 필요 | RuntimeError: 비트포비아 API 조회 실패: /reservation/ck_no1.php |
| 비트포비아 동성로점 | daegu | 공식 시간표·예약처 추가 확인 필요 | 사이트/소개 목록 확인만으로 시간표 수집 성공으로 처리하지 않음 |
| 비트포비아 명동점 | myeongdong | 기존 수집기 재구현/추가 확인 필요 | RuntimeError: 비트포비아 API 조회 실패: /reservation/ck_no1.php |
| 비트포비아 신림점 | sinlim | 공식 시간표·예약처 추가 확인 필요 | 사이트/소개 목록 확인만으로 시간표 수집 성공으로 처리하지 않음 |
| 셜록홈즈 노량진점 | seoul_other | 기존 수집기 재구현/추가 확인 필요 | 공식 응답은 있으나 검증된 요청 기간 시간표가 없음 |
| 셜록홈즈 부산기장정관점 | busan | 기존 수집기 재구현/추가 확인 필요 | 공식 응답은 있으나 검증된 요청 기간 시간표가 없음 |
| 셜록홈즈 분당야탑점 | gyeonggi | 기존 수집기 재구현/추가 확인 필요 | 공식 응답은 있으나 검증된 요청 기간 시간표가 없음 |
| 수원점  | gyeonggi | 기존 수집 카페와 중복 후보 | 현재 수집 ID official_xcape_sw와 주소/공식 사이트 대조 대상. 삭제·중복 수집 안 함 |
| 스키피지  | hongdae | 기존 수집 카페와 중복 후보 | 현재 수집 ID 1825220691와 주소/공식 사이트 대조 대상. 삭제·중복 수집 안 함 |
| 시크릿코드 홍대직영점 | hongdae | 공식 도메인 접속 확인 불가 | ConnectionError — 폐업으로 단정하지 않음 |
| 싸인이스케이프 인계시티점 | gyeonggi | 기존 수집기 재구현/추가 확인 필요 | [WARN] GET http://www.signescape.com/sub/sub03_1.html?R_JIJEM=S1&chois_date=2026-11-16&R_THEMA=A 실패: HTTP Error 500: Internal Server Error; [WARN] GET http://www.signescape.com/sub/sub03_1.html?R_JIJEM=S1&chois_date=2026 |
| 안흥여관  | daejeon | 공개 시간표 확인 필요 | 인스타 DM 예약 안내가 있으나 기계가 읽는 공식 시간표 확인되지 않음 |
| 알카트래즈방탈출카페  | myeongdong | 공식 전화 예약 안내 | 온라인 예약 시스템 공사 중, 전화 예약 안내 |
| 언리미티드 이스케이프  | jeju | 공식 도메인 접속 확인 불가 | ConnectionError — 폐업으로 단정하지 않음 |
| 오늘탈출 고양점 | gyeonggi | 공식 리뉴얼 안내 | 공식 홈페이지 첫출근이야기 테마 리뉴얼 중. 재오픈 일정 준비 중 안내 |
| 오아시스 뮤지엄  | hongdae | 기존 수집기 재구현/추가 확인 필요 | RuntimeError: 마감 목록 조회 실패: tm=8, date=2026-11-17 |
| 월투월방탈출  | sinlim | 기존 수집기 재구현/추가 확인 필요 | 공식 응답은 있으나 검증된 요청 기간 시간표가 없음 |
| 위드방탈출카페  | sinchon | 공식 도메인 접속 확인 불가 | ConnectionError — 폐업으로 단정하지 않음 |
| 제로월드 롯데월드점 | jamsil | 공식 도메인 접속 확인 불가 | ConnectionError — 폐업으로 단정하지 않음 |
| 지니어스이스케이프  | jeonbuk | 예약 경로 접근 제한 | 공식 경로의 접근 제한 응답. 홈페이지 응답과 시간대 수집을 구분 |
| 체셔캣방탈출카페  | gyeonggi | 기존 수집기 재구현/추가 확인 필요 | 공식 응답은 있으나 검증된 요청 기간 시간표가 없음 |
| 카오스이스케이프  | jeonbuk | 공식 시간표·예약처 추가 확인 필요 | 사이트/소개 목록 확인만으로 시간표 수집 성공으로 처리하지 않음 |
| 코난방탈출 구로디지털단지역점 | seoul_other | 공식 도메인 접속 확인 불가 | ConnectionError — 폐업으로 단정하지 않음 |
| 코드이스케이프 가로수길점 | gangnam | 공식 시간표·예약처 추가 확인 필요 | 사이트/소개 목록 확인만으로 시간표 수집 성공으로 처리하지 않음 |
| 키즈인더룸 평촌점 | gyeonggi | 예약 경로 접근 제한 | 공식 경로의 접근 제한 응답. 홈페이지 응답과 시간대 수집을 구분 |
| 파라박스  | gangnam | 공식 도메인 접속 확인 불가 | ConnectionError — 폐업으로 단정하지 않음 |
| 페르소나  | gwangju | 공식 시간표·예약처 추가 확인 필요 | 사이트/소개 목록 확인만으로 시간표 수집 성공으로 처리하지 않음 |
| 필더블랭크  | hongdae | 기존 수집기 재구현/추가 확인 필요 | 공식 응답은 있으나 검증된 요청 기간 시간표가 없음 |
| 하이드앤시크 쌈지길점 | daehakro | 공식 도메인 접속 확인 불가 | SSLError — 폐업으로 단정하지 않음 |
| 하이드앤시크 홍대점 | hongdae | 공식 도메인 접속 확인 불가 | ConnectionError — 폐업으로 단정하지 않음 |
| 할리갈리인더룸방탈출시즌2  | gyeonggi | 공식 시간표·예약처 추가 확인 필요 | 사이트/소개 목록 확인만으로 시간표 수집 성공으로 처리하지 않음 |

## 자동 수집 보류 19곳 (기존 10 + 신규 9)

| 카페/지점 | 수집기 | 사유 |
|---|---|---|
| 큐브이스케이프 전주점 | sync_cubeescape_db | GitHub 실행에서 HTTP 403 접근 제한 |
| 비밀의화원 광주점 | sync_secretgarden_db | GitHub 실행에서 HTTP 403 접근 제한 |
| 어메이즈드 3호점 | sync_amazed_db | GitHub 응답에서 공식 예약 달력 확인 불가 |
| 큐브이스케이프 인천점 | sync_cubeescape_db | GitHub 실행에서 HTTP 403 접근 제한 |
| 비밀의화원 시네마틱 혜화점 | sync_secretgarden_db | GitHub 실행에서 HTTP 403 접근 제한 |
| 제트방탈출카페  | sync_zescape_db | GitHub 실행에서 HTTP 403 접근 제한 |
| 큐브이스케이프 대구점 | sync_cubeescape_db | GitHub 실행에서 HTTP 403 접근 제한 |
| 큐브이스케이프 홍대점 | sync_cubeescape_db | GitHub 실행에서 HTTP 403 접근 제한 |
| 큐브이스케이프 수유점 | sync_cubeescape_db | GitHub 실행에서 HTTP 403 접근 제한 |
| 비밀의화원 전주점 | sync_secretgarden_db | GitHub 실행에서 HTTP 403 접근 제한 |
| 비밀의화원 서면점 | sync_secretgarden_db | GitHub 실행에서 HTTP 403 접근 제한 |
| 덤앤더머 방탈출카페 대학로점 | sync_dumbndumber_db | GitHub 실행에서 HTTP 403 접근 제한 |
| 비밀의화원 대학로점 | sync_secretgarden_db | GitHub 실행에서 HTTP 403 접근 제한 |
| 덤앤더머 방탈출카페 서면점 | sync_dumbndumber_db | GitHub 실행에서 HTTP 403 접근 제한 |
| 비밀의화원 건대점 | sync_secretgarden_db | GitHub 실행에서 HTTP 403 접근 제한 |
| 비밀의화원 동성로점 | sync_secretgarden_db | GitHub 실행에서 HTTP 403 접근 제한 |
| 큐브이스케이프 대전둔산점 | sync_cubeescape_db | GitHub 실행에서 HTTP 403 접근 제한 |
| 큐브이스케이프 천호점 | sync_cubeescape_db | GitHub 실행에서 HTTP 403 접근 제한 |
| 큐브이스케이프 잠실점 | sync_cubeescape_db | GitHub 실행에서 HTTP 403 접근 제한 |

## 검증 자료

- `baseline.json`: 시작 시점 DB의 123개 대상.
- `recheck.json`: 기존 수집기 62곳의 최초 실제 읽기 검증 결과.
- `naver-identity.json`: 공식 네이버 예약 상호·주소 대조 자료.
- `remaining-url-audit.json`: 미해결 항목 공식 URL 49개 조회 결과.
- `published-checks.json`, `published-summary.json`: 로컬 저장 통과 44곳의 상세 증거.
- `github-validation.json`: GitHub 확장 시험 결과 및 보류 근거.
- `metadata-updates.json`: DB 연결 정보 수정 전/후.
- `../../../data/deferred-crawlers.json`: 자동 수집 보류 목록. 재개 시 명시적으로 목록에서 제외하고 정기 대상·DB 보류 표시를 함께 갱신한다.
- 과거 미완성 `test_engines.py`는 현재 없는 엔진 클래스를 참조하므로 서비스 경로 테스트에서 제외.
- 수집 도중 KST 날짜가 바뀌었으므로 관측 수치의 기준 날짜는 각 `checked_at`을 따른다. 정기 수집은 실행 당시 오늘부터 7일을 채운다.
