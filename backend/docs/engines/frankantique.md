# 프랭크의골동품가게 예약 시스템 분석

**대상 사이트**: https://thefrank.co.kr/
**운영 브랜드**: 프랭크의골동품가게 (강남구 강남대로96길 19, 단일 지점)
**크롤링 방법**: 신비웹(sinbiweb) PHP CMS AJAX API 호출 + BeautifulSoup HTML 파싱

---

## 1. 분석 배경

DB에 등록된 프랭크의골동품가게(`cafe_id=874592991`, `website_url=https://thefrank.co.kr/`)에서 크롤링 로직을 구현하기 위해 사이트를 분석.

---

## 2. API 발견 과정

### 2-1. URL 구조 파악

`https://thefrank.co.kr/` 접속 시 302 리다이렉트 발생:

```
https://thefrank.co.kr/
  → (302) https://thefrank.co.kr/layout/res/home.php?go=main
```

메인 페이지의 실제 경로가 `/layout/res/home.php`임을 확인. 이에 따라 예약 관련 페이지도 동일 경로 구조:
- 예약하기: `https://thefrank.co.kr/layout/res/home.php?go=rev.make`

### 2-2. 브라우저 Network 탭 분석

예약 페이지(`?go=rev.make`)에서 F12 → Network → XHR 필터로 AJAX 요청 캡처.

날짜 선택 또는 테마 변경 시 다음 패턴의 POST 요청 발생:

```
POST https://thefrank.co.kr/core/res/rev.make.ajax.php
Content-Type: application/x-www-form-urlencoded
Body: act=time&rev_days=2026-03-02&theme_num=5
```

### 2-3. JS 파일 분석으로 전체 액션 파악

예약 페이지 소스 내 JavaScript에서 AJAX 호출 함수 발견:

```javascript
// 테마 목록 로드
$.ajax({
    type: "POST",
    url: "../../core/res/rev.make.ajax.php",
    data: "act=theme&zizum_num=" + f.zizum_num.value + "&theme_num=" + f.theme_num.value + "&rev_days=" + f.rev_days.value,
    ...
});

// 시간대 슬롯 로드
$.ajax({
    type: "POST",
    url: "../../core/res/rev.make.ajax.php",
    data: "act=time&rev_days=" + f.rev_days.value + "&theme_num=" + f.theme_num.value,
    ...
});
```

- 경로 `../../core/res/` = `/layout/res/` 기준 2단계 위 = 사이트 루트(`/`)
- 절대 URL: `https://thefrank.co.kr/core/res/rev.make.ajax.php`

### 2-4. form 초기값으로 파라미터 확인

예약 페이지 HTML에서 hidden input 발견:

```html
<input type=hidden name=zizum_num value='1'>
<input type=hidden name=rev_days  value='2026-03-02'>
<input type=hidden name=theme_num value='5'>
```

- `zizum_num=1`: 지점 번호 (프랭크는 단일 지점이므로 항상 1)
- `theme_num=5`: 기본 선택 테마

---

## 3. API 명세

### 공통

```
POST https://thefrank.co.kr/core/res/rev.make.ajax.php
Content-Type: application/x-www-form-urlencoded
Referer: https://thefrank.co.kr/layout/res/home.php?go=rev.make
```

### 3-1. 테마 목록 조회

```
Body: act=theme&zizum_num=1&theme_num=&rev_days=YYYY-MM-DD
```

**응답 (HTML):**

```html
<a href="javascript:fun_theme_select('5','0')">
    <span>My Private Heaven</span>
</a>
<a href="javascript:fun_theme_select('6','1')">
    <span>Brooklyn My Love</span>
</a>
<a href="javascript:fun_theme_select('7','2')">
    <span>Plan to save my dear</span>
</a>
```

파싱 포인트:
- `a[href]`에서 `fun_theme_select('N', ...)` 패턴으로 `theme_num` 추출
- `span` 텍스트 → 테마명

### 3-2. 테마 포스터 이미지 조회

```
Body: act=theme_img&theme_num={N}
```

**응답 (HTML):**

```html
<img src="/file/theme/5_3776449804.png">
```

포스터 URL = `https://thefrank.co.kr` + img[src]

### 3-3. 시간대 슬롯 조회

```
Body: act=time&rev_days=YYYY-MM-DD&theme_num={N}
```

