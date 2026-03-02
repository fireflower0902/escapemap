# 마피아카페 강남1호점 (mafiacafe.kr) 크롤링 분석 문서

> **대상 사이트**: https://www.mafiacafe.kr/
> **운영사**: 마피아카페 (강남1호점)
> **관련 스크립트**: `scripts/sync_mafiacafe_db.py`
> **cafe_id**: `1030963843`
> **분석 완료일**: 2026-03-02

---

## 목차

1. [배경 — 마피아카페란](#1-배경--마피아카페란)
2. [플랫폼 파악 — Next.js + 자체 REST API](#2-플랫폼-파악--nextjs--자체-rest-api)
3. [JS 번들 역공학](#3-js-번들-역공학)
4. [API 엔드포인트 발견](#4-api-엔드포인트-발견)
5. [API 상세 명세](#5-api-상세-명세)
6. [데이터 구조 해석](#6-데이터-구조-해석)
7. [UTC → KST 변환](#7-utc--kst-변환)
8. [지점 식별 방법](#8-지점-식별-방법)
9. [booking_url 결정](#9-booking_url-결정)
10. [DB 동기화 전략](#10-db-동기화-전략)
11. [실행 결과](#11-실행-결과)
12. [한계 및 주의사항](#12-한계-및-주의사항)

---

## 1. 배경 — 마피아카페란

마피아카페는 전통적인 방탈출이 아닌 **마피아 보드게임을 진행자(딜러)가 이끄는 형태**의 사회적 추리 게임 카페다.
강남1호점(`서울시 강남구 강남대로 96길 19, 4층`)과 대구점이 운영 중이다.

DB에 이미 카페 정보가 등록되어 있었고, 웹사이트(`mafiacafe.kr`)를 보유하고 있어 크롤링 대상에 포함됐다.

---

## 2. 플랫폼 파악 — Next.js + 자체 REST API

응답 헤더로 즉시 확인:

```
x-powered-by: Next.js
```

Next.js 사이트는 대체로 두 가지 방식 중 하나다:
1. **SSR/SSG**: 서버에서 데이터를 완성해서 HTML로 내려줌 → HTML 파싱 가능
2. **CSR**: 클라이언트에서 fetch() → 별도 API 서버 탐색 필요

`/program` 페이지의 HTML 소스를 보면 실제 데이터가 없고,
JavaScript가 마운트된 후 API를 호출하는 CSR 방식임을 확인했다.

---

## 3. JS 번들 역공학

`/program` 페이지에서 로드되는 JS 파일 목록:

```
/_next/static/chunks/pages/program-c2af588eeba6d3a9018a.js
/_next/static/chunks/870-7773ef9c0d2c866780af.js
```

`program-*.js`에서 React Query 훅 발견:

```javascript
var h = function(){
  return (0,y.useQuery)("meetingList", v.Z.getMeetings)
}
var p = function(e,t,n){
  return (0,y.useQuery)("meetingCalendar", function(){
    return v.Z.getMeetingCalendar(e,t,n)
  })
}
var j = function(){
  return (0,y.useQuery)("locations", v.Z.getLocations)
}
```

`v`는 모듈 `9563`이고, 이 모듈은 `870-*.js`에 있었다.

`870-*.js`에서 API 클라이언트 발견:

```javascript
var d = "https://api.realmafia.kr"

// getMeetingCalendar
l().get(`${d}/web/meetings/calendar`, {
  params: {year: t, month: n, locationId: a},
  headers: {authorization: localStorage.getItem("token") || ""}
})

// getLocations
l().get(`${d}/web/locations`, {
  headers: {authorization: localStorage.getItem("token") || ""}
})
```

→ **API base URL: `https://api.realmafia.kr`**
→ **인증: Bearer 토큰이지만 빈 문자열("")로도 동작 (로그인 불필요)**

---

## 4. API 엔드포인트 발견

발견된 전체 엔드포인트 목록:

| 경로 | 설명 |
|------|------|
| `GET /web/locations` | 지점 목록 |
| `GET /web/meetings` | 전체 미팅 목록 (향후 몇 개) |
| `GET /web/meetings/calendar` | 월별 캘린더 |
| `GET /web/meeting/{id}` | 미팅 상세 |
| `GET /web/faqs` | FAQ |
| `POST /web/payment/pre` | 결제 사전 처리 |
| `POST /web/payment/complete` | 결제 완료 처리 |

크롤링에 사용하는 엔드포인트: **`GET /web/meetings/calendar`**

---

## 5. API 상세 명세

### 지점 목록

```
GET https://api.realmafia.kr/web/locations
Authorization: (빈 문자열)
Origin: https://www.mafiacafe.kr
```

응답:

```json
{
  "status": "success",
  "data": [
    {"id": 2, "name": "강남 1호점", "address": "서울시 강남구 강남대로 96길 19, 4층", "url": "https://naver.me/..."},
    {"id": 3, "name": "대구 동성로1호점", "address": "대구 중구 동성로1길 29-40, 3층"}
  ]
}
```

강남1호점의 `id = 2`.

### 월별 캘린더

```
GET https://api.realmafia.kr/web/meetings/calendar?year=2026&month=3&locationId=2
Authorization: (빈 문자열)
```

응답:

```json
{
  "status": "success",
  "data": {
    "3": [
      {
        "id": 1368,
        "title": "언데드마피아",
        "date": "2026-03-03T06:30:00.000Z",
        "currentNumber": 0,
        "maxNumber": 13,
        "isNumberAvailable": true,
        "thumbnail": {
          "originalPath": "https://realmafia.s3.amazonaws.com/...undead_thumbnail.jpg"
        },
        "location": {"id": 2, "name": "강남 1호점"}
      }
    ],
    "4": [...],
    ...
  }
}
```

응답 구조: `{일(day): [미팅, ...], ...}` — 일별 미팅 목록.

---

## 6. 데이터 구조 해석

각 미팅 항목의 주요 필드:

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | int | 미팅 고유 ID (예약 URL에 사용) |
| `title` | str | 프로그램명 (테마명) |
| `date` | str | UTC ISO8601 datetime |
| `isNumberAvailable` | bool | `true` = 예약 가능, `false` = 마감 |
| `currentNumber` | int | 현재 참가 신청 인원 |
| `maxNumber` | int | 최대 정원 |
| `thumbnail.originalPath` | str | 포스터 이미지 URL |

**`isNumberAvailable`가 `false`인데 `currentNumber = 0`인 경우**:
운영자가 수동으로 해당 세션을 비활성화했거나 내부 정책에 의해 블락된 것으로 추정.
→ `status = "full"`로 처리.

---

## 7. UTC → KST 변환

`date` 필드는 UTC이므로 KST(+9h)로 변환해야 한다.

```python
from datetime import timezone, timedelta

KST = timezone(timedelta(hours=9))

dt_utc = datetime.fromisoformat(meeting["date"].replace("Z", "+00:00"))
dt_kst = dt_utc.astimezone(KST)

target_date = dt_kst.date()   # 날짜 (KST 기준)
time_obj    = dtime(dt_kst.hour, dt_kst.minute)  # 시간 (KST 기준)
```

예시:

| UTC | KST |
|-----|-----|
| `2026-03-03T06:30:00.000Z` | `2026-03-03 15:30` |
| `2026-03-03T10:00:00.000Z` | `2026-03-03 19:00` |
| `2026-03-02T05:00:00.000Z` | `2026-03-02 14:00` |

---

## 8. 지점 식별 방법

캘린더 API에서 `locationId` 파라미터로 지점을 지정하기 때문에
반환되는 미팅은 모두 해당 지점의 것이다.

강남1호점의 API `locationId = 2`는 `/web/locations` 응답에서 확인.

```python
LOCATION_ID = 2  # 강남 1호점
```

---

## 9. booking_url 결정

각 미팅(세션)은 고유한 `id`를 가지므로 **슬롯별 직접 예약 링크**를 생성할 수 있다:

```python
booking_url = f"https://www.mafiacafe.kr/program/reservation/{meeting_id}"
```

이 URL로 이동하면 특정 날짜·시간의 해당 세션 예약 페이지로 바로 연결된다.
마감(full) 슬롯에는 `booking_url = None`.

---

## 10. DB 동기화 전략

마피아카페의 데이터 구조는 기존 방탈출과 다르다:

- **기존 방탈출**: 테마(고정) + 날짜별 반복 슬롯
- **마피아카페**: 테마(고정) + 개별 세션(미팅 id가 각자 다름)

하지만 DB에 저장하는 방식은 동일하게 `theme + schedule` 구조를 사용한다.
차이점: 각 슬롯의 `booking_url`이 개별 미팅 id를 포함.

```
월별 캘린더 조회 → 미팅별 파싱 → Theme upsert → Schedule upsert
```

현재 크롤링 범위: 이번 달 + 다음 달 (--months 2)

---

## 11. 실행 결과

```
============================================================
마피아카페 강남1호점 → DB 동기화
============================================================

[ 1단계 ] 캘린더 조회
  2026년 3월... (29일치 미팅)
  2026년 4월... (30일치 미팅)
  총 슬롯: 66개

[ 2단계 ] 테마 동기화
  테마: '언데드마피아' | poster=https://realmafia.s3.amazonaws.com/.../undead_thumbnail.jpg
  [NEW] 언데드마피아 (id=166)

[ 3단계 ] 스케줄 동기화
  2026-03-03: 가능 2개 / 마감 0개
  2026-03-10: 가능 1개 / 마감 1개
  2026-03-20: 가능 0개 / 마감 2개
  ...
  스케줄 동기화 완료: 66개 레코드 추가
```

---

## 12. 한계 및 주의사항

- **테마 단일**: 현재 강남점은 "언데드마피아" 한 가지 프로그램만 운영
  새 프로그램 추가 시 자동으로 테마 생성됨
- **세션 id 변경**: 미팅 id는 세션마다 다르므로 동일 날짜·시간의 슬롯도 재실행마다 booking_url이 달라질 수 있음
  → schedule upsert 시 status가 변경된 경우만 새 레코드 추가
- **대구점 미포함**: `locationId=3`은 대구점으로, 현재 강남점(id=2)만 수집
- **Authorization 헤더**: 현재 빈 문자열로 동작하지만, 향후 인증 필수로 변경될 가능성 있음
- **월별 API 호출**: 날짜별이 아닌 월별 조회라 API 호출 횟수 적음 (--months 2 → 2회 호출)
