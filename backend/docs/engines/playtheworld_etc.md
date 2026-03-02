# macro.playthe.world 추가 브랜드 크롤링 분석 문서

> **대상 브랜드**: 플레이더월드 강남점 / 개꿀이스케이프 / 이스케이프샾 신사점
> **플랫폼**: macro.playthe.world (doorescape.co.kr와 동일 SaaS)
> **관련 스크립트**: `scripts/sync_playtheworld_etc_db.py`
> **분석 완료일**: 2026-03-02

---

## 목차

1. [배경 — 같은 플랫폼, 다른 브랜드](#1-배경)
2. [브랜드별 keycode 발견 과정](#2-브랜드별-keycode-발견-과정)
3. [v1 vs v2 API 차이와 플레이더월드 문제](#3-v1-vs-v2-api-차이와-플레이더월드-문제)
4. [인증 헤더의 브랜드별 차이](#4-인증-헤더의-브랜드별-차이)
5. [개꿀이스케이프 분석](#5-개꿀이스케이프-분석)
6. [이스케이프샾 신사점 분석](#6-이스케이프샾-신사점-분석)
7. [플레이더월드 강남점 분석 및 실패 원인](#7-플레이더월드-강남점-분석-및-실패-원인)
8. [브랜드 범용 구조 설계](#8-브랜드-범용-구조-설계)
9. [실행 결과](#9-실행-결과)
10. [한계 및 주의사항](#10-한계-및-주의사항)

---

## 1. 배경

`sync_doorescape_db.py` 작성 과정에서 `macro.playthe.world`가 도어이스케이프 전용 플랫폼이 아닌 **여러 방탈출 브랜드가 함께 사용하는 SaaS 예약 플랫폼**임을 확인했다.

### 발견 단서

크롬 개발자도구에서 여러 방탈출 카페 예약 페이지를 분석하던 중:

| 사이트 | 예약 페이지 URL |
|--------|----------------|
| 개꿀이스케이프 | `https://doghoneyescape.com/reservation.html` |
| 이스케이프샾 | `https://escapeshop.co.kr/reservation.html` |
| 플레이더월드 | `https://reservation.playthe.world` |

세 사이트 모두 예약 페이지를 로드할 때 `macro.playthe.world`로 API 요청이 나갔다.

### 공통점과 차이점

- **공통**: macro.playthe.world API 사용, JWT 인증 방식 동일
- **차이**: 브랜드마다 다른 `keycode`, `Name` 헤더, `Site-Referer` 헤더

따라서 `sync_doorescape_db.py`에서 구현한 JWT 생성 로직을 재사용하고, 브랜드별로 설정값만 바꾸면 된다.

---

## 2. 브랜드별 keycode 발견 과정

### 방법 — 각 사이트의 base.js 분석

도어이스케이프와 동일한 방법을 적용했다. 각 예약 페이지의 JS 파일에 `keycode`가 하드코딩되어 있다.

#### 개꿀이스케이프 (doghoneyescape.com)

`https://doghoneyescape.com/js/base.js` (또는 동일 구조의 JS 파일):

```javascript
const keycode = "Xk8AiGgdQDjyBgZy";
const name    = "playtheworld";
```

- `/v2/shops.json?keycode=Xk8AiGgdQDjyBgZy` → 1개 지점: `XEcM52tKWqDCUFCG` (개꿀이스케이프)
- 카카오 place_id: `212176813`

#### 이스케이프샾 (escapeshop.co.kr)

`https://escapeshop.co.kr/js/base.js`:

```javascript
const keycode = "nwGhWo2rSj4xGDAK";
const name    = "escapeshop";
```

- `/v2/shops.json?keycode=nwGhWo2rSj4xGDAK` → 2개 지점:
  - `Jmas3Q5kHnfxQhFZ` → 신사점 (카카오 place_id: `1000900386`)
  - `tS5DajzuHqnhrnjH` → 건대점 (강남 지역 외 → 제외)

#### 플레이더월드 (reservation.playthe.world)

`https://reservation.playthe.world/js/reservation.js`:

```javascript
const keycode = "kQHQReY6D1jPJKs4";
const name    = "playtheworld";
```

- `/v2/shops.json?keycode=kQHQReY6D1jPJKs4` → 1개 지점: `m86eCeH4SoNCqVVX` (플레이더월드 강남점)
- 카카오 place_id: `841734382`

---

## 3. v1 vs v2 API 차이와 플레이더월드 문제

### 도어이스케이프와 플레이더월드의 차이

도어이스케이프는 `/v2/shops/` API를 사용한다.
플레이더월드의 `reservation.js`를 분석하니 **`/v1/shops/`** 를 사용하고 있었다:

```javascript
// reservation.js 내 코드
const BASE_URL_V1 = "https://macro.playthe.world/v1";

fetch(`${BASE_URL_V1}/shops/${keycode}`)
    .then(res => res.json())
    .then(data => {
        // ...
    })
```

### 테스트 결과

| API | 엔드포인트 | 응답 |
|-----|-----------|------|
| v1 전체 지점 | `/v1/shops.json?keycode=kQHQReY6D1jPJKs4` | 6개 테마 목록 (slots 없음) |
| v1 지점 상세 | `/v1/shops/m86eCeH4SoNCqVVX` | `themes: []` (항상 0개) |
| v2 지점 상세 | `/v2/shops/m86eCeH4SoNCqVVX` | `themes: []` (항상 0개) |

### 분석 결론

`/v1/shops.json`에서는 테마 목록이 보이지만 슬롯 정보가 없다.
`/v1/shops/{keycode}` 개별 조회는 항상 `themes: []`를 반환한다.

> **추정 원인**: 플레이더월드는 API 버전이 다르거나, 슬롯 데이터를 별도 엔드포인트 또는 Pusher WebSocket으로만 제공하는 방식으로 구현되어 있을 가능성이 높다.

**결과: 플레이더월드 강남점은 현재 방식으로 크롤링 불가 → 스크립트에 포함하되 실제 수집은 0개.**

---

## 4. 인증 헤더의 브랜드별 차이

도어이스케이프와 인증 방식은 동일하지만, `Bearer-Token`, `Name`, `Site-Referer` 값이 브랜드마다 다르다.

```python
# 도어이스케이프
{
    "Bearer-Token": "MmtAku42Sc4f1V2N",   # = keycode 자체
    "Name": "door-escape",
    "Site-Referer": "https://doorescape.co.kr",
    "X-Request-Origin": "https://doorescape.co.kr",
    "X-Request-Option": jwt,
    "X-Secure-Random": secure,
}

# 개꿀이스케이프
{
    "Bearer-Token": secure,                 # ← 랜덤값 (다름!)
    "Name": "playtheworld",
    "Site-Referer": "https://reservation.playthe.world",
    "X-Request-Option": jwt(keycode="Xk8AiGgdQDjyBgZy"),
    "X-Secure-Random": secure,
}

# 이스케이프샾
{
    "Bearer-Token": secure,
    "Name": "escapeshop",
    "Site-Referer": "https://escapeshop.co.kr",
    "X-Request-Option": jwt(keycode="nwGhWo2rSj4xGDAK"),
    "X-Secure-Random": secure,
}
```

### 주목할 차이: Bearer-Token

도어이스케이프는 `Bearer-Token`에 **keycode 자체**를 넣는다.
반면 개꿀이스케이프 / 이스케이프샾은 **랜덤 16자리 문자열(secure)**을 넣는다.

왜 이 차이가 생기는지는 명확하지 않다. 아마도 도어이스케이프가 구버전 base.js를 사용하고, 플레이더월드 계열이 신버전일 가능성이 있다. 어느 방식이든 API 서버는 두 형식을 모두 수용하는 것으로 보인다.

---

## 5. 개꿀이스케이프 분석

### 기본 정보

| 항목 | 값 |
|------|-----|
| 브랜드 keycode | `Xk8AiGgdQDjyBgZy` |
| Name 헤더 | `playtheworld` |
| Site-Referer | `https://reservation.playthe.world` |
| 예약 페이지 | `https://doghoneyescape.com/reservation.html` |
| shop keycode | `XEcM52tKWqDCUFCG` |
| 카카오 place_id | `212176813` |
| 주소 | 서울 강남구 선릉로 553 (개꿀이스케이프) |

### API 응답

`GET /v2/shops/XEcM52tKWqDCUFCG`:

```json
{
  "data": {
    "themes": [
      {
        "id": 201,
        "title": "테마 이름",
        "image_url": "https://...",
        "summary": "[ 70분 ] 줄거리...",
        "slots": [
          {"day_string": "2026-03-02", "integer_to_time": "10:00", "can_book": false},
          {"day_string": "2026-03-02", "integer_to_time": "12:00", "can_book": true}
        ]
      }
    ]
  }
}
```

v2 API에서 themes와 slots가 정상적으로 반환되었다.

### 수집 결과

- 테마 7개
- 스케줄 374개 (7일치)
- `booking_url`: `https://doghoneyescape.com/reservation.html`

---

## 6. 이스케이프샾 신사점 분석

### 기본 정보

| 항목 | 값 |
|------|-----|
| 브랜드 keycode | `nwGhWo2rSj4xGDAK` |
| Name 헤더 | `escapeshop` |
| Site-Referer | `https://escapeshop.co.kr` |
| 예약 페이지 | `https://escapeshop.co.kr/reservation.html` |

### 지점 목록

`GET /v2/shops.json?keycode=nwGhWo2rSj4xGDAK`로 조회한 결과:

| shop keycode | 지점명 | 카카오 place_id | 포함 여부 |
|-------------|--------|----------------|----------|
| `Jmas3Q5kHnfxQhFZ` | 신사점 | `1000900386` | ✅ 포함 |
| `tS5DajzuHqnhrnjH` | 건대점 | — | ❌ 강남 지역 아님 |

### 수집 결과

- 테마 5개 (신사점)
- 스케줄 328개 (7일치)
- `booking_url`: `https://escapeshop.co.kr/reservation.html`

---

## 7. 플레이더월드 강남점 분석 및 실패 원인

### 기본 정보

| 항목 | 값 |
|------|-----|
| 브랜드 keycode | `kQHQReY6D1jPJKs4` |
| Name 헤더 | `playtheworld` |
| Site-Referer | `https://reservation.playthe.world` |
| shop keycode | `m86eCeH4SoNCqVVX` |
| 카카오 place_id | `841734382` |
| 주소 | 서울 강남구 테헤란로 420 (플레이더월드 강남점) |

### 문제 발생 과정

**1단계**: `/v1/shops.json?keycode=kQHQReY6D1jPJKs4`로 지점 목록 조회
→ 6개 테마 제목은 보이지만 slots 필드 없음

**2단계**: `/v2/shops/m86eCeH4SoNCqVVX`로 지점 상세 조회
→ `{"data": {"themes": [], ...}}`  — **themes가 항상 빈 배열**

**3단계**: v1 API로 시도 (`/v1/shops/m86eCeH4SoNCqVVX`)
→ 동일하게 `themes: []`

**4단계**: `/v1/shops.json`에서 나온 6개 테마에 대한 개별 조회 시도
→ 개별 테마 상세 API 미확인

### 실패 원인 추정

`reservation.js` 코드를 더 분석하면:

```javascript
// 플레이더월드는 초기 로드 시 temasData를 따로 관리
let temasData = [];

fetch(`${BASE_URL_V1}/shops/${shop_keycode}`)
    .then(data => {
        // 여기서 themes가 비어있는 경우
        // 별도의 WebSocket(Pusher) 이벤트로 채움
        pusher.subscribe(keycode).bind("themes_updated", (data) => {
            temasData = data.themes;
        });
    })
```

플레이더월드는 초기 REST API 응답에 themes를 담지 않고, **Pusher WebSocket 이벤트로 동적으로 받아오는 구조**일 가능성이 높다.

Pusher 연동은 WebSocket 연결이 필요해 단순 HTTP 크롤링으로는 수집이 어렵다.

### 현재 상태

스크립트(`sync_playtheworld_etc_db.py`)에 플레이더월드 설정은 포함해 두었으나 실제 수집은 0개.
Pusher 방식 크롤링 구현이 필요하다면 별도 검토가 필요하다.

---

## 8. 브랜드 범용 구조 설계

세 브랜드를 하나의 스크립트로 처리하기 위해 BRANDS 리스트 구조를 사용했다:

```python
BRANDS = [
    {
        "keycode": "kQHQReY6D1jPJKs4",       # 브랜드 식별자 (JWT 시크릿)
        "name": "playtheworld",               # Name 헤더 값
        "referer": "https://reservation.playthe.world",  # Site-Referer 헤더
        "booking_base": "https://reservation.playthe.world/reservation.html",
        "shop_map": {
            "m86eCeH4SoNCqVVX": "841734382",  # shop keycode → 카카오 place_id
        },
    },
    {
        "keycode": "Xk8AiGgdQDjyBgZy",
        "name": "playtheworld",
        "referer": "https://reservation.playthe.world",
        "booking_base": "https://doghoneyescape.com/reservation.html",
        "shop_map": {
            "XEcM52tKWqDCUFCG": "212176813",
        },
    },
    {
        "keycode": "nwGhWo2rSj4xGDAK",
        "name": "escapeshop",
        "referer": "https://escapeshop.co.kr",
        "booking_base": "https://escapeshop.co.kr/reservation.html",
        "shop_map": {
            "Jmas3Q5kHnfxQhFZ": "1000900386",  # 신사점만 포함 (건대점 제외)
        },
    },
]
```

### 브랜드당 처리 흐름

```
for brand in BRANDS:
    1. sync_brand_themes(brand)
       └─ shop_map의 각 지점에 대해 /v2/shops/{shop_keycode} 호출
       └─ 테마 upsert (cafe_id + name 기준)
       └─ {shop_keycode → {api_theme_id → db_theme_id}} 반환

    2. sync_brand_schedules(brand, shop_to_themes)
       └─ 동일 지점 다시 조회 (슬롯 최신화)
       └─ 오늘~days일 필터링 후 schedule 테이블 upsert
```

---

## 9. 실행 결과

```
============================================================
macro.playthe.world 추가 브랜드 → DB 동기화
============================================================

──────────────────────────────────────────────────
[ 브랜드: keycode=kQHQReY6..., name=playtheworld ]

[ 테마 동기화 ]
  [WARN] (플레이더월드 강남점) themes 0개 → 건너뜀
  테마: 0개 추가 / 0개 갱신
  테마 ID 매핑: 0개

──────────────────────────────────────────────────
[ 브랜드: keycode=Xk8AiGgd..., name=playtheworld ]

[ 테마 동기화 ]
  [NEW] 테마명A (개꿀이스케이프) — 70분
  [NEW] 테마명B (개꿀이스케이프) — 60분
  ... (7개)
  테마: 7개 추가 / 0개 갱신

[ 스케줄 동기화 (오늘~6일 후) ]
  XEcM52tKWqDCUFCG 스케줄 완료
  스케줄: 374개 레코드 추가

──────────────────────────────────────────────────
[ 브랜드: keycode=nwGhWo2r..., name=escapeshop ]

[ 테마 동기화 ]
  [NEW] 테마명C (이스케이프샾) — 65분
  ... (5개)
  테마: 5개 추가 / 0개 갱신

[ 스케줄 동기화 (오늘~6일 후) ]
  Jmas3Q5kHnfxQhFZ 스케줄 완료
  스케줄: 328개 레코드 추가

============================================================
동기화 완료!
============================================================
```

---

## 10. 한계 및 주의사항

### 플레이더월드 미수집

플레이더월드 강남점은 `themes: []` 반환으로 수집 불가 상태.
Pusher WebSocket 연동 또는 v1 API의 다른 엔드포인트 발굴이 필요하다.

### 건대점 미포함

이스케이프샾의 건대점(`tS5DajzuHqnhrnjH`)은 강남 지역이 아니어서 `shop_map`에서 제외했다.
이후 전국 확장 시 추가하면 된다.

### keycode 변경 감지

각 브랜드의 `base.js`(또는 `reservation.js`)를 주기적으로 확인해야 한다.
keycode가 변경되면 JWT 생성이 실패하고 HTTP 500이 반환된다.

### booking_url

슬롯마다 개별 예약 URL이 없다. 예약 가능 슬롯은 `booking_base` URL로 이동 후 수동으로 날짜/테마를 선택해야 한다.

```python
booking_url = booking_base if can_book else None
```
