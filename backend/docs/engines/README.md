# 예약 엔진 분석 문서

각 방탈출 카페 예약 시스템의 API 역공학 분석 결과.
분석 방법, 적용한 크롤링 전략, 발생한 문제와 해결 과정까지 기록.

---

## 분석 방법 (공통)

1. 해당 카페 예약 페이지를 크롬에서 열기
2. F12 → Network 탭 → "Fetch/XHR" 필터 선택
3. 달력에서 날짜를 클릭하거나 지점을 바꾸면서 발생하는 요청 확인
4. Headers, Request Payload, Response 탭에서 API 구조 파악
5. 페이지 소스에서 JS 파일을 직접 분석 (인증 로직, 파라미터명 확인)
6. `curl` 또는 Python으로 API 재현 테스트
7. 이 폴더에 분석 결과를 문서로 기록

---

## 파일 목록

| 파일 | 대상 사이트 | 기술 방식 | 특이사항 |
|------|------------|---------|---------|
| [xdungeon.md](xdungeon.md) | xdungeon.net (비트포비아 던전) | SSR + BeautifulSoup | booking_url 버그 수정 포함 |
| [keyescape.md](keyescape.md) | keyescape.com (키이스케이프) | PHP AJAX API | snake_case/camelCase 파라미터 이슈 |
| [doorescape.md](doorescape.md) | doorescape.co.kr (도어이스케이프) | SaaS 플랫폼 REST API | JWT 인증, SSL 우회 필요 |
| [playtheworld_etc.md](playtheworld_etc.md) | 개꿀이스케이프·이스케이프샾·플레이더월드 | macro.playthe.world REST API | 브랜드별 keycode, 플레이더월드 v1 API 수집 불가 |
| [fantastrick.md](fantastrick.md) | fantastrick.co.kr (판타스트릭 3지점) | WordPress Booked AJAX | 지점별 calendar_id 분리, TGC 카카오 분류 오류 |
| [masterkey.md](masterkey.md) | master-key.co.kr (마스터키/플레이포인트랩) | 자체 PHP AJAX + HTML 파싱 | bid로 지점 구분, room_id로 테마 식별, 11개 지점 51개 테마 |
| [frankantique.md](frankantique.md) | thefrank.co.kr (프랭크의골동품가게) | 신비웹 PHP CMS AJAX | 실제 경로 /layout/res/ 하위, SSL 우회 필요, 테마 3개 |
| [dpsnnn.md](dpsnnn.md) | dpsnnn.com (단편선 방탈출 강남점) | imweb fo-booking-widget React API | 구형 .cm 엔드포인트 우회, 세션 쿠키 필요 |
| [studioesc.md](studioesc.md) | studioesc.co.kr (스튜디오이에스씨) | sinbiweb PHP CMS HTML 파싱 | 루트→302 리다이렉트로 실제 경로 발견, span.possible/impossible |
| [mafiacafe.md](mafiacafe.md) | mafiacafe.kr (마피아카페 강남1호점) | 자체 REST API (api.realmafia.kr) | Next.js JS 번들 역공학, UTC→KST 변환, 세션별 고유 booking_url |

---

## 크롤링 방법 비교

각 사이트가 서로 다른 예약 시스템을 사용하기 때문에, 크롤링 방법도 전부 다르다.

### xdungeon.net — 서버사이드 렌더링(SSR) HTML 파싱

**특징**: PHP 서버가 HTML을 완성해서 응답. JavaScript 실행 불필요.

```
GET home.php?go=rev.main&s_zizum={ID}&rev_days={DATE}
→ HTML 파싱 (BeautifulSoup)
→ li.sale → available, li.dead.sale → full
```

**장점**: 단순, 빠름, 외부 의존 없음
**단점**: HTML 구조 변경 시 파서 수정 필요

---

### keyescape.com — PHP AJAX API (자체 개발)

**특징**: 하나의 PHP 파일(`run_proc.php`)이 라우터 역할. `t=` 파라미터로 액션 결정.

```
POST /controller/run_proc.php
t=get_theme_info_list&zizum_num={N}                               → 테마 목록 (JSON)
t=get_theme_time&date=...&zizumNum={N}&themeNum={M}&endDay=0      → 슬롯 (JSON)
```

**발생한 이슈**: `zizum_num`(테마 목록)과 `zizumNum`(슬롯 조회)가 서로 다른 케이스 사용.
혼용하면 `{"status": false, "msg": "잘못된 접근"}` 반환.

**장점**: JSON 응답, 파싱 간단
**단점**: 이미지 정보 없음, 비표준 파라미터 명명

---

### doorescape.co.kr / 개꿀이스케이프 / 이스케이프샾 — SaaS 플랫폼 REST API

