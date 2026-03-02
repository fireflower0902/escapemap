# keyescape.com 크롤링 분석 문서

> **대상 사이트**: https://keyescape.com
> **운영사**: 키이스케이프
> **관련 스크립트**: `scripts/sync_keyescape_db.py`
> **관련 엔진**: `app/engines/keyescape.py`
> **분석 완료일**: 2026-03-02

---

## 목차

1. [배경 — 왜 이 사이트를 분석했는가](#1-배경)
2. [첫 번째 접근 — 화면 구조 파악](#2-첫-번째-접근--화면-구조-파악)
3. [두 번째 접근 — Network 탭 분석](#3-두-번째-접근--network-탭-분석)
4. [API 엔드포인트 역공학](#4-api-엔드포인트-역공학)
5. [파라미터 이름 오류와 해결 과정](#5-파라미터-이름-오류와-해결-과정)
6. [테마 목록 API 상세](#6-테마-목록-api-상세)
7. [스케줄(시간 슬롯) API 상세](#7-스케줄시간-슬롯-api-상세)
8. [지점 매핑 발견 과정](#8-지점-매핑-발견-과정)
9. [memo 필드에서 정보 추출](#9-memo-필드에서-정보-추출)
10. [포스터 이미지 수집 실패와 이유](#10-포스터-이미지-수집-실패와-이유)
11. [booking_url 결정 방식](#11-booking_url-결정-방식)
12. [DB 연동 및 동기화 전략](#12-db-연동-및-동기화-전략)
13. [실행 결과](#13-실행-결과)
14. [한계 및 주의사항](#14-한계-및-주의사항)

---

## 1. 배경

강남 방탈출 카페 크롤링 대상을 선정하면서 키이스케이프를 확인했다.
DB에는 키이스케이프 지점이 강남점, 더오름, 우주라이크, 메모리컴퍼니, 로그인1/2, STATION, 후즈데어 등 **11개 지점**이 등록되어 있었고, 모두 테마 수가 0이었다.
→ 즉 카카오맵에서 카페 위치 정보는 있지만, 예약 가능 여부는 전혀 수집되지 않은 상태였다.

가장 먼저 할 일은 "**키이스케이프가 어떤 방식으로 예약을 처리하는가**"를 파악하는 것이었다.

---

## 2. 첫 번째 접근 — 화면 구조 파악

키이스케이프 공식 사이트(keyescape.com)에 접속하면 예약 페이지는 `reservation1.php`에 있다.
`?zizum_num=3` 같은 쿼리스트링으로 지점을 선택한다.

```
https://keyescape.com/reservation1.php?zizum_num=3
```

처음 본 화면의 특징:
- 지점 선택 드롭다운 (`<select>`)
- 날짜 선택 달력 (jQuery Datepicker 스타일)
- 테마 목록 + 각 테마의 시간 슬롯

화면만 보면 **서버사이드 렌더링(SSR)처럼 보이지 않았다**.
페이지 소스를 보니 `div#theme_wrap`이 비어 있었고, 날짜를 선택하거나 지점을 바꾸면 JavaScript가 동적으로 내용을 채우는 구조였다.

→ **xdungeon.net과 달리 단순한 HTML 파싱으로는 예약 현황을 가져올 수 없다**는 것을 확인했다.

---

## 3. 두 번째 접근 — Network 탭 분석

크롬 개발자도구(F12) → Network 탭 → "Fetch/XHR" 필터를 켜고 날짜와 지점을 바꿔봤다.

요청 목록에서 반복적으로 나타나는 URL:

```
POST https://keyescape.com/controller/run_proc.php
```

**왜 PHP인가?**
파일명 `run_proc.php`에서 보이듯, 키이스케이프는 React/Vue 같은 현대적인 SPA가 아니라 **PHP로 구현된 서버사이드 시스템**이다. 프론트엔드 JavaScript가 jQuery의 `$.ajax()`로 같은 PHP 백엔드에 요청을 보내고, 백엔드가 JSON을 반환하는 구조다.

### 발견된 요청 예시

날짜를 클릭할 때:
```
POST /controller/run_proc.php
Content-Type: application/x-www-form-urlencoded

t=get_theme_time&date=2026-03-02&zizumNum=3&themeNum=7&endDay=0
```

지점을 바꿀 때:
```
POST /controller/run_proc.php
Content-Type: application/x-www-form-urlencoded

t=get_theme_info_list&zizum_num=3
```

`t=` 파라미터가 **어떤 액션을 실행할지** 결정한다는 것을 알았다. 마치 RESTful API의 엔드포인트 역할을 하나의 파일에서 `t` 파라미터로 라우팅하는 방식이다.

---

## 4. API 엔드포인트 역공학

두 가지 API가 핵심이었다.

### 4-1. 테마 목록 API

```
POST https://keyescape.com/controller/run_proc.php
Content-Type: application/x-www-form-urlencoded

t=get_theme_info_list&zizum_num={지점_ID}
```

### 4-2. 시간 슬롯 API

```
POST https://keyescape.com/controller/run_proc.php
Content-Type: application/x-www-form-urlencoded

t=get_theme_time&date={YYYY-MM-DD}&zizumNum={지점_ID}&themeNum={테마_ID}&endDay=0
```

두 API가 다른 파라미터 명명 규칙을 쓴다는 점이 눈에 띄었다:
- 테마 목록: `zizum_num` (snake_case)
- 시간 슬롯: `zizumNum`, `themeNum` (camelCase)

이 차이가 바로 다음 섹션에서 설명하는 버그의 원인이 되었다.

---

## 5. 파라미터 이름 오류와 해결 과정

### 처음 시도 — 실패

시간 슬롯 API를 처음 테스트할 때 `get_theme_info_list`와 같은 명명 규칙으로 snake_case를 사용했다:

```
t=get_theme_time&date=2026-03-02&zizum_num=3&theme_num=7&endDay=0
```

**결과:**

```json
{"status": false, "msg": "잘못된 접근"}
```

### 원인 파악

`run_proc.php`의 소스 코드에 직접 접근할 수 없으므로, 브라우저 Network 탭에서 실제 요청을 다시 캡처했다.
페이로드를 정확히 보니:

```
t=get_theme_time&date=2026-03-02&zizumNum=3&themeNum=7&endDay=0
```

`zizumNum`, `themeNum`이 **camelCase**였다. PHP 내부에서 `$_POST['zizumNum']`으로 받고 있기 때문에 snake_case로 보내면 해당 변수가 null이 되어 "잘못된 접근" 오류가 발생한 것이다.

### 해결

```python
# 수정 전 (실패)
data = f"t=get_theme_time&date={date}&zizum_num={zizum}&theme_num={theme}&endDay=0"

# 수정 후 (성공)
data = f"t=get_theme_time&date={date}&zizumNum={zizum}&themeNum={theme}&endDay=0"
```

**교훈**: PHP AJAX API를 역공학할 때는 파라미터 이름의 snake_case vs camelCase 구분을 반드시 Network 탭에서 원본 페이로드를 확인해야 한다.

---

## 6. 테마 목록 API 상세

### 요청

```
POST https://keyescape.com/controller/run_proc.php
Content-Type: application/x-www-form-urlencoded
X-Requested-With: XMLHttpRequest
Referer: https://keyescape.com/reservation1.php

t=get_theme_info_list&zizum_num=3
```

필수 헤더:
- `Content-Type: application/x-www-form-urlencoded; charset=UTF-8`
- `X-Requested-With: XMLHttpRequest` — PHP 서버가 AJAX 요청 여부 체크에 사용
- `Referer: https://keyescape.com/reservation1.php` — 일부 PHP 서버는 Referer를 검사함

### 응답 구조

```json
{
  "status": true,
  "msg": "",
  "data": [
    {
      "info_num": 7,
      "theme_num": 7,
      "zizum_num": 3,
      "info_name": "그카지말라캤자나",
      "num": 7,
      "doing": 14,
      "memo": "김모씨(전직 프로악플러) \r\n\r\n한때, 제 아이디만 봐도 모르는 사람이 없을 정도로...\r\n\r\n1) 난이도: 4\r\n2) 장르: 코믹\r\n3) 시간: 60분\r\n4) 금액\r\n-1인 50,000원\r\n-2인 이상 25,000원(인당)"
    },
    {
      "info_num": 6,
      "theme_num": 6,
      "zizum_num": 3,
      "info_name": "살랑살랑연구소",
      "num": 6,
      "doing": 12,
      "memo": "사랑만 하기에도 부족한 세상...\r\n\r\n1) 난이도: 3\r\n2) 장르: 로맨스\r\n3) 시간: 60분"
    }
  ]
}
```

### 주요 필드 설명

| 필드 | 타입 | 설명 |
|------|------|------|
| `theme_num` | int | 테마 고유 ID (슬롯 조회 시 사용) |
| `zizum_num` | int | 지점 ID |
| `info_name` | str | 테마명 |
| `doing` | int | 용도 불명 (플레이 횟수 또는 내부 플래그로 추정, 현재 미사용) |
| `memo` | str | 테마 설명 텍스트 (난이도·장르·시간·금액 포함) |

### doing 필드 미스터리

`doing` 값이 14, 12, 0 등 다양하게 나오는데, API 응답만으로는 정확한 의미를 파악하기 어려웠다.
추측: 해당 테마가 지금까지 예약된 횟수이거나 내부 관리용 플래그.
**현재는 사용하지 않는다.**

---

## 7. 스케줄(시간 슬롯) API 상세

### 요청

```
POST https://keyescape.com/controller/run_proc.php
Content-Type: application/x-www-form-urlencoded
X-Requested-With: XMLHttpRequest
Referer: https://keyescape.com/reservation1.php

t=get_theme_time&date=2026-03-02&zizumNum=3&themeNum=7&endDay=0
```

파라미터 설명:
- `t=get_theme_time`: 슬롯 조회 액션
- `date`: 조회 날짜 (YYYY-MM-DD)
- `zizumNum`: 지점 ID
- `themeNum`: 테마 ID
- `endDay=0`: 종료일 오프셋 (0 = 당일만 조회)

### 응답 구조

```json
{
  "status": true,
  "msg": "",
  "data": [
    {
      "num": 34,
      "gubun": "A",
      "theme_num": 7,
      "hh": "13",
      "mm": "20",
      "sale_ck": "N",
      "sale_price": 0,
      "sale_doc": "조조",
      "enable": "N",
      "sale_one": "N",
      "sale_txt": ""
    },
    {
      "num": 35,
      "gubun": "A",
      "theme_num": 7,
      "hh": "14",
      "mm": "30",
      "sale_ck": "N",
      "sale_price": 0,
      "sale_doc": "조조",
      "enable": "Y",
      "sale_one": "N",
      "sale_txt": ""
    }
  ]
}
```

### 주요 필드 설명

| 필드 | 타입 | 설명 |
|------|------|------|
| `hh` | str | 시작 시간 (시) — 문자열 주의 |
| `mm` | str | 시작 시간 (분) — 문자열 주의 |
| `enable` | str | **"Y" = 예약 가능, "N" = 마감** |
| `gubun` | str | 슬롯 구분 (A/B 등, 정확한 의미 미파악) |
| `sale_ck` | str | 할인 여부 |
| `sale_doc` | str | 할인 종류 텍스트 (예: "조조") |
| `sale_one` | str | 1인 특가 여부 |

### enable 판별 로직

```python
enable = slot.get("enable", "N")

if enable == "Y":
    status = "available"
    booking_url = f"https://keyescape.com/reservation1.php?zizum_num={zizum_num}"
else:
    status = "full"
    booking_url = None
```

주의: `hh`와 `mm`은 문자열로 오기 때문에 `int()` 변환이 필요하다.

```python
hh = int(slot["hh"])  # "13" → 13
mm = int(slot["mm"])  # "20" → 20
```

---

## 8. 지점 매핑 발견 과정

### 문제

DB에는 11개의 키이스케이프 지점이 카카오 place_id와 함께 저장되어 있다.
하지만 API를 호출하려면 keyescape.com 내부의 `zizum_num`이 필요하다.
카카오 place_id와 zizum_num을 연결하는 공식 문서는 없다.

### 방법 1 — 예약 페이지 HTML에서 발견

`reservation1.php`를 크롤링해서 `<select name="s_zizum">` 드롭다운의 옵션 목록을 확인했다:

```html
<select name="s_zizum" id="s_zizum">
  <option value="3">강남점</option>
  <option value="14">강남더오름점</option>
  <option value="16">우주라이크</option>
  <option value="18">메모리컴퍼니</option>
  <option value="19">LOG_IN1</option>
  <option value="20">LOG_IN2</option>
  <option value="22">STATION</option>
  <option value="23">후즈데어</option>
  <option value="10">홍대점</option>
  <option value="9">부산점</option>
  <option value="7">전주점</option>
</select>
```

### 방법 2 — 지점명을 카카오 DB와 대조

HTML에서 얻은 지점명 (강남점, 홍대점 등)과 카카오 DB의 `name`, `branch_name` 컬럼을 비교해서 매핑했다:

| zizum_num | keyescape 사이트 표시명 | DB cafe.id | DB name/branch_name |
|-----------|----------------------|------------|---------------------|
| 3 | 강남점 | 1405262610 | 키이스케이프 / 강남점 |
| 14 | 강남더오름 | 400448256 | 키이스케이프 강남 더오름 |
| 16 | 우주라이크 | 916422770 | 키이스케이프 / 우주라이크점 |
| 18 | 메모리컴퍼니 | 459642234 | 키이스케이프 메모리컴퍼니 |
| 19 | LOG_IN1 | 99889048 | 키이스케이프 로그인1 |
| 20 | LOG_IN2 | 320987184 | 키이스케이프 로그인2 |
| 22 | STATION | 298789057 | 키이스케이프 스테이션 |
| 23 | 후즈데어 | 1872221698 | 후즈데어 |
| 10 | 홍대점 | 200411443 | 키이스케이프 / 홍대점 |
| 9 | 부산점 | 1637143499 | 키이스케이프 / 부산점 |
| 7 | 전주점 | 48992610 | 키이스케이프 / 전주점 |

이 매핑 테이블은 `BRANCH_MAP` 딕셔너리로 스크립트에 하드코딩되어 있다.

---

## 9. memo 필드에서 정보 추출

### 문제

테마 목록 API가 반환하는 데이터에는 난이도와 소요 시간이 **별도 필드가 아니라 `memo` 자유 텍스트 안에** 들어있다.

예시:
```
김모씨(전직 프로악플러)

한때, 제 아이디만 봐도 모르는 사람이 없을 정도로...

1) 난이도: 4
2) 장르: 코믹
3) 시간: 60분
4) 금액
-1인 50,000원
```

### 정규표현식으로 추출

```python
import re

def parse_duration(memo: str) -> int | None:
    """'시간: 60분' → 60"""
    m = re.search(r"시간\s*:\s*(\d+)\s*분", memo)
    return int(m.group(1)) if m else None

def parse_difficulty(memo: str) -> int | None:
    """'난이도: 4' → 4 (1~5 범위로 클램프)"""
    m = re.search(r"난이도\s*:\s*(\d+)", memo)
    if m:
        return max(1, min(5, int(m.group(1))))
    return None
```

### 결과 및 예외

키이스케이프 지점마다 memo 작성 형식이 조금씩 달랐다.

- **강남점, 더오름 등 메인 지점**: 정형화된 번호 매기기 형식 → 정규표현식 잘 적용됨
- **부산점, 홍대점, 전주점 등 일부 지점**: 자유 형식이거나 시간 정보가 없음 → `None` 처리

```
삐릿-뽀 (홍대점) — None분 난이도:None
홀리데이 (홍대점) — None분 난이도:None
```

이런 경우 duration_min과 difficulty가 `None`으로 저장된다. 추후 수동 보완이 필요하다.

---

## 10. 포스터 이미지 수집 실패와 이유

### 시도 1 — API 응답에서 직접 추출 시도

`get_theme_info_list` 응답 필드 목록:
```
info_num, theme_num, zizum_num, info_name, num, doing, memo
```
→ **이미지 URL 필드가 전혀 없다.**

### 시도 2 — 예약 페이지 HTML에서 img 태그 찾기

`reservation1.php`를 크롤링해서 `<img>` 태그를 전부 출력해봤다:

```
/img/btnMenu.png
/img/icon.png
/img/resrv_tit.png
/img/noImage.png
...
```

모두 UI 아이콘이나 인터페이스 이미지였다. 테마 포스터 이미지가 없었다.

### 원인 파악

예약 페이지(`reservation1.php`)의 테마 이미지는 JavaScript가 동적으로 DOM에 삽입하는 방식으로 렌더링된다. Python의 `requests`로는 JavaScript 실행이 불가하므로 이 이미지에 접근할 수 없다.

`get_theme_view` 같은 추가 API를 탐색해봤지만:
```json
{"status": false, "msg": ""}
```
정보 없음.

### 결론

키이스케이프 테마 포스터는 현재 수집하지 않는다. `poster_url = None`으로 저장.
검색 결과 UI에서는 포스터 미존재 시 기본 이모지(🔐)로 대체 표시된다.

**Playwright 등 브라우저 자동화 도구를 쓰면 수집 가능**하지만, 속도 및 서버 부하 측면에서 현재는 우선순위를 두지 않는다.

---

## 11. booking_url 결정 방식

xdungeon.net과 다르게 키이스케이프는 "특정 시간 슬롯"으로 직접 이동하는 URL 구조가 없다.
슬롯 API 응답에 booking_url 같은 필드도 없다.

따라서 **예약 가능 슬롯이 있을 때 지점 예약 메인 페이지 URL**을 booking_url로 사용한다:

```python
booking_url = f"https://keyescape.com/reservation1.php?zizum_num={zizum_num}"
```

이 URL로 이동하면 사용자가 날짜를 직접 선택해서 예약을 진행할 수 있다.
마감 슬롯에는 `booking_url = None`을 저장한다.

---

## 12. DB 연동 및 동기화 전략

### 테마 upsert

- `cafe_id` + `name` 조합으로 기존 테마를 조회
- 없으면 INSERT, 있으면 UPDATE (duration_min, difficulty, description 갱신)

```python
result = await session.execute(
    select(Theme).where(
        Theme.cafe_id == cafe_id,
        Theme.name == name,
    )
)
existing = result.scalar_one_or_none()

if existing:
    existing.duration_min = duration
    existing.difficulty = difficulty
    ...
else:
    session.add(Theme(cafe_id=cafe_id, name=name, ...))
    await session.flush()  # DB에서 새 id 생성
```

### 스케줄 upsert 전략

매 크롤링마다 전체를 지우고 다시 쓰는 방식(full-replace)은 히스토리를 잃는다.
대신 **상태가 변경된 슬롯만 새 행을 추가**하는 방식을 선택:

```python
# 같은 날짜+시간의 최근 레코드 조회
result = await session.execute(
    select(Schedule).where(
        Schedule.theme_id == db_theme_id,
        Schedule.date == d,
        Schedule.time_slot == time_obj,
    ).order_by(Schedule.crawled_at.desc()).limit(1)
)
existing = result.scalar_one_or_none()

if existing:
    if existing.status != status:
        # 상태 변화 → 새 행 추가 (변경 시각 추적 가능)
        session.add(Schedule(..., crawled_at=datetime.now()))
else:
    # 처음 보는 슬롯 → 추가
    session.add(Schedule(...))
```

이렇게 하면 "언제 빈자리가 났는지" 나중에 분석할 수 있다.

---

## 13. 실행 결과

```
============================================================
keyescape.com → DB 동기화
============================================================

[ 1단계 ] 테마 동기화
  [NEW] 그카지말라캤자나 (키이스케이프) — 60분 난이도:4
  [NEW] 살랑살랑연구소 (키이스케이프) — 60분 난이도:3
  [NEW] 월야애담-영문병행표기 (키이스케이프) — 60분 난이도:4
  [NEW] 엔제리오 (키이스케이프 강남 더오름) — 70분 난이도:4
  [NEW] 네드 (키이스케이프 강남 더오름) — 75분 난이도:4
  [NEW] WANNA GO HOME (키이스케이프) — 70분 난이도:3
  [NEW] US (키이스케이프) — 65분 난이도:3
  [NEW] FILM BY EDDY (키이스케이프 메모리컴퍼니) — 75분 난이도:3
  [NEW] FILM BY STEVE (키이스케이프 메모리컴퍼니) — 80분 난이도:3
  [NEW] FILM BY BOB (키이스케이프 메모리컴퍼니) — 75분 난이도:3
  [NEW] FOR FREE (키이스케이프 로그인1) — 65분 난이도:4
  [NEW] 머니머니패키지 (키이스케이프 로그인1) — 65분 난이도:4
  ... (총 32개)

  테마 동기화 완료: 32개 추가 / 0개 갱신

[ 2단계 ] 스케줄 동기화 (오늘~6일 후)
  zizum=3 theme=7 7일치 완료
  zizum=3 theme=6 7일치 완료
  ... (총 11지점 × 2~5테마)

  스케줄 동기화 완료: 2202개 레코드 추가
```

---

## 14. 한계 및 주의사항

### 포스터 이미지 없음
테마 이미지는 JavaScript 렌더링으로만 접근 가능. 현재 `poster_url = None`.

### memo 형식 비표준화
일부 지점의 memo에는 시간·난이도 정보가 없음 → `duration_min`, `difficulty` = None.
특히 홍대점(zizum=10), 부산점(zizum=9), 전주점(zizum=7)이 해당.

### 예약 기간 제한
서비스에서 오픈하는 예약 기간이 지점마다 다를 수 있음.
`endDay=0`으로 요청 시 당일 슬롯만 반환하는 경우, 미래 날짜는 빈 배열 반환.

### 정적 매핑 테이블 유지보수
`BRANCH_MAP` 딕셔너리는 하드코딩. 신규 지점이 생기거나 기존 지점이 폐점하면 수동으로 업데이트해야 한다.

### 요청 빈도 제한
요청 사이에 0.5초 딜레이 적용.
11개 지점 × 평균 3개 테마 × 7일치 = 약 231회 슬롯 API 호출.
전체 동기화 소요 시간: 약 3~5분.
