# xdungeon.net 크롤링 분석 문서

> **대상 사이트**: https://xdungeon.net
> **운영사**: (주)비트포비아
> **관련 스크립트**: `scripts/crawl_xdungeon_test.py`

---

## 목차

1. [배경 — 왜 이 사이트를 분석했는가](#1-배경)
2. [사이트 구조 파악 과정](#2-사이트-구조-파악-과정)
3. [지점 ID 매핑 발견](#3-지점-id-매핑-발견)
4. [테마 추출 방법](#4-테마-추출-방법)
5. [테마 상세정보 추출 방법](#5-테마-상세정보-추출-방법)
6. [예약 가능 시간대 추출 방법](#6-예약-가능-시간대-추출-방법)
7. [파싱 중 발생한 버그와 해결](#7-파싱-중-발생한-버그와-해결)
8. [크롤링 테스트 스크립트 구조](#8-크롤링-테스트-스크립트-구조)
9. [실제 실행 결과](#9-실제-실행-결과)
10. [한계 및 주의사항](#10-한계-및-주의사항)

---

## 1. 배경

비트포비아는 전국에 여러 방탈출 지점을 운영하는 대형 체인이다.
카카오맵 전국 크롤링 당시 "비트포비아 던전루나", "비트포비아 던전스텔라" 2개만 DB에 등록되었는데, 알고 보니 **총 9개 지점이 xdungeon.net이라는 자체 예약 시스템을 사용**하고 있었다.

더불어 기존 크롤링 필터(`is_escape_room()`)가 이름에 "방탈출/이스케이프/escape/탈출" 키워드가 없으면 거르는 방식이었기 때문에, "비트포비아 강남던전점" 같은 이름들은 전부 누락되었다.

---

## 2. 사이트 구조 파악 과정

### 2-1. 홈페이지 진입

xdungeon.net을 열면 가장 먼저 보이는 것이 이 URL 구조다:

```
https://xdungeon.net/layou/home.php?go=rev.main
```t/res

`go=` 파라미터로 페이지를 전환하는 **PHP 기반 자체 개발 예약 시스템**이다.
React/Next.js 같은 SPA가 아니라, 서버에서 HTML을 통째로 만들어서 보내주는 방식이기 때문에
별도의 JavaScript 실행 없이 **requests + BeautifulSoup 만으로 데이터를 파싱**할 수 있다.

### 2-2. 페이지 종류

| go= 값 | 역할 |
|--------|------|
| `theme.list` | 테마 목록 페이지 |
| `rev.main` | 예약 페이지 (지점+날짜 선택 → 시간표 노출) |
| `rev.guide` | 예약 안내 |
| `rev.login` | 예약 확인 및 취소 |

### 2-3. 서버 사이드 렌더링 확인

예약 페이지 HTML을 직접 요청해보니, JavaScript 실행 없이도 모든 시간 슬롯 데이터가
이미 HTML에 담겨 있었다. 즉 **서버가 지점+날짜에 맞게 HTML을 완성해서 보내준다**.

```
GET https://xdungeon.net/layout/res/home.php?go=rev.main&s_zizum=6&rev_days=2026-03-02
```

위 요청만으로 던전루나의 2026-03-02 전체 예약 현황을 받아올 수 있다.

---

## 3. 지점 ID 매핑 발견

예약 페이지의 `<select>` 드롭다운 HTML을 보면 각 지점에 숫자 ID가 할당되어 있다:

```html
<select name="s_zizum">
  <option value="3">홍대던전</option>
  <option value="1">던전101</option>
  <option value="5">홍대던전Ⅲ</option>
  <option value="2">강남던전</option>
  <option value="4">강남던전Ⅱ</option>
  <option value="6">던전루나(강남)</option>
  <option value="9">던전스텔라(강남)</option>
  <option value="7">서면던전(부산)</option>
  <option value="10">서면던전 레드(부산)</option>
</select>
```

이 `s_zizum` 값이 모든 API 요청의 핵심 파라미터다. 숫자가 연속적이지 않고 (6 다음이 9) 중간이 빠져 있는 것은 아마 과거에 폐점한 지점의 ID가 있었을 가능성이 있다.

**완성된 지점 매핑표:**

| s_zizum | 지점명 | 카카오 place_id |
|---------|-------|----------------|
| 1 | 던전101 | 1772808576 |
| 2 | 강남던전 | 27413263 |
| 3 | 홍대던전 | 1246652450 |
| 4 | 강남던전Ⅱ | 1769092819 |
| 5 | 홍대던전Ⅲ | 2070160321 |
| 6 | 던전루나(강남) | 1478483341 |
| 7 | 서면던전(부산) | 1322241204 |
| 9 | 던전스텔라(강남) | 436025860 |
| 10 | 서면던전 레드(부산) | 629764977 |

---

## 4. 테마 추출 방법

### 4-1. 요청

```
GET https://xdungeon.net/layout/res/home.php?go=theme.list&s_zizum={지점ID}
```

지점 ID를 넘기면 해당 지점의 테마 목록 HTML이 내려온다.
아무 값도 넘기지 않으면 (`s_zizum=` 생략) **전체 지점의 모든 테마**가 나온다.

### 4-2. HTML 구조

테마 하나의 HTML 구조는 이렇다:

```html
<li>
  <a href="javascript:_fun_theme_view('49')">  <!-- 테마 ID = 49 -->
    <div class="img_box">
      <img src="/file/theme/49/49_8635451017.jpg"/>
    </div>
    <div class="txt_box">
      <p class="thm">3일</p>          <!-- 테마명 -->
      <div class="tag">
        <span class="str">던전루나(강남)</span>  <!-- 지점명 -->
        <span class="lv">NORMAL</span>          <!-- 난이도 -->
        <span class="gr">추리</span>             <!-- 장르 -->
      </div>
    </div>
  </a>
</li>
```

### 4-3. 파싱 로직

핵심은 `href="javascript:_fun_theme_view('49')"` 에서 테마 ID를 정규표현식으로 뽑는 것이다:

```python
# href 속성에서 테마 ID 추출
link = li.find("a", href=lambda h: h and "_fun_theme_view" in str(h))
m = re.search(r"_fun_theme_view\('(\d+)'\)", link["href"])
theme_id = m.group(1)  # "49"

# 나머지 정보는 CSS 클래스로 찾기
name       = li.find("p",    class_="thm").get_text(strip=True)   # "3일"
branch     = li.find("span", class_="str").get_text(strip=True)   # "던전루나(강남)"
difficulty = li.find("span", class_="lv").get_text(strip=True)    # "NORMAL"
genre      = li.find("span", class_="gr").get_text(strip=True)    # "추리"
```

### 4-4. 결과

9개 지점 전체에서 총 **32개 테마** 수집 성공:

| 지점 | 테마 수 | 대표 테마 |
|------|--------|---------|
| 던전101 | 4개 | 전래동 자살사건, LET'S PLAY TOGETHER |
| 강남던전 | 4개 | 강남목욕탕, 대호시장 살인사건 |
| 홍대던전 | 4개 | 날씨의 신, 꿈의 공장 |
| 강남던전Ⅱ | 2개 | MAYDAY, LOST KINGDOM2 |
| 홍대던전Ⅲ | 4개 | 경성 연쇄실종사건, 이미지 세탁소 |
| 던전루나(강남) | 2개 | 검은 운명의 밤, 3일 |
| 서면던전(부산) | 3개 | 날씨의 신, 꿈의 공장, 오늘 나는 |
| 던전스텔라(강남) | 3개 | 데스티니 앤드 타로, 響:향, TIENTANG CITY |
| 서면던전 레드(부산) | 6개 | 고시원 살인사건, AMEN, 부적 |

---

## 5. 테마 상세정보 추출 방법

### 5-1. 발견 과정

테마 목록에는 **플레이타임이 없다**. 그런데 각 테마 이미지를 클릭하면 팝업이 뜨면서
플레이타임, 시놉시스 등 상세정보가 나온다.

브라우저 개발자도구로 이 팝업의 동작을 보면:

```javascript
function _fun_theme_view(num) {
  $.ajax({
    type: "POST",
    url: "../../core/res/theme.act.php",
    data: "not_html=Y&act=view&num=" + num + "&ck_rev_but=N",
    success: function(data) {
      $("#popup_view").html(data);  // 받아온 HTML을 팝업에 삽입
    }
  });
}
```

`theme.act.php`에 POST 요청을 보내면 팝업 내용 HTML을 돌려준다는 것을 알 수 있다.

### 5-2. 요청

```
POST https://xdungeon.net/core/res/theme.act.php
Content-Type: application/x-www-form-urlencoded

not_html=Y&act=view&num=49&ck_rev_but=N
```

파라미터 설명:
- `not_html=Y`: HTML 래퍼 없이 팝업 내용만 반환
- `act=view`: 조회 액션
- `num=49`: 테마 ID
- `ck_rev_but=N`: 예약하기 버튼 숨김 (테마 정보만 볼 때)

### 5-3. 응답 HTML 구조

```html
<div class="thm_popup">
  <div class="conts">
    <div class="info_box">
      <div class="txt_box">
        <dl class="half">
          <dt>지점명</dt>
          <dd>던전루나(강남)</dd>
        </dl>
        <dl class="half">
          <dt>플레이타임</dt>
          <dd>75분</dd>
        </dl>
        <dl class="half">
          <dt>난이도</dt>
          <dd>NORMAL</dd>
        </dl>
        <dl class="half">
          <dt>장르</dt>
          <dd>추리</dd>
        </dl>
        <dl>
          <dt>테마명</dt>
          <dd>3일</dd>
        </dl>
        <dl class="synp">
          <dt>시놉시스</dt>
          <dd>하루 6시간만 깨어있을 수 있는 세상!...</dd>
        </dl>
        <dl class="etc">
          <dt>특이사항</dt>
          <dd>해당 테마는 구역이 나눠져 있으며...</dd>
        </dl>
      </div>
    </div>
  </div>
</div>
```

`<dl>/<dt>/<dd>` 구조로 키-값 쌍이 나열된다.

### 5-4. 파싱 로직

```python
detail = {}
for dl in soup.find_all("dl"):
    dt = dl.find("dt")
    dd = dl.find("dd")
    key = dt.get_text(strip=True)   # "플레이타임"
    val = dd.get_text(separator=" ", strip=True)  # "75분"

    # 한국어 키 → 영어 필드명으로 변환
    key_map = {
        "지점명": "branch",
        "플레이타임": "play_time",
        "난이도": "difficulty",
        "장르": "genre",
        "테마명": "theme_name",
        "시놉시스": "synopsis",
        "특이사항": "notes",
    }
    detail[key_map[key]] = val
```

### 5-5. 주의: 인원 정보 없음

안타깝게도 **최소/최대 인원 정보는 xdungeon.net에서 제공하지 않는다**.
테마 목록에도, 상세팝업에도 인원 관련 필드가 전혀 없다.
(인원 정보가 필요하다면 카카오 플레이스 페이지나 네이버 검색을 따로 활용해야 한다.)

---

## 6. 예약 가능 시간대 추출 방법

### 6-1. 요청

```
GET https://xdungeon.net/layout/res/home.php?go=rev.main&s_zizum=6&rev_days=2026-03-02
```

파라미터:
- `go=rev.main`: 예약 페이지
- `s_zizum=6`: 지점 ID (던전루나)
- `rev_days=2026-03-02`: 조회할 날짜 (YYYY-MM-DD 형식)

### 6-2. 예약 오픈 정책

**중요!** xdungeon.net은 예약을 **오늘부터 7일 후까지만** 오픈한다.
그 이상 날짜를 요청하면:

```html
<div class="rev_make_text">예약 오픈시간이 아닙니다</div>
```

이 메시지가 시간 슬롯 대신 표시된다. 크롤링 시 이 케이스를 먼저 체크해야 한다.

### 6-3. HTML 구조 — 전체 골격

```
div.thm_box                 ← 해당 지점의 전체 테마 컨테이너
  └─ div.box                ← 테마 하나
       ├─ div.img_box       ← 테마 이미지
       │    └─ p.tit        ← 테마명
       └─ div.time_box      ← 시간 슬롯 전체
            └─ ul
                 ├─ li.sale              ← 예약 가능
                 ├─ li.dead.sale         ← 매진
                 └─ li (class 없음)      ← 비운영/닫힘
```

### 6-4. 시간 슬롯 HTML — 3가지 상태

**상태 1: 예약 가능 (li.sale)**

```html
<li class="sale">
  <a href="home.php?go=rev.make&crypt_data=bXJ5aGlz...">
    <span>SALE</span>09:30
  </a>
</li>
```

- `class="sale"` 만 있고 `dead` 없음
- `<a>` 태그에 `href`가 있어서 클릭하면 예약으로 이동
- `<span>SALE</span>` 배지가 시각적으로 표시됨
- `href`에 `crypt_data`라는 암호화된 예약 파라미터가 들어있음

**상태 2: 매진 (li.dead.sale)**

```html
<li class="dead sale">
  <a>14:30</a>
</li>
```

- `class="dead sale"` — `dead`와 `sale` 둘 다 있음
- `<a>` 태그에 `href` 없음 (클릭 불가)
- `<span>SALE</span>` 배지 없음

**상태 3: 비운영 (li, class 없음)**

드물게 등장. 해당 시간대를 운영하지 않는 경우.

### 6-5. crypt_data 분석

예약 가능 슬롯의 href에는 이런 URL이 들어있다:

```
home.php?go=rev.make&crypt_data=bXJ5aGlzMmVjY2xUbVZ5YmdLYUhQ...
```

HTML 주석 안에 원래 파라미터가 적혀 있어서 이를 통해 암호화 전 내용을 알 수 있다:

```html
<!--
  home.php?go=rev.make&theme_num=8&rev_days=2026-03-03&time_index=0
-->
```

즉 `crypt_data`는 `theme_num + rev_days + time_index`를 암호화한 값이다.
(우리 크롤러는 예약까지 자동화하지 않으니 이 값은 참고만 한다.)

### 6-6. 파싱 로직

```python
for li in time_box.find_all("li"):
    classes = li.get("class", [])
    is_sale = "sale" in classes
    is_dead = "dead" in classes

    # <a> 태그 안에서 시간 텍스트 추출
    a_tag = li.find("a")

    # <span>SALE</span> 제거 후 순수 시간 텍스트만 남김
    for span in a_tag.find_all("span"):
        span.decompose()

    t = a_tag.get_text(strip=True)  # "09:30"

    # 상태 판별
    if is_sale and not is_dead:
        status = "available"      # 예약 가능
    elif is_sale and is_dead:
        status = "sold_out"       # 매진
    else:
        status = "closed"         # 비운영

    # 예약 링크 저장 (available일 때만 href가 있음)
    booking_href = a_tag.get("href", "")
```

---

## 7. 파싱 중 발생한 버그와 해결

### 버그: 시간 텍스트에 "SALE"이 붙어서 출력됨

**증상**: `09:30`이 아니라 `SALE09:30`으로 출력됨

**원인**: `li.get_text(strip=True)`를 쓰면 `<span>SALE</span>` 안의 텍스트까지 전부
합쳐져서 반환된다. BeautifulSoup의 `get_text()`는 모든 자식 태그의 텍스트를 이어붙인다.

**원인이 된 HTML**:
```html
<li class="sale">
  <a href="...">
    <span>SALE</span>09:30   ← span 텍스트 "SALE" + 일반 텍스트 "09:30"
  </a>
</li>
```

**해결**: `<a>` 태그 안의 `<span>`을 먼저 제거(`decompose()`)한 뒤 텍스트를 추출

```python
# 수정 전 (버그)
t = li.get_text(strip=True)   # → "SALE09:30"

# 수정 후 (정상)
a_tag = li.find("a")
for span in a_tag.find_all("span"):
    span.decompose()           # span 제거
t = a_tag.get_text(strip=True)  # → "09:30"
```

---

## 8. 크롤링 테스트 스크립트 구조

파일: `scripts/crawl_xdungeon_test.py`

### 전체 구조

```
crawl_xdungeon_test.py
├── 상수/설정
│   ├── BASE_URL        = home.php URL
│   ├── THEME_ACT_URL   = theme.act.php URL
│   ├── HEADERS         = User-Agent, Referer
│   └── BRANCH_MAP      = {s_zizum → (지점명, kakao_place_id)}
│
├── fetch_themes_for_branch(zizum_id)
│   └── 테마 목록 HTML 파싱 → list[dict]
│
├── fetch_theme_detail(theme_id)
│   └── 테마 상세 POST → dict (플레이타임, 시놉시스 등)
│
├── fetch_schedule(zizum_id, date)
│   └── 예약 페이지 HTML 파싱 → list[dict] (테마별 슬롯 목록)
│
└── 테스트 함수 (--mode 인자로 선택)
    ├── test_themes()          → 1단계: 테마 목록
    ├── test_theme_details()   → 2단계: 테마 상세
    └── test_schedule()        → 3단계: 예약 가능 슬롯
```

### 실행 방법

```bash
cd escape-aggregator/backend

# 전체 실행 (테마 + 상세 + 스케줄, 모든 지점, 3일치)
python scripts/crawl_xdungeon_test.py

# 테마 목록만
python scripts/crawl_xdungeon_test.py --mode themes

# 스케줄만, 특정 지점(던전루나=6, 던전스텔라=9), 2일치
python scripts/crawl_xdungeon_test.py --mode schedule --branch 6 9 --days 2

# 스케줄, 전체 지점, 7일치
python scripts/crawl_xdungeon_test.py --mode schedule --days 7
```

### 반환 데이터 형태

```python
# fetch_themes_for_branch(6) 결과 예시
[
  {"theme_id": "8",  "name": "검은 운명의 밤", "branch": "던전루나(강남)", "difficulty": "NORMAL", "genre": "판타지"},
  {"theme_id": "49", "name": "3일",            "branch": "던전루나(강남)", "difficulty": "NORMAL", "genre": "추리"},
]

# fetch_theme_detail("49") 결과 예시
{
  "branch":     "던전루나(강남)",
  "play_time":  "75분",
  "difficulty": "NORMAL",
  "genre":      "추리",
  "theme_name": "3일",
  "synopsis":   "하루 6시간만 깨어있을 수 있는 세상!...",
  "notes":      "해당 테마는 구역이 나눠져 있으며...",
}

# fetch_schedule(6, date(2026, 3, 2)) 결과 예시
[
  {
    "theme_id":   "8",
    "theme_name": "검은 운명의 밤",
    "slots": [
      {"time": "09:30", "status": "sold_out",  "booking_url": ""},
      {"time": "22:30", "status": "available", "booking_url": "home.php?go=rev.make&crypt_data=..."},
    ]
  },
  {
    "theme_id":   "49",
    "theme_name": "3일",
    "slots": [
      {"time": "19:35", "status": "available", "booking_url": "home.php?go=rev.make&crypt_data=..."},
      {"time": "20:20", "status": "available", "booking_url": "home.php?go=rev.make&crypt_data=..."},
    ]
  }
]
```

---

## 9. 실제 실행 결과

2026-03-01 기준 실행 결과 요약:

### 테마 수집 (전 지점)

총 **32개 테마** 수집 완료. 지점별 테마 수 2~6개.

### 스케줄 수집 (던전루나 + 던전스텔라, 2일치)

```
2026-03-02 | 던전루나   | 검은 운명의 밤    → 22:30 (1개 가능)
2026-03-02 | 던전루나   | 3일              → 19:35, 20:20, 21:05, 21:50, 22:35 (5개 가능)
2026-03-02 | 던전스텔라  | 데스티니 앤드 타로 → 21:20, 22:25 (2개 가능)
2026-03-02 | 던전스텔라  | 響:향            → 0개 (전체 매진)
2026-03-02 | 던전스텔라  | TIENTANG CITY   → 0개 (전체 매진)
```

3일치(`2026-03-03`)는 예약 오픈 직후라 대부분 슬롯이 남아 있었다.

---

## 10. 한계 및 주의사항

### 예약 가능 기간 제한
- **오늘부터 최대 7일 후까지만** 예약 가능
- 그 이상 날짜로 요청하면 `"예약 오픈시간이 아닙니다"` 응답
- 크롤링 주기: **매일 1회 이상** 실행해야 최신 상태 유지

### 인원 정보 없음
- xdungeon.net은 최소/최대 인원 정보를 웹에 노출하지 않음
- 필요 시 별도 소스(카카오 플레이스, 네이버 블로그 등) 참고

### crypt_data 예약 링크
- 예약 가능 슬롯의 링크는 암호화된 `crypt_data` 파라미터를 사용
- 이 값은 `theme_num + rev_days + time_index` 조합의 암호화이며,
  직접 예약 자동화에 활용하려면 추가 분석이 필요

### 요청 간격
- API 남용 방지를 위해 요청 사이에 `0.5초` 딜레이 적용
- 전체 9개 지점 × 7일치 × 지점당 평균 3테마 = 약 200회 요청
- 예상 소요 시간: 약 2~3분

### 지점 ID 공백 (s_zizum 8번)
- 현재 s_zizum 값 1~10 중 **8번이 없다**
- 과거 폐점 지점이었거나 내부 시스템용 ID일 가능성이 있음
- 크롤링 시 8번은 건너뛰어야 함 (BRANCH_MAP에 포함 안 됨)
