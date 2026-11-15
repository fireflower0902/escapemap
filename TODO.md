# 추후 작업 목록

## 🕐 크롤링 주기 — 시간대별 분리 (20분 / 1시간)

**목표**: 낮 시간대(예약 활발)는 20분마다, 새벽은 1시간마다 크롤링

**현재**: 매시간 정각 1회 (`0 * * * *`)

**변경 방안** (`.github/workflows/crawl.yml`):
```yaml
on:
  schedule:
    - cron: "*/20 1-13 * * *"   # 낮 10시~밤 22시 KST (UTC 01~13) — 20분마다
    - cron: "0 14-0 * * *"      # 밤 23시~오전 9시 KST (UTC 14~00) — 1시간마다
    - cron: "0 15 * * *"        # 매일 자정 KST — 카페/테마 전체 동기화
```

**왜 지금 안 하나**: Firebase 무료 요금제(Spark) 쓰기 한도(20,000/일) 초과 우려
- 20분 주기(72회/일) × 265 카페 = 해시 쓰기만 19,080건 → 한도 도달
- 먼저 코드 최적화 또는 Blaze 요금제 전환 후 진행 권장

**코드 최적화 방안** (선택): `save_cafe_hashes()`를 데이터 변경 시에만 쓰도록 수정
```python
# backend/app/firestore_db.py
def save_cafe_hashes(db, cafe_id, hashes, changed: bool = False):
    if not changed:
        return  # 변경 없으면 쓰기 생략
    today = _date.today().isoformat()
    pruned = {k: v for k, v in hashes.items() if k >= today}
    if pruned:
        db.collection("cafe_hashes").document(cafe_id).set(pruned)
```
→ 최적화 후 예상 쓰기: ~7,600/일 (38%) → 20분 크롤도 무료 유지 가능

---

---

## 🔐 소셜 로그인 구현 (카카오 + 구글 + 네이버)

**스택**: Firebase Authentication + 같은 Firestore에 `users/{uid}` 컬렉션 추가

### 구현 순서
1. Firebase Console에서 Authentication 활성화
2. Google OAuth → Firebase 직접 지원, 설정만 하면 됨
3. Kakao OAuth → 카카오 개발자 앱 등록 → FastAPI에서 커스텀 토큰 발급
4. Naver OAuth → 네이버 개발자 앱 등록 → FastAPI에서 커스텀 토큰 발급

### Firestore users 컬렉션 구조
```
users/{uid}
  provider: "kakao" | "google" | "naver"
  email: "..."
  nickname: "..."
  profile_image_url: "..."
  created_at: Timestamp
  last_login_at: Timestamp
```

### 로그인 화면 UI
```
[ 카카오로 시작하기 ]
[ 구글로 시작하기   ]
[ 네이버로 시작하기 ]

☐ 이용약관 및 개인정보처리방침에 동의합니다.  [약관 확인 →]
```
- 체크박스 미체크 시 로그인 버튼 비활성화
- [약관 확인 →] 클릭 시 약관/개인정보처리방침 페이지로 이동

### 법적 필수 항목
- [ ] 개인정보처리방침 페이지 작성 및 게시
- [ ] 이용약관 페이지 작성 및 게시
- [ ] 로그인 화면에 동의 체크박스 + 약관 확인 링크 추가

---

## 📌 기타 메모

- Firebase Blaze(종량제) 전환 시 초과 비용: 약 **월 $0.4** 수준 (거의 무료)
- 시간대 분리만 원하면 코드 최적화 없이 Blaze로 전환하는 게 더 간단할 수 있음
