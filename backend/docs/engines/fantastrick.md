# 판타스트릭 크롤링 분석 문서

> **대상 사이트**: http://fantastrick.co.kr
> **운영사**: 판타스트릭 (3개 지점: 강남1호점 / 2호점 / TGC 3호점)
> **플랫폼**: WordPress + Booked 예약 플러그인
> **관련 스크립트**: `scripts/sync_fantastrick_db.py`
> **분석 완료일**: 2026-03-02

---

## 목차

1. [배경 — 예약 시스템 파악](#1-배경)
2. [WordPress Booked 플러그인 발견 과정](#2-wordpress-booked-플러그인-발견-과정)
3. [AJAX API 역공학](#3-ajax-api-역공학)
4. [calendar_id 발견 과정](#4-calendar_id-발견-과정)
5. [HTML 응답 파싱](#5-html-응답-파싱)
6. [지점별 테마 분리 문제와 해결](#6-지점별-테마-분리-문제와-해결)
7. [판타스트릭TGC (3호점) place_id 조회 문제](#7-판타스트릭tgc-3호점-place_id-조회-문제)
8. [rooms 페이지에서 poster 이미지 추출](#8-rooms-페이지에서-poster-이미지-추출)
9. [DB 연동 구조](#9-db-연동-구조)
10. [실행 결과](#10-실행-결과)
11. [한계 및 주의사항](#11-한계-및-주의사항)

---

## 1. 배경

판타스트릭은 강남 지역에 총 3개 지점을 운영하는 방탈출 카페다.

| 지점 | 주소 | 카카오 place_id |
|------|------|----------------|
| 1호점 | 서울 서초구 강남대로79길 39 지하1층 | `1421844037` |
| 2호점 | 서울 서초구 사평대로 353 서일빌딩 지하1층 4호 | `192767471` |
| TGC 3호점 | 서울 서초구 강남대로83길 34 지하1층 | `2020129484` |

카카오 DB에 3개 지점이 별도로 등록되어 있지만, **공식 홈페이지는 하나(`fantastrick.co.kr`)를 공유**한다.
xdungeon처럼 지점별로 예약 URL이 완전히 분리되지 않고, 하나의 WordPress 사이트에서 테마별로 `calendar_id`만 다르다.

---

## 2. WordPress Booked 플러그인 발견 과정

### 2-1. 첫 관찰

판타스트릭 예약 페이지(`http://fantastrick.co.kr/booking/`)를 크롬에서 열어 Network 탭을 관찰했다.

날짜를 클릭하면 아래와 같은 POST 요청이 발생했다:

```
POST http://fantastrick.co.kr/wp-admin/admin-ajax.php
Content-Type: application/x-www-form-urlencoded

action=booked_calendar_date&date=2026-03-02&calendar_id=17
```

URL 자체가 힌트다: `wp-admin/admin-ajax.php`는 **WordPress의 AJAX 처리 endpoint**다.
파라미터의 `action=booked_calendar_date`는 WordPress 플러그인이 등록한 AJAX 액션 이름이다.

### 2-2. Booked 플러그인 확인

`booked_calendar_date`를 검색하면 **[Booked](https://codecanyon.net/item/booked-appointments/9466968)** — CodeCanyon에서 판매하는 WordPress 예약 플러그인임을 확인할 수 있다.

Booked 플러그인의 특징:
- WordPress 대시보드에서 캘린더(`calendar_id`)와 타임슬롯을 설정
- 예약 페이지에 캘린더 위젯 삽입
- 사용자가 날짜를 선택하면 AJAX로 해당 날짜의 타임슬롯 조회
- 예약 완료 여부에 따라 "예약가능" / "예약완료" 표시

### 2-3. 동일 플랫폼을 쓰는 다른 카페

Booked 플러그인을 사용하는 방탈출 카페는 판타스트릭 외에도 있을 수 있다.
`wp-admin/admin-ajax.php` 요청이 보이면 동일한 방법으로 분석 가능하다.

---

## 3. AJAX API 역공학

### Request

```
POST http://fantastrick.co.kr/wp-admin/admin-ajax.php
```

| 파라미터 | 값 | 설명 |
|---------|-----|------|
| `action` | `booked_calendar_date` | Booked 플러그인 AJAX 액션 이름 |
| `date` | `2026-03-02` | 조회할 날짜 (YYYY-MM-DD) |
| `calendar_id` | `17` | 테마별 캘린더 ID |

**인증 불필요**: WordPress 공개 AJAX 엔드포인트로, 별도 인증 없이 호출 가능하다.
(도어이스케이프의 JWT 인증과 달리 훨씬 단순하다.)

### Python 구현

```python
import urllib.request, urllib.parse

def _fetch_slots(calendar_id: int, target_date: date) -> list[dict]:
    body = urllib.parse.urlencode({
        "action": "booked_calendar_date",
        "date": target_date.strftime("%Y-%m-%d"),
        "calendar_id": str(calendar_id),
    }).encode()

    req = urllib.request.Request(
        "http://fantastrick.co.kr/wp-admin/admin-ajax.php",
        data=body,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "http://fantastrick.co.kr/booking/",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        html = r.read().decode("utf-8", errors="ignore")
    # 이후 BeautifulSoup으로 파싱
```

### Response

JSON이 아닌 **HTML 조각(fragment)** 이 반환된다.
Booked 플러그인이 서버에서 HTML을 렌더링해서 응답하는 방식이다.

```html
<div class="booked-cal-ajax-wrap">
  <ul class="timeslots">
    <li class="timeslot available">
      <button data-timeslot="1400-1540">
        14:00 - 15:40
      </button>
      <span class="spots-available">예약가능</span>
    </li>
    <li class="timeslot">
      <button data-timeslot="1600-1740">
        16:00 - 17:40
      </button>
      <span class="spots-available">예약완료</span>
    </li>
  </ul>
</div>
```

---

## 4. calendar_id 발견 과정

`calendar_id`는 테마마다 다르다. 이 값을 알아야 해당 테마의 슬롯을 조회할 수 있다.

### 방법 1 — Network 탭에서 직접 확인

예약 페이지에서 각 테마 탭을 눌러보면 `calendar_id` 파라미터값이 다르게 보인다.

### 방법 2 — rooms 페이지 HTML 파싱

판타스트릭 공식 사이트의 테마 소개 페이지(`/rooms/{slug}/`)에는 Booked 캘린더 위젯이 삽입되어 있다:

```html
<table class="booked-calendar" data-calendar-id="17">
  ...
</table>
```

`data-calendar-id` 속성에서 calendar_id를 추출할 수 있다:

```python
from bs4 import BeautifulSoup
import urllib.request

def _fetch_room_info(slug: str) -> dict:
    url = f"http://fantastrick.co.kr/rooms/{slug}/"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        html = r.read().decode("utf-8", errors="ignore")

    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="booked-calendar")
    cal_id = int(table["data-calendar-id"]) if table else None
    return {"calendar_id": cal_id, ...}
```

### 최종 확인된 calendar_id

| 테마 | slug | calendar_id |
|------|------|-------------|
| 태초의 신부 | `firstfoundbride` | **17** |
| 사자의 서 | `bookofduat` | **23** |
| LOCKDOWN CITY | `ldc` | **24** |

---

## 5. HTML 응답 파싱

AJAX 응답 HTML을 BeautifulSoup으로 파싱해 슬롯 정보를 추출한다.

### 구조 파악

```html
<div class="timeslot">          ← 슬롯 하나
  <button data-timeslot="HHMM-HHMM">   ← 시작/종료 시간 (예: "1400-1540")
    14:00 - 15:40
  </button>
  <span class="spots-available">       ← 예약 가능 여부
    예약가능  (or 예약완료)
  </span>
</div>
```

### 파싱 코드

```python
soup = BeautifulSoup(html, "html.parser")
slots = []

for slot_div in soup.find_all("div", class_="timeslot"):
    btn = slot_div.find("button")
    if not btn:
        continue

    timeslot = btn.get("data-timeslot", "")  # "1400-1540"
    if not timeslot or "-" not in timeslot:
        continue

    start_str = timeslot.split("-")[0]  # "1400"
    if len(start_str) != 4:
        continue

    hh = int(start_str[:2])  # 14
    mm = int(start_str[2:])  # 00

    avail_span = slot_div.find("span", class_="spots-available")
    if avail_span:
        status = "available" if "예약가능" in avail_span.text else "full"
    else:
        status = "full"  # span 없으면 마감으로 처리

    slots.append({"time": dtime(hh, mm), "status": status})
```

### data-timeslot 형식 주의

`data-timeslot`의 값은 `"HHMM-HHMM"` 형식이다.

- 오전 10시 → `"1000-1140"`
- 오후 2시 → `"1400-1540"`

`"HH:MM"` 콜론 형식이 아니므로 파싱 시 주의.

---

## 6. 지점별 테마 분리 문제와 해결

### 문제

판타스트릭은 3개 지점이 각각 별도 테마를 운영한다:

- 1호점: 태초의 신부
- 2호점: 사자의 서
- TGC 3호점: LOCKDOWN CITY

그런데 공식 홈페이지는 **하나의 WordPress 사이트**에서 3개 테마를 모두 관리한다.
처음 스크립트를 작성할 때는 3개 테마를 모두 1호점(`cafe_id=1421844037`)에 연결하는 실수를 했다.

### 해결

THEMES 딕셔너리에 `cafe_id`를 테마별로 개별 지정:

```python
THEMES = [
    {
        "cafe_id": "1421844037",   # 강남 1호점
        "name": "태초의 신부",
        "calendar_id": 17,
        "slug": "firstfoundbride",
        "poster_url": "http://fantastrick.co.kr/wp-content/uploads/2018/10/poster-scaled.jpg",
    },
    {
        "cafe_id": "192767471",    # 2호점 (사평대로 353)
        "name": "사자의 서",
        "calendar_id": 23,
        "slug": "bookofduat",
        "poster_url": None,
    },
    {
        "cafe_id": "2020129484",   # TGC 3호점 (강남대로83길 34)
        "name": "LOCKDOWN CITY",
        "calendar_id": 24,
        "slug": "ldc",
        "poster_url": None,
    },
]
```

### DB 수정 이력

사자의 서가 처음에 1호점에 연결되었다가 이후 2호점으로 수정:

```sql
UPDATE theme SET cafe_id = '192767471' WHERE id = 106;
```

---

## 7. 판타스트릭TGC (3호점) place_id 조회 문제

### 문제

판타스트릭TGC를 DB에 추가하기 위해 카카오 place_id가 필요했다.
카카오 로컬 REST API로 "판타스트릭TGC"를 검색했으나 **결과가 0개**였다.

```python
# 아래 검색 모두 결과 0개
requests.get("https://dapi.kakao.com/v2/local/search/keyword.json",
             params={"query": "판타스트릭TGC"}, ...)

requests.get("https://dapi.kakao.com/v2/local/search/keyword.json",
             params={"query": "판타스트릭", "x": ..., "y": ..., "radius": 10000}, ...)
# → 2개만 반환 (1호점, 2호점)
```

### 원인

카카오맵 앱에서 "판타스트릭"을 검색하면 TGC가 포함된 3개가 정상적으로 나온다.
다만 판타스트릭TGC는 카카오맵에서 **"게임방, PC방"으로 잘못 분류**되어 있다.

카카오 로컬 REST API의 키워드 검색은 특정 카테고리(게임방, PC방 등)를 결과에서 제외하는 것으로 추정된다.
이로 인해 API 검색에서는 나오지 않고 앱에서만 보이는 현상이 발생한다.

### 해결

사용자가 카카오맵 앱에서 직접 검색해 place URL을 공유:
`https://place.map.kakao.com/2020129484`

place_id: **`2020129484`**

이를 DB에 직접 수동 등록했다:

```python
cafe = Cafe(
    id="2020129484",
    name="판타스트릭TGC",
    address="서울 서초구 강남대로83길 34",
    website_url="http://fantastrick.co.kr",
    engine="fantastrick",
    lat=37.505858554363,
    lng=127.021767947017,
    is_active=True,
)
```

좌표는 카카오 주소 검색 API(`/v2/local/search/address.json?query=강남대로83길 34`)로 획득.

---

## 8. rooms 페이지에서 poster 이미지 추출

테마 포스터 이미지 URL은 각 테마의 rooms 페이지에서 추출한다:

```
GET http://fantastrick.co.kr/rooms/{slug}/
```

```python
for img in soup.find_all("img"):
    src = img.get("src", "")
    if "fantastrick.co.kr/wp-content/uploads" in src and "poster" in src.lower():
        poster = src
        break
```

### 결과

- 태초의 신부: `http://fantastrick.co.kr/wp-content/uploads/2018/10/poster-scaled.jpg`
- 사자의 서: 포스터 이미지 없음 → `None`
- LOCKDOWN CITY: 포스터 이미지 존재 (3호점 포스터)

---

## 9. DB 연동 구조

### 테마 동기화 흐름

```
for theme in THEMES:
    1. rooms/{slug}/ 에서 calendar_id, poster_url 추출 (rooms 페이지 보강)
    2. DB에서 (cafe_id, name) 기준으로 기존 테마 조회
    3. 없으면 INSERT, 있으면 poster_url / is_active 업데이트
    4. cal_to_db[calendar_id] = db_theme.id 매핑 저장
```

### 스케줄 동기화 흐름

```
for (calendar_id, db_theme_id) in cal_to_db:
    for date in [오늘, 내일, ..., +6일]:
        1. _fetch_slots(calendar_id, date) 호출
        2. 각 슬롯에 대해:
           - 현재 시각 이전 슬롯 스킵
           - DB에서 (theme_id, date, time_slot) 기준 최신 레코드 조회
           - 없거나 상태(status)가 바뀐 경우 새 레코드 INSERT
```

### upsert 전략

다른 크롤러와 동일하게 **변경 이력을 보존하는 방식** 사용:
- `available` → `full`처럼 상태가 바뀌면 기존 레코드를 UPDATE하지 않고 새 레코드를 INSERT
- `crawled_at`으로 가장 최신 레코드를 조회해 현재 상태 파악

```python
# 가장 최신 레코드 조회
result = await session.execute(
    select(Schedule).where(
        Schedule.theme_id == db_theme_id,
        Schedule.date == target_date,
        Schedule.time_slot == time_obj,
    ).order_by(Schedule.crawled_at.desc()).limit(1)
)
existing = result.scalar_one_or_none()

if existing:
    if existing.status != status:
        # 상태 변경 시에만 새 레코드 추가
        session.add(Schedule(..., status=status, crawled_at=now))
else:
    # 새 슬롯 → 추가
    session.add(Schedule(..., status=status, crawled_at=now))
```

---

## 10. 실행 결과

```
============================================================
판타스트릭 강남1호점 → DB 동기화
============================================================

[ 1단계 ] 테마 동기화
  [UPD] 태초의 신부 (판타스트릭) calendar_id=17
  [UPD] 사자의 서 (판타스트릭) calendar_id=23
  [UPD] LOCKDOWN CITY (판타스트릭TGC) calendar_id=24

  테마 동기화 완료: 0개 추가 / 3개 갱신
  calendar_id 매핑: {17: 105, 23: 106, 24: 107}

[ 2단계 ] 스케줄 동기화 (오늘~6일 후)
  calendar_id=17 완료
  calendar_id=23 완료
  calendar_id=24 완료

  스케줄 동기화 완료: 125개 레코드 추가

============================================================
동기화 완료!
============================================================
```

---

## 11. 한계 및 주의사항

### HTTP (비HTTPS)

판타스트릭 공식 사이트(`http://fantastrick.co.kr`)는 HTTPS를 사용하지 않는다.
MITM 공격 위험이 있지만, 이 스크립트는 읽기 전용 크롤링이므로 현재는 허용.

### 날짜별 개별 호출

xdungeon, keyescape와 마찬가지로 날짜마다 별도 API를 호출해야 한다.
7일치 × 3개 테마 = 21번 호출. `REQUEST_DELAY = 0.8`초 간격 적용.

### calendar_id 변경 가능성

WordPress 관리자가 캘린더를 삭제하고 다시 생성하면 calendar_id가 바뀔 수 있다.
정기적으로 rooms 페이지(`/rooms/{slug}/`)의 `data-calendar-id`를 재확인하는 것이 안전하다.
현재 스크립트는 매 실행 시 rooms 페이지에서 calendar_id를 다시 읽어오므로, 자동 감지가 가능하다.

### poster_url 없는 테마

사자의 서의 rooms 페이지에 "poster"가 포함된 이미지가 없어서 `poster_url = None`.
수동으로 이미지를 찾아 업데이트하거나, 네이버 플레이스 사진을 활용할 수 있다.

### 판타스트릭TGC 카카오 카테고리 오류

카카오맵에서 판타스트릭TGC가 "게임방, PC방"으로 잘못 분류되어 있다.
카카오 로컬 REST API 키워드 검색에서 해당 장소가 제외되므로, 자동 조회가 불가하다.
카카오맵에 카테고리 수정을 요청하거나, place_id를 수동으로 관리해야 한다.