**특징**: `macro.playthe.world`라는 외부 예약 플랫폼 사용. JWT 인증 필요.
동일 플랫폼을 여러 방탈출 브랜드가 사용하며, 브랜드별로 `keycode`만 다르다.

```
GET https://macro.playthe.world/v2/shops/{shop_keycode}
Headers: Bearer-Token, X-Request-Option(JWT), X-Secure-Random, Site-Referer 등
→ 전체 슬롯 (한 번에, can_book boolean)
```

**발생한 이슈**:
1. keycode가 각 브랜드의 `base.js`에 하드코딩 → 직접 추출 가능
2. JWT 생성 로직을 `createJWT(keycode, SECURERANDOM)`에서 역공학
3. SSL 인증서 체인 오류 → `ssl.CERT_NONE`으로 우회
4. 플레이더월드는 v1 API 사용 + 개별 지점 조회 시 themes 0개 반환 → 수집 불가

**장점**: 테마 이미지 URL 제공, 슬롯 데이터 풍부
**단점**: SSL 우회 필요, keycode 변경 감지 어려움, 전체 슬롯을 항상 로드

---

### fantastrick.co.kr — WordPress Booked 플러그인 AJAX

**특징**: WordPress 예약 플러그인 사용. 날짜별로 HTML 응답.

```
POST http://fantastrick.co.kr/wp-admin/admin-ajax.php
Body: action=booked_calendar_date&date=YYYY-MM-DD&calendar_id=N
→ HTML 파싱 (div.timeslot > button[data-timeslot], span.spots-available)
```

**발생한 이슈**:
1. 3개 지점이 하나의 WordPress 사이트 공유 → calendar_id로만 테마 구분
2. 판타스트릭TGC(3호점)가 카카오 DB에 "게임방, PC방"으로 오분류 → REST API 검색 불가, 수동 등록 필요
3. 지점별 cafe_id를 테마마다 개별 지정해야 함

**장점**: 인증 불필요, 구조 단순
**단점**: JSON이 아닌 HTML 파싱 필요, 날짜별 개별 호출

---

### master-key.co.kr — 자체 PHP AJAX + HTML 파싱

**특징**: 단일 엔드포인트가 날짜+지점별 전체 테마와 슬롯을 HTML로 반환. 별도 테마 목록 API 없음.

```
POST /booking/booking_list_new
Body: date=YYYY-MM-DD&store={bid}&room=
→ HTML 파싱 (div.box2-inner 단위로 테마별 슬롯)
→ p.col.true → available, p.col.false → full
→ a 텍스트에서 span 제거 → "HH:MM"
→ img[src]의 /upload/room/{room_id}_img1.gif에서 room_id 추출
```

**발생한 이슈**:
1. 테마 목록 API 없음 → 오늘~6일 슬롯 스캔으로 활성 테마 동적 발견
2. `a` 태그에 시간과 상태명이 혼재(`"14:45예약가능"`) → span 텍스트 제거 후 시간 파싱

**장점**: HTTP(비암호화)라 SSL 오류 없음, 지점별 API 1회 호출로 전 테마 슬롯 수집
**단점**: JSON 아닌 HTML 파싱 필요, 테마별 직접 예약 링크 없음

---

### thefrank.co.kr — 신비웹(sinbiweb) PHP CMS AJAX

**특징**: `core/res/rev.make.ajax.php` 단일 파일이 `act=` 파라미터로 라우팅. 테마·슬롯 모두 HTML 응답.

```
POST /core/res/rev.make.ajax.php
act=theme&zizum_num=1&theme_num=&rev_days=YYYY-MM-DD   → 테마 목록 (HTML)
act=theme_img&theme_num={N}                             → 포스터 이미지 URL (HTML)
act=time&rev_days=YYYY-MM-DD&theme_num={N}              → 슬롯 (HTML)
→ a.none → full, a[href] → available
→ span 텍스트 "10시 30분" 형식에서 시간 파싱
```

**발생한 이슈**:
1. 사이트 실제 경로가 `/layout/res/` 하위 → `/core/res/` 절대 경로로 직접 호출
2. SSL 인증서 체인 불완전 → `ssl.CERT_NONE`으로 우회

**장점**: 인증 불필요, `act=theme` 1회 호출로 전체 테마 목록 수집
**단점**: HTML 파싱 필요, SSL 우회 필요

---

## 앞으로 추가 예정

- `parabox.md` — 파라박스 (xdungeon과 동일한 PHP 시스템으로 추정, DNS 오류로 현재 접근 불가)
- `exodus.md` — 엑소더스 (xdungeon 계열, 방화벽으로 현재 접근 불가)
- `naver_booking.md` — 네이버 예약 통합 분석
