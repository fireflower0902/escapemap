# xdungeon.net (비트포비아 던전) 크롤링 분석 문서

> **대상 사이트**: https://xdungeon.net
> **운영사**: (주)비트포비아
> **관련 스크립트**: `scripts/crawl_xdungeon_test.py`, `scripts/sync_xdungeon_db.py`
> **관련 엔진**: `app/engines/bitfobia.py` (구현 예정)
> **최초 분석일**: 2026-02-XX | **DB 동기화 추가**: 2026-03-01 | **booking_url 버그 수정**: 2026-03-01

---

## 목차

1. [배경 — 왜 이 사이트를 분석했는가](#1-배경)
2. [사이트 구조 파악 과정](#2-사이트-구조-파악-과정)
3. [지점 ID(s_zizum) 매핑 발견](#3-지점-ids_zizum-매핑-발견)
4. [테마 목록 추출 방법](#4-테마-목록-추출-방법)
5. [테마 상세정보 추출 방법](#5-테마-상세정보-추출-방법)
6. [예약 가능 시간대 추출 방법](#6-예약-가능-시간대-추출-방법)
7. [파싱 중 발생한 버그와 해결](#7-파싱-중-발생한-버그와-해결)
8. [DB 동기화 스크립트 구현](#8-db-동기화-스크립트-구현)
9. [booking_url 버그 발견과 수정](#9-booking_url-버그-발견과-수정)
10. [실행 결과](#10-실행-결과)
11. [한계 및 주의사항](#11-한계-및-주의사항)

---

## 1. 배경

비트포비아는 전국에 여러 방탈출 지점을 운영하는 대형 체인이다.
카카오맵 전국 크롤링 당시 "비트포비아 던전루나", "비트포비아 던전스텔라" 2개만 DB에 등록되었는데, 알고 보니 **총 9개 지점이 xdungeon.net이라는 자체 예약 시스템을 사용**하고 있었다.

더불어 기존 크롤링 필터(`is_escape_room()`)가 이름에 "방탈출/이스케이프/escape/탈출" 키워드가 없으면 거르는 방식이었기 때문에, "비트포비아 강남던전점" 같은 이름들은 전부 누락되었다.

**별도 스크립트로 7개 지점을 DB에 추가** (`scripts/add_missing_bitfobia.py`).

---

## 2. 사이트 구조 파악 과정

### 2-1. 홈페이지 진입

xdungeon.net을 열면 가장 먼저 보이는 URL 구조:

```
https://xdungeon.net/layout/res/home.php?go=rev.main
```

`go=` 파라미터로 페이지를 전환하는 **PHP 기반 자체 개발 예약 시스템**이다.
React/Next.js 같은 SPA가 아니라, 서버에서 HTML을 통째로 만들어서 보내주는 방식.
→ 별도 JavaScript 실행 없이 **requests + BeautifulSoup만으로 데이터 파싱 가능**.

### 2-2. 페이지 종류

| go= 값 | 역할 |
|--------|------|
| `theme.list` | 테마 목록 페이지 |
| `rev.main` | 예약 페이지 (지점+날짜 선택 → 시간표 노출) |
| `rev.guide` | 예약 안내 |
| `rev.login` | 예약 확인 및 취소 |

### 2-3. SSR 확인

예약 페이지 HTML을 직접 요청해보니, JavaScript 실행 없이도 모든 시간 슬롯 데이터가 이미 HTML에 담겨 있었다. **서버가 지점+날짜에 맞게 HTML을 완성해서 보낸다**.

```
GET https://xdungeon.net/layout/res/home.php?go=rev.main&s_zizum=6&rev_days=2026-03-02
```

위 요청 하나로 던전루나의 2026-03-02 전체 예약 현황을 받아올 수 있다.

---

## 3. 지점 ID(s_zizum) 매핑 발견

예약 페이지의 `<select>` 드롭다운 HTML:

```html
<select name="s_zizum">
  <option value="1">던전101</option>
  <option value="2">강남던전</option>
  <option value="3">홍대던전</option>
  <option value="4">강남던전Ⅱ</option>
  <option value="5">홍대던전Ⅲ</option>
  <option value="6">던전루나(강남)</option>
  <option value="7">서면던전(부산)</option>
  <option value="9">던전스텔라(강남)</option>
  <option value="10">서면던전 레드(부산)</option>
</select>
```

`s_zizum` 값이 모든 API 요청의 핵심 파라미터. 숫자 8이 빠져 있는 것은 과거 폐점 지점의 ID로 추정.

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

## 4. 테마 목록 추출 방법

### 요청

```
GET https://xdungeon.net/layout/res/home.php?go=theme.list&s_zizum={지점ID}
```

### HTML 구조

```html
<li>
  <a href="javascript:_fun_theme_view('49')">
    <div class="img_box">
      <img src="/file/theme/49/49_8635451017.jpg"/>
    </div>
    <div class="txt_box">
      <p class="thm">3일</p>
      <div class="tag">
        <span class="str">던전루나(강남)</span>
        <span class="lv">NORMAL</span>
        <span class="gr">추리</span>
      </div>
    </div>
  </a>
</li>
```

### 파싱 로직

```python
link = li.find("a", href=lambda h: h and "_fun_theme_view" in str(h))
m = re.search(r"_fun_theme_view\('(\d+)'\)", link["href"])
theme_id = m.group(1)  # "49"

name       = li.find("p",    class_="thm").get_text(strip=True)
difficulty = li.find("span", class_="lv").get_text(strip=True)   # "NORMAL"
genre      = li.find("span", class_="gr").get_text(strip=True)   # "추리"
img        = li.find("img")
poster     = f"https://xdungeon.net{img['src']}" if img else None
```

**난이도 변환 맵:**
```python
DIFFICULTY_MAP = {"EASY": 2, "NORMAL": 3, "HARD": 4}
```

---

## 5. 테마 상세정보 추출 방법

### 발견 과정

테마 목록에는 **플레이타임이 없다**. 클릭 시 팝업으로 상세정보를 로드한다:

```javascript
function _fun_theme_view(num) {
  $.ajax({
    type: "POST",
    url: "../../core/res/theme.act.php",
    data: "not_html=Y&act=view&num=" + num + "&ck_rev_but=N",
    success: function(data) {
      $("#popup_view").html(data);
    }
  });
}
```

### 요청

```
POST https://xdungeon.net/core/res/theme.act.php
Content-Type: application/x-www-form-urlencoded

not_html=Y&act=view&num=49&ck_rev_but=N
```

### 응답 HTML 구조

```html
<dl class="half">
  <dt>플레이타임</dt>
  <dd>75분</dd>
</dl>
<dl class="synp">
  <dt>시놉시스</dt>
  <dd>하루 6시간만 깨어있을 수 있는 세상!...</dd>
</dl>
```

### 파싱 로직

```python
for dl in soup.find_all("dl"):
    dt = dl.find("dt")
    dd = dl.find("dd")
    key_map = {
        "플레이타임": "play_time",  # "75분" → int(75)
        "시놉시스":   "synopsis",
        "특이사항":   "notes",
    }
    key = dt.get_text(strip=True)
    if key in key_map:
        detail[key_map[key]] = dd.get_text(separator=" ", strip=True)

# 플레이타임 파싱: "75분" → 75
m = re.search(r"(\d+)", detail.get("play_time", ""))
duration = int(m.group(1)) if m else None
```

---

## 6. 예약 가능 시간대 추출 방법

### 요청

```
GET https://xdungeon.net/layout/res/home.php?go=rev.main&s_zizum=6&rev_days=2026-03-02
```

### HTML 구조 — 시간 슬롯 3가지 상태

```
div.thm_box
  └─ div.box  (테마 하나)
       └─ div.time_box
            └─ ul
                 ├─ li.sale        → 예약 가능
                 ├─ li.dead.sale   → 매진
                 └─ li             → 비운영
```

**예약 가능 (li.sale):**
```html
<li class="sale">
  <a href="home.php?go=rev.make&crypt_data=bXJ5aGlz...">
    <span>SALE</span>09:30
  </a>
</li>
```

**매진 (li.dead.sale):**
```html
<li class="dead sale">
  <a>14:30</a>
</li>
```

### 파싱 로직

```python
for li in time_box.find_all("li"):
    classes = li.get("class", [])
    is_sale = "sale" in classes
    is_dead = "dead" in classes

    a_tag = li.find("a")
    for span in a_tag.find_all("span"):
        span.decompose()   # <span>SALE</span> 제거
    t = a_tag.get_text(strip=True)   # "09:30"

    if is_sale and not is_dead:
        status = "available"
    elif is_sale and is_dead:
        status = "full"
    else:
        status = "closed"
```

---

## 7. 파싱 중 발생한 버그와 해결

### 버그: 시간 텍스트에 "SALE"이 붙어서 출력됨

**증상**: `09:30`이 아니라 `SALE09:30`으로 출력됨

**원인**: `li.get_text(strip=True)`가 `<span>SALE</span>` 안의 텍스트까지 합쳐서 반환.

**해결**: `<a>` 태그 안의 `<span>`을 먼저 `decompose()`로 제거한 뒤 텍스트 추출.

```python
# 수정 전 (버그)
t = li.get_text(strip=True)   # → "SALE09:30"

# 수정 후 (정상)
a_tag = li.find("a")
for span in a_tag.find_all("span"):
    span.decompose()
t = a_tag.get_text(strip=True)  # → "09:30"
```

---

## 8. DB 동기화 스크립트 구현

크롤링 테스트 스크립트(`crawl_xdungeon_test.py`) 검증 후, 실제 DB에 저장하는 스크립트(`sync_xdungeon_db.py`)를 구현했다.

### 핵심 설계 결정

**테마 upsert**: `cafe_id + name` 조합으로 기존 테마 조회. 없으면 INSERT, 있으면 UPDATE.

**스케줄 변경 추적**: 단순 INSERT/UPDATE 대신, **상태가 바뀐 슬롯만 새 행 추가**:
```python
if existing.status != slot["status"]:
    session.add(Schedule(..., crawled_at=datetime.now()))
```
→ 시간대별 예약 상태 변화 이력 보존 가능.

---

## 9. booking_url 버그 발견과 수정

### 발견 경위

프론트엔드에서 예약 가능 슬롯을 클릭했을 때 아래 오류가 발생:

```
[에러]테마정보가 없습니다
```

### 원인 분석

DB에 저장된 `booking_url` 형식:
```
https://xdungeon.net/layout/res/home.php?go=rev.make&crypt_data=bXJ5aGlzMmVjY2x...
```

`crypt_data` 파라미터는 `theme_num + rev_days + time_index`를 암호화한 **세션 의존 토큰**이었다.
크롤링 시점의 세션에서 발급된 토큰이므로, 시간이 지나거나 다른 브라우저에서 접근하면 유효하지 않다.
→ `rev.make` 경로는 특정 시간 슬롯의 직접 예약 페이지인데, 세션 토큰이 만료되면 "[에러]테마정보가 없습니다"를 반환한다.

### 해결

`crypt_data` 기반 직접 예약 URL 대신, **지점+날짜 예약 메인 페이지 URL**을 사용:

```python
# 수정 전 (세션 의존, 만료됨)
booking_url = "home.php?go=rev.make&crypt_data=bXJ5aGlz..."

# 수정 후 (안정적, 날짜 정보 포함)
booking_url = (
    f"https://xdungeon.net/layout/res/home.php"
    f"?go=rev.main&s_zizum={zizum_id}&rev_days={date}"
)
```

이 URL로 이동하면 해당 지점의 해당 날짜 예약 페이지로 바로 연결되며, 사용자가 원하는 테마와 시간을 직접 선택해서 예약할 수 있다.

### 기존 DB 레코드 일괄 수정

이미 DB에 저장된 651개의 잘못된 booking_url을 일괄 수정했다:

```python
# 각 스케줄의 theme_id → cafe_id → s_zizum을 역추적
CAFE_TO_ZIZUM = {v: k for k, v in BRANCH_MAP.items()}

for row in schedules_with_crypt_data:
    cafe_id = theme_cafe_map[row.theme_id]
    zizum = CAFE_TO_ZIZUM.get(cafe_id)
    date_str = row.date.strftime("%Y-%m-%d")
    row.booking_url = (
        f"https://xdungeon.net/layout/res/home.php"
        f"?go=rev.main&s_zizum={zizum}&rev_days={date_str}"
    )

# 결과: available 업데이트 651개
```

---

## 10. 실행 결과

### 테마 수집 (전 지점)

총 **32개 테마** 수집 완료. 지점별 테마 수 2~6개.

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

### DB 동기화 결과

```
테마 동기화 완료: 32개 추가 / 0개 갱신
스케줄 동기화 완료: 1340개 레코드 추가 (7일치)
booking_url 수정: available 651개
```

---

## 11. 한계 및 주의사항

### 예약 가능 기간 제한
오늘부터 최대 **7일 후까지만** 예약 오픈. 그 이상 날짜는 `"예약 오픈시간이 아닙니다"` 반환.

### 인원 정보 없음
xdungeon.net은 최소/최대 인원 정보를 웹에 노출하지 않음. 별도 소스 참고 필요.

### crypt_data 예약 링크 사용 불가
`go=rev.make&crypt_data=...` URL은 세션 의존 토큰으로, 직접 예약 자동화 불가.
현재는 `go=rev.main` 방식(날짜별 예약 메인 페이지)으로 대체.

### 지점 ID 공백 (s_zizum 8번)
8번 지점이 없음. 과거 폐점 지점의 ID로 추정. `BRANCH_MAP`에 포함하지 않음.

### 요청 간격
서버 부하 방지를 위해 요청 사이에 0.4초 딜레이 적용.
9개 지점 × 7일치 × 평균 3.5테마 + 테마 상세 조회 ≈ 약 250회 요청. 소요 시간 2~3분.
