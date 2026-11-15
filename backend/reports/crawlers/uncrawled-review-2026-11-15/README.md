# 수집 성공 기록이 없던 173개 카페 검토

기준: 2026-11-15. 실행 당시 DB에서 한 번도 성공하지 않은 운영 카페 173곳을 추출했다. 지점별 조회는 실제 예약 제출 없이 읽기 전용으로 수행했다.

## 결과

- 기존 크롤러 연결 133곳: 시간표 구현 114곳, 목록 전용 룸즈에이 19곳.
- 미연결 40곳: 등록 URL의 상태 및 공개 예약 링크 확인. 지도/단축 URL만 있는 항목은 공식 예약 URL 추가 확인 대상으로 분류.
- 시간표 크롤러 114곳: 오늘~다음날 검증 48곳 통과, 61곳 검토 필요, 5곳 오류.
- 통과 48곳은 7일 재검증 후 실제 Supabase에 반영했다. 클레버타운의 미래 날짜 한정 테마 누락을 수정했다.
- 정기 수집 대상은 232곳에서 280곳으로 확대했다. 기존 173곳 중 125곳은 예약 시간대 저장이 아직 확인되지 않았다.
- 엑스케이프 기존 ID 4개는 주소·공식 사이트가 현재 수집 ID와 같아 중복 후보로 분류했다. 데이터나 카페를 삭제하지 않았다.
- 접근 제한·빈 응답·폐업 가능성은 동일한 것으로 단정하지 않는다. 아래 사유 및 원본 JSON을 함께 확인한다.

## 카페별 목록

