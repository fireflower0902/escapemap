# 단편선 방탈출 (dpsnnn.com) 크롤링 분석 문서

> **대상 사이트**: https://www.dpsnnn.com/
> **운영사**: 단편선 방탈출 (강남점)
> **관련 스크립트**: `scripts/sync_dpsnnn_db.py`
> **cafe_id**: `377197835`
> **분석 완료일**: 2026-03-02

---

## 목차

1. [배경](#1-배경)
2. [플랫폼 파악 — imweb](#2-플랫폼-파악--imweb)
3. [구 방식 API 탐색 실패](#3-구-방식-api-탐색-실패)
4. [신형 예약 위젯 역공학](#4-신형-예약-위젯-역공학)
5. [API 엔드포인트 발견](#5-api-엔드포인트-발견)
6. [API 상세 명세](#6-api-상세-명세)
7. [날짜별 가용성 조회 구조](#7-날짜별-가용성-조회-구조)
8. [세션 쿠키 처리](#8-세션-쿠키-처리)
9. [DB 동기화 전략](#9-db-동기화-전략)
10. [실행 결과](#10-실행-결과)
11. [한계 및 주의사항](#11-한계-및-주의사항)

---

## 1. 배경

강남 미크롤링 카페 목록 중 단편선 방탈출은 공식 사이트(`dpsnnn.com`)를 보유하고 있었다.
`/reserve_g` 경로가 강남점 예약 페이지임을 메뉴 구조로 확인했다.

---

## 2. 플랫폼 파악 — imweb

HTML 소스를 보면:

```html
<meta name="publisher" content="imweb" />
```

**imweb**: 카카오스토어·Wix와 비슷한 한국형 웹사이트 빌더.
자체 예약 시스템(`fo-booking-widget`)을 탑재할 수 있다.

페이지 내에서 발견된 JS 로더:

```javascript
SITE_BOOKING.init_calendar({idx: "839631993", ...})
```

처음에는 구 jQuery 기반 `site_booking.js` 방식을 분석했으나, 실제 UI는 이미 **React + Web Components** 기반의 신형 위젯으로 교체된 상태였다.

---

## 3. 구 방식 API 탐색 실패

imweb의 구형 예약 시스템은 `.cm` 확장자를 가진 PHP 스타일 엔드포인트를 사용한다:

```
POST /booking/html_day_booking.cm
POST /booking/html_detail_calendar.cm
```

이 방식은 `booking_f` 폼 데이터 직렬화가 필요하고, 응답이 HTML이다.
테스트해보니 세션 없이는 "Error 1" 응답이 반환됐다.

→ **구 방식은 사용하지 않는다.** 신형 React 위젯 분석으로 방향을 전환했다.

---

## 4. 신형 예약 위젯 역공학

`/reserve_g` 페이지를 로드하면 `html_mfe_list.cm`이 호출되고, 이 응답에서 magnet-shell(Web Components 프레임워크)이 로딩된다.

실제 예약 UI는 `/_/fo-booking-widget/assets/` 경로에 있는 React 번들에서 렌더링된다.

핵심 파일: `reservation-item-components-DJp2U0gt.js`

이 파일에서 axios 인스턴스를 발견했다:

```javascript
k = Y.create({
  baseURL: `${ne}${ie ? "/admin/ajax/" : "/"}booking`,
  responseType: "json",
  headers: {"Content-Type": "application/x-www-form-urlencoded"}
})
```

→ **실제 API base URL = `{사이트 origin}/booking`**

API 호출 코드:

```javascript
k.post("/get_prod_list.cm", {start_date, end_date})
```

→ **실제 엔드포인트 = `POST https://www.dpsnnn.com/booking/get_prod_list.cm`**

---

## 5. API 엔드포인트 발견

| 속성 | 값 |
|------|-----|
| URL | `POST https://www.dpsnnn.com/booking/get_prod_list.cm` |
| Content-Type | `application/x-www-form-urlencoded` |
| 인증 | 세션 쿠키(`IMWEBVSSID`) 필요 |
| 파라미터 없음 | 전체 상품(테마+시간 조합) 목록 반환 |
| `start_date` + `end_date` | 해당 날짜의 가용성 반환 |

---

## 6. API 상세 명세

### 6-1. 전체 상품 목록 (파라미터 없음)

```
POST /booking/get_prod_list.cm
(body 없음)
```

응답:

```json
{
  "total": [
    {"idx": 5,  "name": "상자 / 10:00", "thumbnail": "https://...jpg"},
    {"idx": 6,  "name": "상자 / 11:30", "thumbnail": "https://...jpg"},
    {"idx": 25, "name": "행복 / 10:20", "thumbnail": "https://...jpg"},
    ...
  ]
}
```

**상품명 파싱**: `"{테마명} / {HH:MM}"` → `split(" / ", 1)` 로 테마명과 시간 분리.

강남점 발견 상품:

| 테마명 | 시간 슬롯 |
|--------|-----------|
| 상자 | 10:00, 11:30, 13:00, 14:30, 16:00, 17:30, 19:00, 20:30, 22:00 |
| 행복 | 10:20, 11:50, 13:20, 14:50, 16:20, 17:50, 19:20, 20:50, 22:20 |

### 6-2. 날짜별 가용성

```
POST /booking/get_prod_list.cm
Body: start_date=2026-03-07&end_date=2026-03-07
```

응답:

```json
{
  "available":   [{"idx": 5, "name": "상자 / 10:00", ...}],
  "unavailable": [{"idx": 6, "name": "상자 / 11:30", ...}],
  "total": []
}
```

- `available` 목록에 있으면 → `status = "available"`
- `unavailable` 목록에 있으면 → `status = "full"`
- 두 목록 모두 비어 있으면 → 예약 미오픈 → `status = "closed"`

---

## 7. 날짜별 가용성 조회 구조

날짜별로 `start_date=date&end_date=date` 형태로 동일 날짜를 양쪽에 넣어서 조회한다.

```python
data = _post_api(opener, {"start_date": date_str, "end_date": date_str})
```

응답 확인 결과 (2026-03-02 기준):

| 날짜 | 가능 | 마감 | 비고 |
|------|------|------|------|
| 3/2 | 0 | 18 | 당일 전체 마감 |
| 3/4 | 3 | 15 | 일부 가능 |
| 3/7 | 0 | 18 | 전체 마감 |
| 3/9~ | 0 | 0 | 예약 미오픈 → closed |

---

## 8. 세션 쿠키 처리

imweb 예약 시스템은 `IMWEBVSSID` 쿠키가 필요하다.

`urllib.request.CookieJar` + `HTTPCookieProcessor`를 사용해 자동 처리:

```python
cj = CookieJar()
https_handler = urllib.request.HTTPSHandler(context=_SSL_CTX)
opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(cj),
    https_handler,
)

# 1) GET reserve_g → IMWEBVSSID 쿠키 자동 저장
opener.open(Request("https://www.dpsnnn.com/reserve_g", ...))

# 2) POST API 시 쿠키 자동 포함
opener.open(Request(API_URL, data=body, ...))
```

SSL 인증서 검증도 비활성화 필요 (macOS Python 기본 인증서 체인 문제):

```python
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE
```

---

## 9. DB 동기화 전략

1. 세션 획득 (`/reserve_g` GET)
2. 전체 상품 목록 조회 → 테마 파싱 → Theme upsert
3. 날짜별 (오늘~N일 후) 가용성 조회 → Schedule upsert

**booking_url**: 슬롯별 직접 링크가 없으므로 `https://www.dpsnnn.com/reserve_g` (강남점 예약 페이지)

---

## 10. 실행 결과

```
============================================================
단편선 방탈출 강남점 → DB 동기화
============================================================

[ 0단계 ] 세션 획득: 완료
[ 1단계 ] 전체 상품 목록:
  테마: '상자' → 9개 슬롯
  테마: '행복' → 9개 슬롯

[ 2단계 ] 테마 동기화: 2개 추가 (id=162, 163)
[ 3단계 ] 스케줄 동기화: 256개 레코드 추가 (14일치)
```

---

## 11. 한계 및 주의사항

- **슬롯별 직접 예약 링크 없음**: booking_url은 강남점 예약 메인 페이지로 고정
- **예약 오픈 기간**: 보통 1~2주 앞까지만 오픈 → 미오픈 날짜는 `closed`로 저장
- **성수점 별도**: `dpsnnn-s.imweb.me`는 성수구 소재로 강남 크롤링 대상 아님
- **imweb 플랫폼 업데이트 취약**: imweb이 위젯 버전 올릴 시 API 경로 변경 가능
