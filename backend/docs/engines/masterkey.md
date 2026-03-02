# 마스터키 (플레이포인트랩) 예약 시스템 분석

**대상 사이트**: http://www.master-key.co.kr/
**운영 브랜드**: 마스터키 / 플레이포인트랩 (11개 지점 DB 등록, 전국 18개 지점 운영)
**크롤링 방법**: 자체 개발 PHP 시스템 직접 AJAX 호출 + BeautifulSoup HTML 파싱

---

## 1. 분석 배경

DB에 등록된 플레이포인트랩 강남점(`website_url=http://www.master-key.co.kr/`)에서 크롤링 로직을 구현하기 위해 사이트를 분석.

분석 결과 **마스터키(MasterKey)**라는 브랜드가 전국 18개 지점을 운영하며, 각 지점이 동일한 예약 시스템(`master-key.co.kr`)을 공유함을 확인.

---

## 2. API 발견 과정

### 2-1. 브라우저 Network 탭 분석

1. `http://www.master-key.co.kr/booking/bk_detail?bid=35` (강남점) 접속
2. F12 → Network → Fetch/XHR 필터
3. 달력에서 날짜 클릭 시 AJAX 요청 발생 확인:

```
POST http://www.master-key.co.kr/booking/booking_list_new
Content-Type: application/x-www-form-urlencoded
Body: date=2026-03-02&store=35&room=
```

### 2-2. JS 파일 분석으로 파라미터 확인

예약 페이지에서 로드되는 `bk_detail.js`를 분석해 핵심 함수 발견:

```javascript
function list_ajax(date, store, room) {
    $.ajax({
        type: "POST",
        url: "/booking/booking_list_new",
        data: "date=" + date + "&store=" + store + "&room=" + room,
        success: function(data) { ... }
    });
}
```

- `date`: `YYYY-MM-DD` 형식
- `store`: 지점 ID (`bid`, URL의 `?bid=N`과 동일)
- `room`: 빈 문자열 (`""`) — 전 테마 동시 반환

### 2-3. bid(지점 ID) 수집

마스터키 사이트 내 지점 선택 페이지(`/booking/bk_select`)에서 전체 지점 목록과 bid 값 확인.

---

## 3. API 명세

### 요청

```
POST http://www.master-key.co.kr/booking/booking_list_new
Content-Type: application/x-www-form-urlencoded
Referer: http://www.master-key.co.kr/booking/bk_detail?bid={bid}

Body:
  date=YYYY-MM-DD   (조회 날짜)
  store={bid}       (지점 ID)
  room=             (빈 문자열, 전 테마 조회)
```

### 응답

HTML 형식. 테마별로 `div.box2-inner` 블록 하나씩 반환.

```html
<div class='box2-inner'>
    <!-- 왼쪽: 테마 이미지 + 이름 -->
    <div class='left room_explanation_go'>
        <img src='/upload/room/209_img1.gif'>
        <div class='title'> 위로</div>
    </div>
    <!-- 오른쪽: 해시태그 + 시간별 슬롯 -->
    <div class='right'>
        <div class='hashtags'>#감성 #70분</div>

        <!-- 예약완료 슬롯: p.col.false -->
        <p class='col false'>
            <a href='#'>11:55<span>예약완료</span></a>
        </p>

        <!-- 예약가능 슬롯: p.col.true.c_pointer -->
        <p class='col true c_pointer'>
            <a href='#'>14:45<span>예약가능</span></a>
        </p>
    </div>
</div>
```

### 응답 파싱 포인트

| 필드 | 파싱 방법 |
|------|-----------|
| 테마명 | `div.title` 텍스트 |
| room_id | `img[src]`에서 `/upload/room/{room_id}_img1.gif` 패턴 추출 |
| 포스터 URL | `http://www.master-key.co.kr/upload/room/{room_id}_img1.gif` 구성 |
| 소요 시간 | `div.hashtags` 텍스트에서 `(\d+)분` 정규식으로 추출 |
| 시간 | `a` 태그 전체 텍스트에서 `span` 텍스트 제거 → `"HH:MM"` |
| 예약 상태 | `p.col.true` → available, `p.col.false` → full |

---

## 4. 지점 매핑

DB에 등록된 11개 지점과 마스터키 시스템의 `bid` 값 매핑:

| bid | DB cafe_id | 지점명 |
|-----|-----------|--------|
| 35 | 1466171651 | 플레이포인트랩 강남점 |
| 41 | 1987907479 | 노바홍대점 |
| 26 | 671151862  | 건대점 |
| 40 | 1559912469 | 해운대 블루오션스테이션 |
| 43 | 1397923384 | 서면탄탄스트리트점 |
| 1  | 27495854   | 궁동직영점 (대전) |
| 2  | 27523824   | 은행직영점 (대전) |
| 24 | 164781377  | 프라임청주점 |
| 27 | 1850589033 | 평택점 |
| 30 | 1834906043 | 동탄프라임 |
| 23 | 870806933  | 화정점 |