| 카페 / 지점 | 지역 | 크롤러 | 검토 결과 | 최근 테스트 테마/시간대 | 사유 |
|---|---|---|---|---|---|
| ESC방탈출카페 대전둔산점 | daejeon | sync_escbangtalul_db | 7일 저장 확인 / 정기 수집 추가 | 6 / 64 |  |
| gateoftime 광주점 | gwangju | sync_playtheworld_etc_db | 기존 크롤러 검토 필요 / needs_review | 9 / 0 | [WARN] GET /v2/shops/YybEYe16XjtuRV7S 실패: HTTP Error 500: Internal Server Error |
| gateoftime 대구동성로점 | daegu | sync_playtheworld_etc_db | 기존 크롤러 검토 필요 / needs_review | 5 / 0 | [WARN] GET /v2/shops/HiJhoQFf8ThapVG3 실패: HTTP Error 500: Internal Server Error |
| 강남점  | gangnam | sync_xcape_db | 중복 등록 후보 / 현재 수집 ID official_xcape_gn | 0 / 0 | [WARN] GET /merchants 실패: HTTP Error 503: Service Unavailable: Back-end server is at capacity; [WARN] cafe 1551717206 Firestore 미존재 — 건너뜀 |
| 강릉방탈출카페  | gangwon | 미연결 | 공식 예약 URL 추가 확인 필요 | 0 / 0 |  |
| 개꿀이스케이프  | gangnam | sync_playtheworld_etc_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 | [WARN] GET /v2/shops/XEcM52tKWqDCUFCG 실패: HTTP Error 500: Internal Server Error |
| 건대2호  | konkuk | sync_xcape_db | 중복 등록 후보 / 현재 수집 ID official_xcape_xr | 0 / 0 | [WARN] GET /merchants 실패: HTTP Error 503: Service Unavailable: Back-end server is at capacity; [WARN] GET /reservations 실패: HTTP Error 503: Service Unavailable: Back-end server is at capacity |
| 건대점  | konkuk | sync_xcape_db | 중복 등록 후보 / 현재 수집 ID official_xcape_xc | 0 / 0 | [WARN] GET /merchants 실패: HTTP Error 503: Service Unavailable: Back-end server is at capacity; [WARN] cafe 27354377 Firestore 미존재 — 건너뜀 |
| 고한 시티써커스  | gangwon | 미연결 | 공식 예약 URL 추가 확인 필요 | 0 / 0 |  |
| 광주방탈출카페 식스센스  | gwangju | 미연결 | 공식 예약 URL 추가 확인 필요 | 0 / 0 |  |
| 꿈소풍 부천점 | gyeonggi | sync_dreampicnic_db | 7일 저장 확인 / 정기 수집 추가 | 6 / 69 |  |
| 넥스트에디션 건대1호점 | konkuk | sync_nextedition_db | 7일 저장 확인 / 정기 수집 추가 | 6 / 65 |  |
| 다락방 안양점 | gyeonggi | 미연결 | 크롤러 미연결 / unreachable | 0 / 0 | ConnectionError |
| 다락방방탈출카페 청주직영점 | chungbuk | 미연결 | 공식 예약 URL 추가 확인 필요 | 0 / 0 |  |
| 단편선 방탈출 강남점 | gangnam | sync_dpsnnn_db | 7일 저장 확인 / 정기 수집 추가 | 2 / 20 |  |
| 더도어즈이스케이프  | gyeonggi | 미연결 | 크롤러 미연결 / public_page | 0 / 0 |  |
| 더메이즈 건대점 | konkuk | sync_themazegd_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 | [WARN] GET http://www.themazegd.co.kr/bbs/ajax.get_room.php?date=2026-11-15 실패: HTTP Error 404: Not Found; [WARN] GET http://www.themazegd.co.kr/bbs/ajax.get_room.php?date=2026-11-16 실패: HTTP Error 404: Not Found |
| 더코드  | gwangju | sync_thecode_db | 기존 크롤러 검토 필요 / needs_review | 10 / 104 | [WARN] GET http://www.thecode-escape.com/sub/code_sub03.html?chois_date=2026-11-15&r_thema=esc_09 실패: HTTP Error 500: Internal Server Error; [WARN] GET http://www.thecode-escape.com/sub/code_sub03.html?chois_date=2026-11-15&r_thema=esc_10 실 |
| 더큐이스케이프 대전둔산점 | daejeon | sync_theqescape_db | 7일 저장 확인 / 정기 수집 추가 | 5 / 71 |  |
| 더타임이스케이프  | gyeongnam | sync_thetimeescape_db | 7일 저장 확인 / 정기 수집 추가 | 6 / 60 |  |
| 더트랩 수유점 | seoul_other | sync_thetrapsy_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 |  |
| 덤앤더머 방탈출카페 대학로점 | myeongdong | sync_dumbndumber_db | 7일 저장 확인 / 정기 수집 추가 | 6 / 72 |  |
| 도어이스케이프 강남 가든점 | gangnam | sync_doorescape_db | 7일 저장 확인 / 정기 수집 추가 | 4 / 37 |  |
| 도파민방탈출  | gyeonggi | 미연결 | 공식 예약 URL 추가 확인 필요 | 0 / 0 |  |
| 두잇이스케이프  | gyeonggi | 미연결 | 공식 예약 URL 추가 확인 필요 | 0 / 0 |  |
| 둠이스케이프 1호점 | incheon | sync_sinbiweb_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 |  |
| 둠이스케이프 2호점 | incheon | sync_sinbiweb_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 |  |
| 둠이스케이프 DTH점 | incheon | sync_sinbiweb_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 |  |
| 드림이스케이프  | konkuk | 미연결 | 공식 예약 URL 추가 확인 필요 | 0 / 0 |  |
| 라비린스이스케이프  | gyeonggi | sync_sinbiweb_db | 기존 크롤러 검토 필요 / needs_review | 7 / 58 | [WARN] 세션 획득 실패: <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1081)> |
| 라스트이스케이프 강남점 | gangnam | sync_lastescape_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 | [WARN] POST 실패 (date=2026-11-15): <urlopen error [Errno 8] nodename nor servname provided, or not known>; [WARN] POST 실패 (date=2026-11-16): <urlopen error [Errno 8] nodename nor servname provided, or not known> |
| 레다스퀘어 홍대점 | hongdae | sync_ledasquare_db | 기존 크롤러 검토 필요 / needs_review | 1 / 0 |  |
| 레드런 천안점 | chungnam | 미연결 | 공식 예약 URL 추가 확인 필요 | 0 / 0 |  |
| 레드런 천호점 | jamsil | 미연결 | 공식 예약 URL 추가 확인 필요 | 0 / 0 |  |
| 레전드이스케이프 서현점 | gyeonggi | sync_sinbiweb_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 |  |
| 룸엘이스케이프 신림점 | sinlim | sync_roomlescape_db | 기존 크롤러 검토 필요 / needs_review | 4 / 0 |  |
| 룸엘이스케이프 홍대1호점 | hongdae | sync_roomlescape_db | 7일 저장 확인 / 정기 수집 추가 | 2 / 22 |  |
| 룸익스케이프 신촌 블랙점 | sinchon | sync_playtheworld_etc_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 | [WARN] GET /v2/shops/Z5dmpFTTqzaSqaa4 실패: HTTP Error 500: Internal Server Error; [WARN] cafe 27329834 Firestore 미존재 — 건너뜀 |
| 룸익스케이프 신촌 올리브점 | sinchon | sync_playtheworld_etc_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 | [WARN] GET /v2/shops/vG4SZyg8jem2YYuo 실패: HTTP Error 500: Internal Server Error; [WARN] cafe 912842418 Firestore 미존재 — 건너뜀 |
| 룸익스케이프 신촌 화이트점 | sinchon | sync_playtheworld_etc_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 | [WARN] GET /v2/shops/p8j31JZAgRCJWnUc 실패: HTTP Error 500: Internal Server Error; [WARN] cafe 1542251042 Firestore 미존재 — 건너뜀 |
| 룸익스케이프 인디고블루점 | sinchon | sync_playtheworld_etc_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 | [WARN] GET /v2/shops/mpu5Jvr5DzANeHRL 실패: HTTP Error 500: Internal Server Error |
| 룸즈에이 강남점 | gangnam | sync_roomsa_catalog_db | 목록 전용 구현 / 예약 시간대 미구현 | 0 / 0 |  |
| 룸즈에이 광주상무점 | gwangju | sync_roomsa_catalog_db | 목록 전용 구현 / 예약 시간대 미구현 | 0 / 0 |  |
| 룸즈에이 광주수완2호점 | gwangju | sync_playtheworld_etc_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 | [WARN] GET /v2/shops/N22seZPUEfSe1jKQ 실패: HTTP Error 500: Internal Server Error |
| 룸즈에이 광주수완점 | gwangju | sync_roomsa_catalog_db | 목록 전용 구현 / 예약 시간대 미구현 | 0 / 0 |  |
| 룸즈에이 대구동성로점 | daegu | sync_roomsa_catalog_db | 목록 전용 구현 / 예약 시간대 미구현 | 0 / 0 |  |
| 룸즈에이 대구스테이지점 | daegu | sync_roomsa_catalog_db | 목록 전용 구현 / 예약 시간대 미구현 | 0 / 0 |  |
| 룸즈에이 대전둔산점 | daejeon | sync_roomsa_catalog_db | 목록 전용 구현 / 예약 시간대 미구현 | 0 / 0 |  |
| 룸즈에이 대전은행점 | daejeon | sync_roomsa_catalog_db | 목록 전용 구현 / 예약 시간대 미구현 | 0 / 0 |  |
| 룸즈에이 대학로점 | myeongdong | sync_roomsa_catalog_db | 목록 전용 구현 / 예약 시간대 미구현 | 0 / 0 |  |
| 룸즈에이 동성로 아카데미점 | daegu | sync_roomsa_catalog_db | 목록 전용 구현 / 예약 시간대 미구현 | 0 / 0 |  |
| 룸즈에이 동성로2호점 | daegu | sync_roomsa_catalog_db | 목록 전용 구현 / 예약 시간대 미구현 | 0 / 0 |  |
| 룸즈에이 부산남포점 | busan | sync_roomsa_catalog_db | 목록 전용 구현 / 예약 시간대 미구현 | 0 / 0 |  |
| 룸즈에이 부산서면점 | busan | sync_roomsa_catalog_db | 목록 전용 구현 / 예약 시간대 미구현 | 0 / 0 |  |
| 룸즈에이 부평 2호점 | incheon | sync_roomsa_catalog_db | 목록 전용 구현 / 예약 시간대 미구현 | 0 / 0 |  |
| 룸즈에이 부평점 | incheon | sync_playtheworld_etc_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 | [WARN] GET /v2/shops/HUSqfLY6kenWuw5q 실패: HTTP Error 500: Internal Server Error |
| 룸즈에이 수원역 2호점 | gyeonggi | sync_roomsa_catalog_db | 목록 전용 구현 / 예약 시간대 미구현 | 0 / 0 |  |
| 룸즈에이 수원역점 | gyeonggi | sync_roomsa_catalog_db | 목록 전용 구현 / 예약 시간대 미구현 | 0 / 0 |  |
| 룸즈에이 안양범계점 | gyeonggi | sync_roomsa_catalog_db | 목록 전용 구현 / 예약 시간대 미구현 | 0 / 0 |  |
| 룸즈에이 의정부점 | gyeonggi | sync_roomsa_catalog_db | 목록 전용 구현 / 예약 시간대 미구현 | 0 / 0 |  |
| 룸즈에이 일산 웨스턴돔점 | gyeonggi | sync_roomsa_catalog_db | 목록 전용 구현 / 예약 시간대 미구현 | 0 / 0 |  |
| 룸즈에이 포항점 | gyeongbuk | sync_roomsa_catalog_db | 목록 전용 구현 / 예약 시간대 미구현 | 0 / 0 |  |
| 리버스이스케이프 안산점 | gyeonggi | sync_reverseesc_db | 기존 크롤러 검토 필요 / error | 0 / 0 | ValueError: 테마/예약완료 목록 응답을 모두 확인하지 못했습니다. |
| 리버스이스케이프 향남점 | gyeonggi | sync_reverseesc_db | 기존 크롤러 검토 필요 / error | 0 / 0 | ValueError: 테마/예약완료 목록 응답을 모두 확인하지 못했습니다. |
| 리얼이스케이프챌린지  | hongdae | 미연결 | 크롤러 미연결 / public_page | 0 / 0 |  |
| 리즌방탈출  | incheon | 미연결 | 공식 예약 URL 추가 확인 필요 | 0 / 0 |  |
| 마피아카페 강남1호점 | gangnam | sync_mafiacafe_db | 7일 저장 확인 / 정기 수집 추가 | 1 / 34 |  |
| 머더파커 전주1호점 | jeonbuk | sync_murderparker_db | 7일 저장 확인 / 정기 수집 추가 | 3 / 22 |  |
| 무비이스케이프 동탄남광장점 | gyeonggi | sync_movieescape_db | 7일 저장 확인 / 정기 수집 추가 | 4 / 41 |  |
| 미션브레이크 CGV용산아이파크몰점 | itaewon | 미연결 | 크롤러 미연결 / public_page | 0 / 0 |  |
| 미스터리담  | gyeonggi | sync_escapetop_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 |  |
| 미스터리룸이스케이프 강남점 | gangnam | sync_mysteryroom_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 | [WARN] 페이지 로드 실패 a=27 2026-11-15: <urlopen error [Errno 8] nodename nor servname provided, or not known> |
| 미스터리룸이스케이프 홍대2호점 | hongdae | sync_mysteryroom_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 | [WARN] 페이지 로드 실패 a=44 2026-11-15: <urlopen error [Errno 8] nodename nor servname provided, or not known> |
| 방탈출 뉴케이스  | konkuk | 미연결 | 공식 예약 URL 추가 확인 필요 | 0 / 0 |  |
| 방탈출 미로  | seoul_other | 미연결 | 공식 예약 URL 추가 확인 필요 | 0 / 0 |  |
| 방탈출ESC 신촌점 | sinchon | sync_roomescape_db | 7일 저장 확인 / 정기 수집 추가 | 5 / 52 |  |
| 방탈출NO1 수원점 | gyeonggi | sync_no1escape_db | 7일 저장 확인 / 정기 수집 추가 | 4 / 38 |  |
| 방탈출고  | incheon | 미연결 | 공식 예약 URL 추가 확인 필요 | 0 / 0 |  |
| 방탈출브이 공평점 | daegu | sync_vescape_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 | [WARN] GET http://www.v-escape.co.kr/sub/sub03_1.html?R_JIJEM=S2&R_THEMA=A&chois_date=2026-11-15 실패: <urlopen error [Errno 8] nodename nor servname provided, or not known>; [WARN] GET http://www.v-escape.co.kr/sub/sub03_1.html?R_JIJEM=S2&R_ |
| 방탈출브이 삼덕점 | daegu | sync_vescape_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 | [WARN] GET http://www.v-escape.co.kr/sub/sub03_1.html?R_JIJEM=S1&R_THEMA=A&chois_date=2026-11-15 실패: <urlopen error [Errno 8] nodename nor servname provided, or not known>; [WARN] GET http://www.v-escape.co.kr/sub/sub03_1.html?R_JIJEM=S1&R_ |
| 방탈출카페 일상탈출 안양일번가점 | gyeonggi | 미연결 | 공식 예약 URL 추가 확인 필요 | 0 / 0 |  |
| 방탈출탐정 수원점 | gyeonggi | sync_escapedetective_db | 7일 저장 확인 / 정기 수집 추가 | 4 / 35 |  |
| 브레이크아웃 광안  | busan | 미연결 | 크롤러 미연결 / public_page | 0 / 0 |  |
| 비트포비아 강남던전2 | gangnam | sync_xdungeon_db | 7일 저장 확인 / 정기 수집 추가 | 2 / 46 |  |
| 비트포비아 강남던전점 | gangnam | sync_xdungeon_db | 7일 저장 확인 / 정기 수집 추가 | 4 / 76 |  |
| 비트포비아 대학로점 | myeongdong | sync_xphobia_db | 기존 크롤러 검토 필요 / error | 0 / 0 | RuntimeError: 비트포비아 API 조회 실패: /reservation/ck_no1.php |
| 비트포비아 동성로점 | daegu | 미연결 | 크롤러 미연결 / public_page | 0 / 0 |  |
| 비트포비아 명동점 | myeongdong | sync_xphobia_db | 기존 크롤러 검토 필요 / error | 0 / 0 | RuntimeError: 비트포비아 API 조회 실패: /reservation/ck_no1.php |
| 비트포비아 서면던전점 | busan | sync_xdungeon_db | 7일 저장 확인 / 정기 수집 추가 | 3 / 60 |  |
| 비트포비아 신림점 | sinlim | 미연결 | 크롤러 미연결 / public_page | 0 / 0 |  |
| 비트포비아 홍대던전3 | hongdae | sync_xdungeon_db | 7일 저장 확인 / 정기 수집 추가 | 4 / 92 |  |
| 비트포비아 홍대던전점 | hongdae | sync_xdungeon_db | 7일 저장 확인 / 정기 수집 추가 | 4 / 76 |  |
| 비트포비아 던전루나  | gangnam | sync_xdungeon_db | 7일 저장 확인 / 정기 수집 추가 | 2 / 59 |  |
| 비트포비아 던전스텔라  | gangnam | sync_xdungeon_db | 7일 저장 확인 / 정기 수집 추가 | 3 / 60 |  |
| 비트포비아 레드던전 서면점 | busan | sync_xdungeon_db | 7일 저장 확인 / 정기 수집 추가 | 6 / 111 |  |
| 서울이스케이프룸 홍대점 | hongdae | sync_seoulescaperoom_db, sync_seoulesc_db | 7일 저장 확인 / 정기 수집 추가 | 1 / 12 |  |
| 셜록홈즈 노량진점 | seoul_other | sync_sherlock_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 |  |
| 셜록홈즈 부산기장정관점 | busan | sync_sherlock_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 |  |
| 셜록홈즈 분당야탑점 | gyeonggi | sync_sherlock_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 |  |
| 쇼룸404 홍대점 | hongdae | sync_showroom404_db | 7일 저장 확인 / 정기 수집 추가 | 4 / 48 |  |
| 수원점  | gyeonggi | sync_xcape_db | 중복 등록 후보 / 현재 수집 ID official_xcape_sw | 0 / 0 | [WARN] GET /merchants 실패: HTTP Error 503: Service Unavailable: Back-end server is at capacity; [WARN] GET /reservations 실패: HTTP Error 503: Service Unavailable: Back-end server is at capacity |
| 스키피지  | hongdae | 미연결 | 크롤러 미연결 / public_page | 0 / 0 |  |
| 스튜디오이에스씨  | gangnam | sync_studioesc_db | 7일 저장 확인 / 정기 수집 추가 | 2 / 2 |  |
| 시그널헌터 가로수길점 | gangnam | 미연결 | 크롤러 미연결 / unreachable | 0 / 0 | SSLError |
| 시그널헌터 동탄점 | gyeonggi | 미연결 | 크롤러 미연결 / public_page | 0 / 0 |  |
| 시크릿코드 홍대직영점 | hongdae | sync_secretcode_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 | [WARN] GET http://www.secret-code.co.kr/sub_02/sub02_1.html?JIJEM=S3&chois_date=2026-11-15 실패: <urlopen error [Errno 8] nodename nor servname provided, or not known>; [WARN] GET http://www.secret-code.co.kr/sub_02/sub02_1.html?JIJEM=S3&choi |
| 신나는방탈출  | busan | 미연결 | 공식 예약 URL 추가 확인 필요 | 0 / 0 |  |
| 싸인이스케이프 인계시티점 | gyeonggi | sync_signescape_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 | [WARN] GET http://www.signescape.com/sub/sub03_1.html?R_JIJEM=S1&chois_date=2026-11-15&R_THEMA=A 실패: HTTP Error 500: Internal Server Error; [WARN] GET http://www.signescape.com/sub/sub03_1.html?R_JIJEM=S1&chois_date=2026-11-15&R_THEMA=B 실패: |
| 싸인이스케이프 홍대점 | hongdae | sync_signescape_db | 7일 저장 확인 / 정기 수집 추가 | 3 / 20 |  |
| 안흥여관  | daejeon | 미연결 | 공식 예약 URL 추가 확인 필요 | 0 / 0 |  |
| 알카트래즈방탈출카페  | myeongdong | 미연결 | 크롤러 미연결 / public_page | 0 / 0 |  |
| 앨리스이스케이프  | daegu | sync_aliceescape_db | 7일 저장 확인 / 정기 수집 추가 | 9 / 80 |  |
| 어메이즈드 3호점 | incheon | 미연결 | 크롤러 미연결 / public_page | 0 / 0 |  |
| 언리미티드 이스케이프  | jeju | 미연결 | 크롤러 미연결 / unreachable | 0 / 0 | ConnectionError |
| 엑소더스 강남1호점 | gangnam | sync_sinbiweb_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 |  |
| 엑스이스케이프 홍대놀이터점 | hongdae | sync_xescape_db | 7일 저장 확인 / 정기 수집 추가 | 8 / 116 |  |
| 오늘의한페이지 방탈출카페  | gangnam | sync_playtheworld_etc_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 | [WARN] GET /v2/shops/rjwaaAh3mVPbCdHA 실패: HTTP Error 500: Internal Server Error |
| 오늘탈출 고양점 | gyeonggi | sync_escapetop_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 |  |
| 오아시스 뮤지엄  | hongdae | sync_oasisescape_db | 기존 크롤러 검토 필요 / error | 4 / 0 | RuntimeError: 마감 목록 조회 실패: tm=5, date=2026-11-16 |
| 월투월방탈출  | sinlim | sync_escapetop_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 |  |
| 위드방탈출카페  | sinchon | 미연결 | 크롤러 미연결 / unreachable | 0 / 0 | ConnectionError |
| 이스케이프샾 건대점 | konkuk | sync_playtheworld_etc_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 | [WARN] GET /v2/shops/tS5DajzuHqnhrnjH 실패: HTTP Error 500: Internal Server Error |
| 이스케이프샾  | gangnam | sync_playtheworld_etc_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 | [WARN] GET /v2/shops/Jmas3Q5kHnfxQhFZ 실패: HTTP Error 500: Internal Server Error |
| 이스케이프시티 그랜드시티신촌점 | sinchon | sync_escapecity_db | 7일 저장 확인 / 정기 수집 추가 | 3 / 25 |  |
| 이스케이프시티 부천신중동점 | gyeonggi | sync_escapecity_db | 7일 저장 확인 / 정기 수집 추가 | 4 / 32 |  |
| 이스케이프시티 성신여대점 | seoul_other | sync_escapecity_db | 7일 저장 확인 / 정기 수집 추가 | 5 / 36 |  |
| 이스케이프시티 영등포본점 | seoul_other | sync_escapecity_db | 7일 저장 확인 / 정기 수집 추가 | 6 / 45 |  |
| 이스케이프존 강대점 | gangwon | 미연결 | 크롤러 미연결 / public_page | 0 / 0 |  |
| 이스케이프탑 광주점 | gwangju | sync_escapetop_db | 7일 저장 확인 / 정기 수집 추가 | 5 / 47 |  |
| 이스케이프하우스 홍대점 | hongdae | sync_escapehouse_db | 7일 저장 확인 / 정기 수집 추가 | 8 / 101 |  |
| 제로월드 롯데월드점 | jamsil | sync_zeroworld_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 | [WARN] CSRF 획득 실패 https://zerolotteworld.com: <urlopen error [Errno 8] nodename nor servname provided, or not known>; [WARN] 슬롯 조회 실패 https://zerolotteworld.com 2026-11-15: <urlopen error [Errno 8] nodename nor servname provided, or not kno |
| 제트방탈출카페  | ulsan | sync_zescape_db | 7일 저장 확인 / 정기 수집 추가 | 9 / 129 |  |
| 지구별방탈출 홍대어드벤처점 | hongdae | sync_jigobyeol_db | 7일 저장 확인 / 정기 수집 추가 | 6 / 7 |  |
| 지니어스이스케이프  | jeonbuk | sync_geniusescape_db | 기존 크롤러 검토 필요 / needs_review | 5 / 0 | [WARN] POST http://www.geniusescape.kr/sub/03_1_1.html (A/2026-11-15) 실패: HTTP Error 403: Forbidden; [WARN] POST http://www.geniusescape.kr/sub/03_1_1.html (B/2026-11-15) 실패: HTTP Error 403: Forbidden |
| 체셔캣방탈출카페  | gyeonggi | sync_escapetop_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 |  |
| 카오스이스케이프  | jeonbuk | 미연결 | 크롤러 미연결 / public_page | 0 / 0 |  |
| 코난방탈출 구로디지털단지역점 | seoul_other | sync_conanescape_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 | [WARN] POST http://conanescape.kr/sub/sub03_01.php 실패: <urlopen error [Errno 8] nodename nor servname provided, or not known>; [WARN] POST http://conanescape.kr/sub/sub03_01.php 실패: <urlopen error [Errno 8] nodename nor servname provided, o |
| 코드나인방탈출카페  | chungnam | 미연결 | 공식 예약 URL 추가 확인 필요 | 0 / 0 |  |
| 코드이스케이프 가로수길점 | gangnam | 미연결 | 크롤러 미연결 / public_page | 0 / 0 |  |
| 큐브이스케이프 대구점 | daegu | sync_cubeescape_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 |  |
| 큐브이스케이프 대전둔산점 | daejeon | sync_cubeescape_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 |  |
| 큐브이스케이프 수유점 | seoul_other | sync_cubeescape_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 |  |
| 큐브이스케이프 인천점 | incheon | sync_cubeescape_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 |  |
| 큐브이스케이프 잠실점 | jamsil | sync_cubeescape_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 |  |
| 큐브이스케이프 전주점 | jeonbuk | sync_cubeescape_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 |  |
| 큐브이스케이프 천호점 | jamsil | sync_cubeescape_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 |  |
| 큐브이스케이프 홍대점 | hongdae | sync_cubeescape_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 |  |
| 크라임씬카페 퍼즐팩토리 홍대3호점 | hongdae | sync_puzzlefactory_db | 7일 저장 확인 / 정기 수집 추가 | 4 / 28 |  |
| 클레버타운 신촌점 | sinchon | sync_clevertown_db | 7일 저장 확인 / 정기 수집 추가 | 4 / 19 |  |
| 키이스케이프 강남점 | gangnam | sync_keyescape_db | 7일 저장 확인 / 정기 수집 추가 | 3 / 52 |  |
| 키즈인더룸 평촌점 | gyeonggi | 미연결 | 크롤러 미연결 / public_page | 0 / 0 |  |
| 테라스페이스 홍대점 | hongdae | sync_teraspace_db | 7일 저장 확인 / 정기 수집 추가 | 2 / 18 |  |
| 트릭이스케이프  | gyeonggi | sync_trickescape_db | 7일 저장 확인 / 정기 수집 추가 | 4 / 4 |  |
| 티켓투이스케이프 홍대점 | hongdae | sync_ttescape_db | 7일 저장 확인 / 정기 수집 추가 | 4 / 8 |  |
| 파노라마 부산  | busan | 미연결 | 공식 예약 URL 추가 확인 필요 | 0 / 0 |  |
| 파라박스  | gangnam | 미연결 | 크롤러 미연결 / unreachable | 0 / 0 | ConnectionError |
| 패닉이스케이프 목동점 | seoul_other | sync_panicescape_db | 7일 저장 확인 / 정기 수집 추가 | 1 / 1 |  |
| 페르소나  | gwangju | 미연결 | 공식 예약 URL 추가 확인 필요 | 0 / 0 |  |
| 프랭크의골동품가게  | gangnam | sync_frankantique_db | 7일 저장 확인 / 정기 수집 추가 | 3 / 30 |  |
| 플레이더월드 강남점 | gangnam | sync_playtheworld_etc_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 | [WARN] GET /v2/shops/m86eCeH4SoNCqVVX 실패: HTTP Error 500: Internal Server Error |
| 플레이더월드 건대점 | konkuk | 미연결 | 크롤러 미연결 / unreachable | 0 / 0 | ConnectionError |
| 플레이더월드 대전은행점 | daejeon | sync_playtheworld_etc_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 | [WARN] GET /v2/shops/U9cZjMPWeVZbij6X 실패: HTTP Error 500: Internal Server Error |
| 플레이더월드 동성로점 | daegu | sync_playtheworld_etc_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 | [WARN] GET /v2/shops/bF9P9ARTDcgrbcDR 실패: HTTP Error 500: Internal Server Error |
| 플레이더월드 부평점 | incheon | sync_playtheworld_etc_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 | [WARN] GET /v2/shops/fsGEtW3EXJiFXVCZ 실패: HTTP Error 500: Internal Server Error |
| 플레이더월드 평택점 | gyeonggi | sync_playtheworld_etc_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 | [WARN] GET /v2/shops/eerYSTbbLAQnqZv3 실패: HTTP Error 500: Internal Server Error |
| 플레이이스케이프 원주점 | gangwon | sync_playescape_db | 7일 저장 확인 / 정기 수집 추가 | 6 / 48 |  |
| 플레이포인트랩 강남점 | gangnam | sync_masterkey_db | 7일 저장 확인 / 정기 수집 추가 | 6 / 38 |  |
| 필더블랭크  | hongdae | sync_escapetop_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 |  |
| 하이드앤시크 쌈지길점 | daehakro | sync_escapetop_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 |  |
| 하이드앤시크 홍대점 | hongdae | sync_escapetop_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 |  |
| 할리갈리인더룸방탈출시즌2  | gyeonggi | 미연결 | 공식 예약 URL 추가 확인 필요 | 0 / 0 |  |
| 호러스위치 홍대점 | hongdae | sync_horrorswitch_db | 7일 저장 확인 / 정기 수집 추가 | 1 / 32 |  |
| 호텔레토 성수점 | seongsu | sync_sinbiweb_db | 기존 크롤러 검토 필요 / needs_review | 0 / 0 |  |