**응답 (HTML):**

```html
<!-- 예약완료: a.none -->
<a class="none">
    <span><img src="..."> &nbsp; 10시 00분 </span>
</a>

<!-- 예약가능: a[href] (class 없음) -->
<a href="javascript:fun_theme_time_select('164','0')">
    <span><img src="..."> &nbsp; 10시 30분 </span>
</a>
```

파싱 포인트:
- `a.none` → full (예약완료)
- `a[href]` containing `fun_theme_time_select` → available (예약가능)
- span 텍스트에서 `(\d+)시\s*(\d+)분` 정규식으로 시간 추출

---

## 4. 테마 목록 (2026-03-02 기준)

| theme_num | 테마명 | 포스터 URL |
|-----------|--------|-----------|
| 5 | My Private Heaven | https://thefrank.co.kr/file/theme/5_3776449804.png |
| 6 | Brooklyn My Love | https://thefrank.co.kr/file/theme/6_5641498189.png |
| 7 | Plan to save my dear | https://thefrank.co.kr/file/theme/7_8452267713.jpg |

---

## 5. 크롤링 전략

1. `act=theme` 호출로 현재 운영 중인 테마 목록을 동적으로 수집 (theme_num + 테마명)
2. `act=theme_img` 호출로 테마별 포스터 이미지 URL 수집
3. 오늘~6일 후 날짜 × 전체 테마에 대해 `act=time` 호출로 슬롯 수집
4. `(cafe_id, name)` 기준으로 테마 upsert, 상태 변경 시 신규 스케줄 레코드 추가

---

## 6. 발생한 이슈 및 해결

### 이슈 1: 실제 경로가 `/layout/res/` 하위

**문제**: `https://thefrank.co.kr/home.php?go=rev.make`로 직접 접근하면 404 방화벽 차단.

**원인**: 사이트가 302 리다이렉트로 `/layout/res/home.php?go=main`으로 안내. JS에서 상대 경로(`../../core/res/...`)로 API 호출.

**해결**: 실제 절대 URL `https://thefrank.co.kr/core/res/rev.make.ajax.php`로 직접 POST 요청.

### 이슈 2: SSL 인증서 체인 오류

**문제**: Python `urllib.request`로 HTTPS 요청 시 `[SSL: CERTIFICATE_VERIFY_FAILED]` 오류 발생.

```
<urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed:
unable to get local issuer certificate (_ssl.c:1081)>
```

**원인**: 서버 SSL 인증서가 중간 인증서를 포함하지 않음 (curl은 자체 CA 번들로 통과).

**해결**: `ssl.create_default_context()`로 컨텍스트 생성 후 검증 비활성화:

```python
import ssl
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

urllib.request.urlopen(req, timeout=15, context=_SSL_CTX)
```

---

## 7. 동기화 결과

초기 실행 결과 (2026-03-02 기준):

| 항목 | 수량 |
|------|------|
| 처리 지점 수 | 1개 (단일 지점) |
| 등록된 테마 수 | 3개 |
| 추가된 스케줄 레코드 | 179개 |

---

## 8. 실행 방법

```bash
cd escape-aggregator/backend

# 전체 동기화 (오늘~6일 후)
uv run python scripts/sync_frankantique_db.py

# 테마만 동기화 (스케줄 수집 생략)
uv run python scripts/sync_frankantique_db.py --no-schedule

# 수집 기간 변경
uv run python scripts/sync_frankantique_db.py --days 3
```

---

## 9. 특이사항 및 주의점

- **단일 지점**: `zizum_num=1` 고정
- **theme_num 연속성 없음**: 1~4번이 빈 번호 (삭제된 테마 추정), 5·6·7번만 유효
  - theme_num 1~4, 8+ 호출 시 `alert('잘못된 접근입니다.')` 반환
  - `act=theme` 응답으로 유효한 theme_num 목록을 동적으로 파악하므로 번호 하드코딩 불필요
- **SSL 우회 필요**: doorescape, macro.playthe.world와 동일한 SSL 인증서 체인 문제
- **booking_url**: 직접 예약 페이지 링크만 제공 (`?go=rev.make`), 테마·시간대별 직접 링크 없음
- **플랫폼**: 신비웹(sinbiweb) PHP CMS — xdungeon(sinbiweb 계열 추정)과 구조 유사하나 별도 플랫폼
