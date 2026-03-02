# 스튜디오이에스씨 (studioesc.co.kr) 크롤링 분석 문서

> **대상 사이트**: https://studioesc.co.kr/
> **운영사**: Studio ESC
> **관련 스크립트**: `scripts/sync_studioesc_db.py`
> **cafe_id**: `1908100709`
> **분석 완료일**: 2026-03-02

---

## 목차

1. [배경](#1-배경)
2. [플랫폼 파악 — sinbiweb PHP CMS](#2-플랫폼-파악--sinbiweb-php-cms)
3. [실제 URL 구조 발견](#3-실제-url-구조-발견)
4. [예약 페이지 HTML 구조](#4-예약-페이지-html-구조)
5. [타임슬롯 파싱 로직](#5-타임슬롯-파싱-로직)
6. [날짜별 가용성 처리](#6-날짜별-가용성-처리)
7. [세션 쿠키 처리](#7-세션-쿠키-처리)
8. [DB 동기화 전략](#8-db-동기화-전략)
9. [실행 결과](#9-실행-결과)
10. [한계 및 주의사항](#10-한계-및-주의사항)

---

## 1. 배경

강남 미크롤링 카페 중 스튜디오이에스씨는 `home.php?go=rev.make` URL 패턴이
xdungeon.net(`home.php?go=rev.main`)과 유사해 같은 플랫폼일 가능성이 있었다.
분석 결과 **sinbiweb**이라는 한국형 PHP CMS로 판명됐으며,
xdungeon과는 다르지만 일관된 구조를 갖고 있었다.

---

## 2. 플랫폼 파악 — sinbiweb PHP CMS

HTML 소스에서 확인:

```html
<meta name="publisher" content="(주)신비웹,신비웹,sinbiweb,sinbiweb.co.kr,www.sinbiweb.co.kr" />
```

sinbiweb은 `home.php?go={페이지코드}` 형태로 모든 페이지를 라우팅하는 구조다.

| URL 파라미터 | 설명 |
|-------------|------|
| `go=main` | 메인 페이지 |
| `go=theme.list` | 테마 목록 |
| `go=rev.make` | 예약 페이지 |
| `go=rev.make.input` | 예약 폼 입력 (특정 슬롯) |
| `go=rev.login` | 예약 확인/취소 |

---

## 3. 실제 URL 구조 발견

처음에 `https://studioesc.co.kr/home.php?go=rev.make`를 시도했으나 **404**가 반환됐다.

원인 파악: 루트(`/`) 접속 시 **302 리다이렉트** 발생.

```
GET https://studioesc.co.kr/
→ 302 Location: https://studioesc.co.kr/layout/res/home.php?go=main
```

즉 실제 PHP 파일 경로는 `/layout/res/home.php`이다.

```python
BASE_URL = "https://studioesc.co.kr/layout/res/home.php"
RESERVE_URL = BASE_URL + "?go=rev.make"
```

---

## 4. 예약 페이지 HTML 구조

`GET {RESERVE_URL}&rev_days=YYYY-MM-DD` 요청 시 전체 테마 목록과 슬롯이 포함된 HTML이 반환된다.

```
https://studioesc.co.kr/layout/res/home.php?go=rev.make&rev_days=2026-03-07
```

HTML 구조:

```html
<div class="theme_box">
  <div class="theme_Title">
    <h3 class="h3_theme">검은마법사 (The Dark Enchanter)</h3>
  </div>
  <div class="theme_pic">
    <img src="../../file/theme/1_a.jpg?..." />
  </div>
  <div class="time_Area">
    <ul class="reserve_Time">
      <li>
        <a class="end">
          <span class="time">09:30 </span>
          <span class="impossible">예약마감</span>
        </a>
      </li>
      <li>
        <a href="home.php?go=rev.make.input&rev_days=2026-03-07&theme_time_num=54">
          <span class="time">11:05 </span>
          <span class="possible">예약가능</span>
        </a>
      </li>
    </ul>
  </div>
</div>
```

---

## 5. 타임슬롯 파싱 로직

`BeautifulSoup`으로 `.theme_box` 단위 파싱:

```python
for box in soup.select(".theme_box"):
    theme_name = box.select_one("h3.h3_theme").text.strip()

    # 포스터: ../../file/theme/1_a.jpg → 절대 경로 변환
    img = box.select_one(".theme_pic img")
    raw_src = img["src"].split("?")[0]  # 캐시버스터 제거
    poster_url = "https://studioesc.co.kr/" + raw_src[6:]  # ../../ 제거

    for li in box.select("ul.reserve_Time li"):
        time_str = li.select_one("span.time").text.strip()   # "09:30"
        possible = li.select_one("span.possible")
        impossible = li.select_one("span.impossible")

        if possible:
            status = "available"
            href = li.select_one("a").get("href", "")
            booking_url = "https://studioesc.co.kr/layout/res/" + href
        elif impossible:
            status = "full"
            booking_url = None
```

**status 판별 기준**:

| HTML 클래스 | 상태 |
|------------|------|
| `span.possible` | `available` |
| `span.impossible` | `full` |
| `.theme_box` 없음 | 예약 미오픈 → 건너뜀 |

---

## 6. 날짜별 가용성 처리

날짜별로 `rev_days=YYYY-MM-DD` 파라미터를 바꿔가며 요청:

```
GET /layout/res/home.php?go=rev.make&rev_days=2026-03-03
GET /layout/res/home.php?go=rev.make&rev_days=2026-03-04
...
```

**예약 미오픈 날짜 처리**:
- 예약 가능 날짜: `.theme_box` 2개 존재 → 정상 파싱
- 미오픈 날짜: `.theme_box` 0개 → 스킵 (schedule 미생성)

2026-03-02 기준 결과:

| 날짜 | 가능 | 마감 |
|------|------|------|
| 3/2 | 2 | 0 (과거 슬롯 대부분 제외) |
| 3/3 | 14 | 2 |
| 3/7 | 14 | 4 |
| 3/9~ | 예약 미오픈 | — |

---

## 7. 세션 쿠키 처리

sinbiweb 사이트는 `PHPSESSID`가 필요하다.

루트 접속 시 자동 발급됨 → `CookieJar`로 자동 처리:

```python
cj = CookieJar()
https_handler = urllib.request.HTTPSHandler(context=_SSL_CTX)
opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(cj),
    https_handler,
)

# 루트 GET → 302 → main 페이지 → PHPSESSID 획득
opener.open(Request("https://studioesc.co.kr/", ...))
```

이후 모든 `opener.open()` 호출에 쿠키가 자동 포함된다.

---

## 8. DB 동기화 전략

1. 루트 GET으로 세션 획득
2. 오늘 날짜 예약 페이지에서 테마 목록 추출 (→ Theme upsert)
3. 날짜별 순회로 Schedule upsert

**booking_url**: `https://studioesc.co.kr/layout/res/home.php?go=rev.make.input&rev_days={date}&theme_time_num={N}` (가능 슬롯만)

테마 포스터 URL 변환:

```
../../file/theme/1_a.jpg → https://studioesc.co.kr/file/theme/1_a.jpg
../../file/theme/2_a.jpg → https://studioesc.co.kr/file/theme/2_a.jpg
```

---

## 9. 실행 결과

```
============================================================
스튜디오이에스씨 (Studio ESC) → DB 동기화
============================================================

[ 0단계 ] 세션 획득: 완료
[ 1단계 ] 테마 목록:
  '검은마법사 (The Dark Enchanter)' | poster=https://studioesc.co.kr/file/theme/1_a.jpg
  '하얀마법사 (The Pure Enchanter)' | poster=https://studioesc.co.kr/file/theme/2_a.jpg

[ 2단계 ] 테마 동기화: 2개 추가 (id=164, 165)
[ 3단계 ] 스케줄 동기화: 102개 레코드 추가 (14일치, 미오픈 제외)
```

---

## 10. 한계 및 주의사항

- **예약 미오픈 날짜**: 보통 약 1주일 앞까지만 오픈 → schedule 미생성
- **슬롯 시간 요일마다 다름**: 평일/주말 슬롯 시작 시간이 다름 (10:20 vs 09:30 등)
- **sinbiweb 플랫폼 업데이트 시**: CSS 클래스명이 바뀌면 파싱 로직 수정 필요
- **booking_url 슬롯별 직접 링크**: `theme_time_num` 값이 날짜마다 다르므로 실시간 파싱이 필수