**DB 미등록 지점** (스크립트에서 제외):

| bid | 지점명 |
|-----|--------|
| 31 | 노원점 |
| 21 | 잠실점 |
| 18 | 천안프리미엄점 |
| 13 | 안양점 |
| 7  | 천안두정점 |
| 44 | 서면오리진점 |
| 11 | 홍대점 |

---

## 5. 크롤링 전략

### 테마 발견 (동적 스캔)

마스터키 시스템에는 "테마 목록" 전용 API가 없다. 날짜별 슬롯 조회 API에서 테마가 함께 반환되는 구조이므로, **오늘~6일 후** 날짜를 순서대로 스캔해 발견된 모든 테마를 집계.

이 방식의 장점: 활성 테마만 자동으로 수집됨 (휴면 테마 자동 제외).

### 테마 고유 식별

- **`room_id`**: 이미지 URL(`/upload/room/{room_id}_img1.gif`)에서 추출한 숫자
- DB 저장 키: `(cafe_id, name)` — room_id는 내부 매핑에만 사용
- 동일 테마명이 다른 지점에 있어도 cafe_id가 달라 충돌 없음

### 스케줄 수집

- 오늘~6일 후 (기본값, `--days` 옵션으로 변경 가능)
- 지점별 × 날짜별로 API 1회씩 호출 (= 지점 수 × 날짜 수)
- 과거 슬롯(현재 시각 이전)은 자동 제외
- 상태 변경 시에만 새 레코드 추가 (스냅샷 방식)

---

## 6. 발생한 이슈 및 해결

### 이슈 1: 테마 목록 API 부재

**문제**: 별도의 "전체 테마 조회" 엔드포인트가 없어 테마를 미리 알 수 없음.

**해결**: 슬롯 조회 API를 날짜별로 반복 호출해 테마를 동적으로 발견. 7일치 스캔으로 현재 운영 중인 모든 테마를 확보.

### 이슈 2: a 태그 텍스트에 시간 + 상태 혼재

**문제**: `a` 태그 전체 텍스트가 `"14:45예약가능"` 형식 — 시간만 추출해야 함.

```python
# 잘못된 방법: "14:45예약가능" 전체가 나옴
time_str = a_tag.get_text(strip=True)

# 올바른 방법: span 텍스트("예약가능") 제거 후 시간만 추출
full_text = a_tag.get_text(strip=True)   # "14:45예약가능"
span_text = span_tag.get_text(strip=True)  # "예약가능"
time_str = full_text.replace(span_text, "").strip()  # "14:45"
```

### 이슈 3: room_id 없는 경우 대비

**문제**: 일부 테마에서 이미지 태그가 없거나 경로 패턴이 다를 수 있음.

**해결**: room_id 추출 실패 시 테마명(`name`)을 대체 키로 사용:
```python
room_id = r["room_id"] or r["name"]
```

---

## 7. 동기화 결과

초기 실행 결과 (2026-03-02 기준):

| 항목 | 수량 |
|------|------|
| 처리 지점 수 | 11개 |
| 발견된 테마 수 | 51개 (지점별 2~6개) |
| 추가된 스케줄 레코드 | 2,690개 |

지점별 테마 수:

| bid | 지점 | 테마 수 |
|-----|------|--------|
| 35 | 플레이포인트랩 강남점 | 6 |
| 41 | 노바홍대점 | 2 |
| 26 | 건대점 | 3 |
| 40 | 해운대 블루오션스테이션 | 6 |
| 43 | 서면탄탄스트리트점 | 3 |
| 1  | 궁동직영점 | 5 |
| 2  | 은행직영점 | 5 |
| 24 | 프라임청주점 | 5 |
| 27 | 평택점 | 6 |
| 30 | 동탄프라임 | 4 |
| 23 | 화정점 | 6 |

---

## 8. 실행 방법

```bash
cd escape-aggregator/backend

# 전 지점 동기화 (기본: 오늘~6일 후)
uv run python scripts/sync_masterkey_db.py

# 테마만 동기화 (스케줄 수집 생략)
uv run python scripts/sync_masterkey_db.py --no-schedule

# 특정 지점만 동기화
uv run python scripts/sync_masterkey_db.py --bid 35

# 수집 기간 변경
uv run python scripts/sync_masterkey_db.py --days 3
```

---

## 9. 특이사항 및 주의점

- **HTTP only**: 사이트가 `http://`(비암호화)로 운영됨 → SSL 관련 오류 없음
- **지점 추가 시**: `SHOP_MAP`에 `bid → cafe_id` 항목 추가 후 재실행
- **bid 값 변경 없음**: 오래된 브랜드이며 URL 기반 bid가 안정적으로 유지됨
- **테마 변경**: 신규/폐지 테마는 다음 실행 시 자동 감지 (7일치 스캔)
- **booking_url**: 지점 단위 링크(`/booking/bk_detail?bid={bid}`)만 제공, 테마/시간대별 직접 링크는 없음
