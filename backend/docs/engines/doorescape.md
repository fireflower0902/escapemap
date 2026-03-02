# doorescape.co.kr 크롤링 분석 문서

> **대상 사이트**: https://doorescape.co.kr
> **운영사**: 도어이스케이프
> **관련 스크립트**: `scripts/sync_doorescape_db.py`
> **관련 엔진**: `app/engines/doorescape.py`
> **분석 완료일**: 2026-03-02

---

## 목차

1. [배경 — 왜 이 사이트를 분석했는가](#1-배경)
2. [xdungeon·keyescape와 근본적으로 다른 구조](#2-xdungeankeyescape와-근본적으로-다른-구조)
3. [macro.playthe.world 플랫폼 발견 과정](#3-macroplaytheworldcom-플랫폼-발견-과정)
4. [base.js 분석 — 인증 메커니즘 파악](#4-basejs-분석--인증-메커니즘-파악)
5. [JWT 인증 역공학](#5-jwt-인증-역공학)
6. [Python에서 JWT 구현](#6-python에서-jwt-구현)
7. [SSL 인증서 문제와 해결](#7-ssl-인증서-문제와-해결)
8. [API 엔드포인트 상세](#8-api-엔드포인트-상세)
9. [지점 매핑 발견 과정](#9-지점-매핑-발견-과정)
10. [summary 필드에서 정보 추출](#10-summary-필드에서-정보-추출)
11. [booking_url 결정 방식](#11-booking_url-결정-방식)
12. [DB 연동 및 동기화 전략](#12-db-연동-및-동기화-전략)
13. [실행 결과](#13-실행-결과)
14. [한계 및 주의사항](#14-한계-및-주의사항)

---

## 1. 배경

DB에는 도어이스케이프 지점이 강남가든점, 신논현레드점, 신논현블루점을 포함해 여러 개 등록되어 있었고, 모두 테마가 0개였다.

도어이스케이프 홈페이지 접속 시 기존에 분석한 xdungeon, keyescape와 전혀 다른 UI 구조가 보였다. 화면이 훨씬 현대적이었고, 예약 선택 화면이 SPA처럼 동작했다.

---

## 2. xdungeon·keyescape와 근본적으로 다른 구조

### xdungeon (비트포비아) 방식
- 완전한 SSR (서버사이드 렌더링)
- HTML에 예약 현황이 이미 담겨 있음
- `requests + BeautifulSoup`으로 직접 파싱 가능

### keyescape 방식
- PHP 기반 자체 개발 시스템
- 같은 회사 서버에 AJAX로 JSON을 요청
- PHP 파일 하나(`run_proc.php`)가 라우터 역할

### doorescape 방식 (처음 발견 시점)
- 화면이 SPA처럼 부드럽게 전환됨
- 예약 페이지가 `reservation.html` — **확장자가 `.html`인데 내용이 동적으로 바뀜**
- 날짜를 선택하면 외부 도메인으로 요청이 나감

이 시점에서 이미 예감이 왔다: **외부 SaaS 예약 플랫폼을 사용하고 있다**.

---

## 3. macro.playthe.world 플랫폼 발견 과정

### 3-1. Network 탭 관찰

크롬 개발자도구 → Network 탭에서 `https://doorescape.co.kr`의 예약 페이지를 열면:

```
GET https://macro.playthe.world/v2/shops/aAo1RDEnfyPkbeix
```

`doorescape.co.kr`과 전혀 다른 도메인 `macro.playthe.world`로 요청이 나가는 것이 확인됐다.

### 3-2. base.js 파일 분석

페이지 소스에서 외부 JS 파일들을 확인했다. 그 중 `https://doorescape.co.kr/js/base.js` 파일에 핵심 설정이 모두 담겨 있었다:

```javascript
const keycode = "MmtAku42Sc4f1V2N"; // Brand Keycode
const baseUrl = "https://macro.playthe.world";
const PUSHERKEY = "3473fff52b16af519867";
```

여기서 세 가지 중요한 정보를 얻었다:

1. **`keycode`**: 도어이스케이프가 macro 플랫폼에서 사용하는 브랜드 식별자
2. **`baseUrl`**: 실제 API 서버 주소
3. **`PUSHERKEY`**: [Pusher](https://pusher.com/) WebSocket 서비스 키 → 실시간 예약 상태 업데이트에 사용

### 3-3. macro.playthe.world 정체

검색 결과와 사이트 분석으로 파악한 것:
- **playthe.world**: 방탈출 카페 전용 SaaS 예약 플랫폼
- 도어이스케이프, 그리고 다른 방탈출 카페들이 이 플랫폼을 사용
- `keycode`로 브랜드(업체)를 구분, `shop_keycode`로 지점을 구분
- Pusher로 실시간 예약 현황을 WebSocket으로 push

→ **직접 `macro.playthe.world` API를 호출하면 모든 예약 현황을 가져올 수 있다.**

---

## 4. base.js 분석 — 인증 메커니즘 파악

처음 API를 그냥 호출했을 때:

```bash
curl "https://macro.playthe.world/v2/shops/aAo1RDEnfyPkbeix"
```

**결과: HTTP 500 (빈 응답)**

도어이스케이프 사이트처럼 동일한 URL이지만 인증 없이는 실패하는 것이다.

`base.js`의 전체 내용을 읽어보니 `$.ajaxSetup()`으로 **모든 AJAX 요청에 공통 헤더를 붙이는** 코드가 있었다:

```javascript
const SECURERANDOM = !sessionStorage.getItem("SECURECODE")
    ? generateSecure(16)
    : sessionStorage.getItem("SECURECODE");
sessionStorage.setItem("SECURECODE", SECURERANDOM);

$(function () {
    let token = createJWT(keycode, SECURERANDOM);
    $.ajaxSetup({
        headers: {
            "Bearer-Token": keycode,
            "Name": "door-escape",
            "Site-Referer": "https://doorescape.co.kr",
            "X-Request-Origin": "https://doorescape.co.kr",
            "X-Request-Option": token,      // ← JWT 토큰
            "X-Secure-Random": SECURERANDOM // ← 랜덤 문자열
        }
    })
    ...
```

인증 메커니즘 정리:

1. 페이지 로드 시 16자리 랜덤 문자열(`SECURERANDOM`) 생성 + sessionStorage 저장
2. `createJWT(keycode, SECURERANDOM)`으로 JWT 생성
3. 이후 모든 API 요청에 6개의 커스텀 헤더 추가

---

## 5. JWT 인증 역공학

`base.js`에 `createJWT` 함수 구현이 있었다:

```javascript
const createJWT = (key, token) => {
    var header = {
        "alg": "HS256",
        "typ": "JWT"
    };
    var payload = {
        "X-Auth-Token": token,       // SECURERANDOM 값
        "expired_at": (new Date().getTime() / 1000) + 3600  // 1시간 뒤 만료
    };
    var secret = key;  // Brand Keycode = "MmtAku42Sc4f1V2N"

    var sJWT = KJUR.jws.JWS.sign("HS256", sHeader, sPayload, secret);
    return sJWT;
}
```

### JWT 구조 분석

| 구성요소 | 내용 |
|---------|------|
| 알고리즘 | HS256 (HMAC-SHA256) |
| 시크릿 | Brand Keycode (`MmtAku42Sc4f1V2N`) |
| payload.X-Auth-Token | SECURERANDOM (16자리 랜덤) |
| payload.expired_at | 현재 Unix 타임스탬프 + 3600초 |

### 왜 이 인증이 완벽히 보호되지 않는가

일반적인 JWT는 서버가 발급하고 클라이언트가 보관한다. 그런데 이 경우:
- **시크릿(keycode)이 클라이언트 JavaScript에 하드코딩**되어 있다
- 누구나 `base.js`를 읽으면 keycode를 알 수 있다
- 따라서 누구나 유효한 JWT를 직접 생성할 수 있다

이는 보안상 취약점이지만, API를 역공학하는 입장에서는 오히려 좋다.
공식 클라이언트(브라우저의 JS)가 하는 것과 똑같이 Python에서 JWT를 만들면 된다.

---

## 6. Python에서 JWT 구현

`jsrsasign` 라이브러리(`KJUR.jws.JWS.sign`)의 HS256 JWT 생성을 Python 표준 라이브러리로 재구현했다. 외부 패키지를 최소화하기 위해 `PyJWT`를 쓰지 않고 직접 구현:

```python
import base64, hashlib, hmac, json, time, random, string

def _b64url(data: bytes | str) -> str:
    """URL-safe Base64 인코딩 (패딩 제거)"""
    if isinstance(data, str):
        data = data.encode()
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

def _create_jwt(keycode: str, secure_random: str) -> str:
    """
    JavaScript의 createJWT(key, token)을 Python으로 재구현.
    keycode = Brand Keycode (시크릿)
    secure_random = 16자리 랜덤 문자열
    """
    header = json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":"))
    payload = json.dumps(
        {
            "X-Auth-Token": secure_random,
            "expired_at": int(time.time()) + 3600,
        },
        separators=(",", ":"),
    )
    # JWT 서명 대상: Base64URL(header) + "." + Base64URL(payload)
    msg = f"{_b64url(header)}.{_b64url(payload)}"

    # HMAC-SHA256으로 서명
    sig = hmac.new(keycode.encode(), msg.encode(), hashlib.sha256).digest()

    return f"{msg}.{_b64url(sig)}"
```

### 처음 시도한 방법과 실패

처음에는 `hmac.new()` 대신 `hmac.new()`를 `hmac.HMAC()` 방식으로 호출했는데, Python 3.14에서 경고가 나왔다. 그냥 `hmac.new()`를 유지.

더 중요한 실패: **JSON 직렬화 순서 문제**

Python의 `json.dumps()`는 기본적으로 키 순서를 보장하지 않는다(Python 3.7+는 삽입 순서 유지).
`separators=(",", ":")`를 사용해 공백 없이 직렬화해야 JWT가 올바르게 생성된다.

```python
# 잘못된 방법 (공백 포함)
json.dumps({"alg": "HS256", "typ": "JWT"})
# → '{"alg": "HS256", "typ": "JWT"}'  ← 공백이 Base64 인코딩에 영향

# 올바른 방법
json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":"))
# → '{"alg":"HS256","typ":"JWT"}'
```

### 요청 헤더 조합

```python
def _make_auth_headers() -> dict:
    chars = string.ascii_letters + string.digits
    secure = "".join(random.choices(chars, k=16))
    jwt = _create_jwt(BRAND_KEYCODE, secure)

    return {
        "Bearer-Token": BRAND_KEYCODE,
        "Name": "door-escape",
        "Site-Referer": "https://doorescape.co.kr",
        "X-Request-Origin": "https://doorescape.co.kr",
        "X-Request-Option": jwt,
        "X-Secure-Random": secure,
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 ...",
    }
```

---

## 7. SSL 인증서 문제와 해결

JWT 인증 헤더를 완성하고 테스트했다:

```python
import urllib.request
req = urllib.request.Request(url, headers=_make_auth_headers())
with urllib.request.urlopen(req) as r:
    data = r.read()
```

**결과:**
```
ssl.SSLError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed:
unable to get local issuer certificate (_ssl.c:1081)
```

### 원인

`macro.playthe.world` 서버의 SSL 인증서 체인에 문제가 있다. 중간 인증서(Intermediate CA)가 누락되어 있어서 클라이언트가 루트 CA까지 체인을 완성하지 못한다. 브라우저는 자체적으로 인증서 체인을 캐싱/복구하는 기능이 있어서 오류가 없지만, Python의 `urllib` / `requests`는 엄격하게 검증한다.

### 해결 방법 선택

**옵션 1 — 특정 CA 인증서 번들 지정**: 서버 인증서를 받아서 Python이 신뢰하도록 추가. 복잡하고 유지보수 어려움.

**옵션 2 — SSL 검증 비활성화**: 보안 위험이 있지만, 이 스크립트는 내부 크롤링 용도이며 공개 웹 서비스를 읽는 것이므로 실용적인 선택.

```python
import ssl

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE
```

`aiohttp`에서도 동일하게:
```python
aiohttp.TCPConnector(ssl=_SSL_CTX)
```

**주의**: 이 설정은 MITM(중간자 공격)에 취약해지므로 프로덕션 환경의 민감한 데이터 전송에는 사용하면 안 된다. 우리 케이스에서는 읽기 전용 크롤링이므로 허용 가능.

---

## 8. API 엔드포인트 상세

### 8-1. 전체 지점 목록 API

```
GET https://macro.playthe.world/v2/shops.json?keycode=MmtAku42Sc4f1V2N
```

**응답 구조:**
```json
{
  "result": "success",
  "data": [
    {
      "id": 30,
      "keycode": "aAo1RDEnfyPkbeix",
      "name": "강남 가든점",
      "address": "서울 서초구 사평대로56길 10, 지하 1층",
      "contact": "02-535-9745",
      "image_url": "https://...",
      "brand_site_url": "https://doorescape.co.kr/reservation.html?keycode=aAo1RDEnfyPkbeix",
      "themes": [
        {"id": 169, "...": "..."}
      ]
    },
    ...
  ]
}
```

이 엔드포인트로 모든 지점의 keycode를 한 번에 수집할 수 있다.

### 8-2. 지점 상세 API

```
GET https://macro.playthe.world/v2/shops/{shop_keycode}
```

**응답 구조:**
```json
{
  "result": "success",
  "data": {
    "shop": {
      "id": 30,
      "name": "강남 가든점",
      "address": "서울 서초구 사평대로56길 10",
      "contact": "02-535-9745",
      "coordinates_x": "127.023007777275",
      "coordinates_y": "37.5030568232159",
      "start_date": "2026-01-01",
      "end_date": "2026-12-31",
      "price_image_url": "https://...",
      "event_image_url": "https://..."
    },
    "themes": [
      {
        "id": 169,
        "title": "출동",
        "image_url": "https://playtheworld-opengame.s3.ap-northeast-2.amazonaws.com/...",
        "summary": "[ 70분 ] 난이도: <img ...> 줄거리...",
        "description": "상세 설명...",
        "slots": [
          {
            "id": 12345,
            "day_string": "2026-03-02",
            "integer_to_time": "10:50",
            "can_book": false
          },
          {
            "id": 12346,
            "day_string": "2026-03-02",
            "integer_to_time": "12:20",
            "can_book": true
          }
        ]
      }
    ],
    "token": "..."
  }
}
```

### 슬롯 필드 설명

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | int | 슬롯 고유 ID (Pusher 실시간 업데이트에 사용) |
| `day_string` | str | 날짜 (YYYY-MM-DD) |
| `integer_to_time` | str | 시작 시간 (HH:MM) |
| `can_book` | bool | **true = 예약 가능, false = 마감** |

### summary 필드의 HTML 포함

`summary` 필드에는 순수 텍스트가 아닌 **HTML이 그대로 들어있다**:

```
"summary": "[ 70분 ] 난이도: <img id=\"se_object_14547302011365818\" src=\"https://ssl.pstatic.net/...\"> 줄거리..."
```

이유: 네이버 스마트에디터로 작성한 내용을 raw HTML 그대로 저장한 것으로 추정.
파싱 시 HTML 태그를 제거해야 한다:

```python
import re
clean_summary = re.sub(r"<[^>]+>", "", summary).strip()
```

---

## 9. 지점 매핑 발견 과정

### 방법 1 — shops.json으로 전체 지점 keycode 수집

```python
data = get_api("/v2/shops.json?keycode=MmtAku42Sc4f1V2N")
for shop in data["data"]:
    print(f"id={shop['id']} keycode={shop['keycode']} name={shop['name']}")
```

결과:
```
id=30 keycode=aAo1RDEnfyPkbeix name=강남 가든점
id=33 keycode=NeZqzMtPCBsSvbAq name=신논현 레드점
id=34 keycode=yGozPSZSJXwrzbin name=신논현 블루점
id=35 keycode=o83TaXbnod8DtEX5 name=홍대점
id=32 keycode=h1i4d4YyEfBctnpQ name=이수역점
id=31 keycode=DGpkkgMQYaNLYXTZ name=안산점
id=36 keycode=fGDxtefVDEyWczai name=대전유성 NC백화점
id=70 keycode=FgBZDHfrR8p5UDmF name=부평점
```

### 방법 2 — DB의 카카오 place_id와 매핑

shop `name`과 카카오 DB의 `branch_name`을 비교해서 연결:

| shop keycode | 지점명 | DB cafe.id | DB name / branch_name |
|-------------|--------|------------|----------------------|
| aAo1RDEnfyPkbeix | 강남 가든점 | 691418241 | 도어이스케이프 / 강남가든점 |
| NeZqzMtPCBsSvbAq | 신논현 레드점 | 765336936 | 도어이스케이프 레드 / 신논현점 |
| yGozPSZSJXwrzbin | 신논현 블루점 | 2058736611 | 도어이스케이프 블루 / 신논현점 |
| o83TaXbnod8DtEX5 | 홍대점 | 153136502 | 도어이스케이프 / 홍대점 |
| h1i4d4YyEfBctnpQ | 이수역점 | 190103388 | 도어이스케이프 / 이수역점 |
| DGpkkgMQYaNLYXTZ | 안산점 | 27609271 | 도어이스케이프 / None (안산) |
| fGDxtefVDEyWczai | 대전유성 NC백화점 | 1836271694 | 도어이스케이프 / 대전유성NC백화점 |
| FgBZDHfrR8p5UDmF | 부평점 | 1460830485 | 도어이스케이프 / 부평점 |

대전, 안산, 부평은 강남 지역은 아니지만 같은 브랜드(도어이스케이프)이므로 함께 수집한다.

### 강남 지역 지점 (강남·서초 주소)

- 강남가든점: 서울 서초구 사평대로56길 10
- 신논현레드점: 서울 서초구 사평대로 360
- 신논현블루점: 서울 서초구 사평대로53길 8-1

---

## 10. summary 필드에서 정보 추출

### duration_min 추출

summary에는 `[ N분 ]` 형식으로 소요 시간이 들어있다:

```
[ 70분 ] 난이도: <img...> 줄거리...
```

정규표현식:
```python
def parse_duration(summary: str) -> int | None:
    m = re.search(r"\[\s*(\d+)\s*분\s*\]", summary or "")
    return int(m.group(1)) if m else None
```

### difficulty 추출

일부 테마는 summary에 "난이도: 숫자" 형식이 없고, 네이버 블로그에서 퍼온 별 이미지(`<img>`)로 난이도를 표현한다. 이미지는 HTML 태그를 제거하면 사라지므로 수치로 추출하기 어렵다.

```python
def parse_difficulty(summary: str) -> int | None:
    m = re.search(r"난이도\s*[:\s]+(\d+)", summary or "")
    if m:
        return max(1, min(5, int(m.group(1))))
    return None
```

결과: 대부분의 테마에서 `difficulty = None`.

### 실제 파싱 결과

```
출동 (도어이스케이프) — 70분 (difficulty=None)
Insert Coin (도어이스케이프) — 60분 (difficulty=None)
둘이라면 (도어이스케이프) — 60분 (difficulty=None)
유전 (도어이스케이프 레드) — 75분 (difficulty=None)
LUCKY (도어이스케이프 레드) — None분 (이미지로만 표현됨)
```

---

## 11. booking_url 결정 방식

도어이스케이프 API의 슬롯에는 직접 예약할 수 있는 URL이 없다.
사용자는 아래 URL에서 날짜와 테마를 선택해 예약한다:

```
https://doorescape.co.kr/reservation.html?keycode={shop_keycode}
```

예약 가능 슬롯의 `booking_url`:
```python
booking_url = f"https://doorescape.co.kr/reservation.html?keycode={shop_keycode}"
```

마감 슬롯은 `booking_url = None`.

---

## 12. DB 연동 및 동기화 전략

### 핵심 차이 — 데이터 범위

xdungeon, keyescape는 **날짜를 파라미터로 넘겨서 조회**한다. 따라서 오늘~N일치를 N번 호출해야 한다.

도어이스케이프(macro.playthe.world)는 **지점 하나 조회 시 전체 슬롯이 한 번에 온다**. 과거부터 미래까지 운영 가능한 모든 날짜의 슬롯이 포함된다.

→ 따라서 스케줄 동기화 시 "오늘~N일치 필터링"을 클라이언트에서 직접 해야 한다.

```python
# 오늘부터 days일 후까지의 날짜 문자열 집합
target_dates = {
    (today + timedelta(days=i)).strftime("%Y-%m-%d")
    for i in range(days + 1)
}

# 슬롯 순회 시 날짜 필터 적용
for slot in theme["slots"]:
    if slot["day_string"] not in target_dates:
        continue
    ...
```

### 과거 슬롯 제외

이미 지난 시간대(오늘이지만 현재 시각 이전)는 저장하지 않음:

```python
slot_dt = datetime(d.year, d.month, d.day, hh, mm)
if slot_dt <= datetime.now():
    continue
```

### 테마 upsert

- `cafe_id` + `title(name)` 조합으로 기존 테마 조회
- 없으면 INSERT, 있으면 UPDATE
- `image_url`이 있으면 `poster_url`로 저장 (도어이스케이프는 S3에 저장된 실제 이미지 제공)

```python
image_url = t.get("image_url") or None
```

---

## 13. 실행 결과

```
============================================================
doorescape.co.kr → DB 동기화
============================================================

[ 1단계 ] 테마 동기화
  [NEW] 출동 (도어이스케이프) — 70분
  [NEW] Insert Coin (도어이스케이프) — 60분
  [NEW] 둘이라면 (도어이스케이프) — 60분
  [NEW] Imagine (도어이스케이프) — 70분
  [NEW] LUCKY (도어이스케이프 레드) — None분
  [NEW] 비 (도어이스케이프 레드) — None분
  [NEW] 유전 (도어이스케이프 레드) — 75분
  [NEW] TRUTH (도어이스케이프 블루) — None분
  [NEW] 이방인 (도어이스케이프 블루) — None분
  ... (총 28개)

  테마 동기화 완료: 28개 추가 / 0개 갱신
  테마 ID 매핑: 28개

[ 2단계 ] 스케줄 동기화 (오늘~6일 후)
  aAo1RDEnfyPkbeix 완료
  NeZqzMtPCBsSvbAq 완료
  yGozPSZSJXwrzbin 완료
  o83TaXbnod8DtEX5 완료
  h1i4d4YyEfBctnpQ 완료
  DGpkkgMQYaNLYXTZ 완료
  fGDxtefVDEyWczai 완료
  FgBZDHfrR8p5UDmF 완료

  스케줄 동기화 완료: 1718개 레코드 추가
```

---

## 14. 한계 및 주의사항

### keycode 하드코딩

`BRAND_KEYCODE = "MmtAku42Sc4f1V2N"`은 doorescape의 `base.js`에서 추출한 값이다.
이 값은 변경될 수 있으며, 변경 시 모든 API 호출이 실패한다. 정기적으로 `base.js`를 확인해야 한다.

### SSL 검증 비활성화

`macro.playthe.world`의 인증서 체인 오류로 인해 SSL 검증을 비활성화했다.
이 서버의 인증서 문제가 해결되면 검증을 다시 활성화하는 것이 권장된다.

### difficulty 정보 없음

대부분의 테마 summary가 난이도를 별 이미지로 표현해서 숫자로 추출 불가.
수동 보완 또는 다른 소스(네이버 플레이스, 공식 인스타그램 등)에서 추가 수집 필요.

### 전체 슬롯 로드 방식

지점 상세 API 한 번 호출에 전체 슬롯(수백 개)이 온다. 특정 날짜만 빠르게 확인하고 싶어도 항상 전체를 받아야 한다. 네트워크/처리 비용이 keyescape보다 높다.

### Pusher 실시간 업데이트

도어이스케이프는 Pusher WebSocket으로 실시간 예약 현황 변경을 push한다.
현재 크롤러는 이를 활용하지 않고 polling(주기적 전체 동기화)만 한다.
실시간 알림 정확도를 높이려면 Pusher 채널(`keycode`)을 구독하면 된다.

```javascript
// 브라우저에서 Pusher 구독 방식 (참고용)
const channel = pusher.subscribe(keycode);
channel.bind('update', function(data) {
    // data.data.theme_id, data.data.id, data.data.can_book
});
```

### 정적 매핑 테이블

`SHOP_MAP` 딕셔너리는 하드코딩. 신규 지점이 추가되거나 keycode가 변경되면 수동 업데이트 필요.
`/v2/shops.json` 엔드포인트를 동적으로 호출하면 자동화 가능하지만, 새 지점의 카카오 place_id 매핑은 여전히 수동으로 해야 한다.
