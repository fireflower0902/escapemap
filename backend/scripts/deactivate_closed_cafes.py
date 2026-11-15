#!/usr/bin/env python3
"""폐업한 카페를 is_active=false로 표시"""
import sys
from pathlib import Path
import json

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings
from app.firestore_db import init_firestore, get_db

# 검증 결과에서 확인된 폐업/접근 불가 카페들
DEFINITELY_CLOSED = [
    "401872428",  # 시그널헌터 - 폐업 키워드 감지
    "260184665",  # 초상화 - 예약 기능 없음
    "123477337",  # 파라박스 - 도메인 없음
    "2006661572",  # 쿠쿠룸190000 - HTTP 400
]

# 카카오맵 링크만 있는 카페들 (폐업 가능성 높음)
KAKAO_MAP_ONLY = [
    "2006661572",  # 쿠쿠룸190000
    "260184665",   # 초상화
    "578778978",   # 쿠쿠룸 1089
    "1548712469",  # 방탈출둡두
    "987374256",   # 파노라마 홍대
    "1078153820",  # 차작가의 방탈출테마연구소
    "1336760672",  # 방탈출크라임씬
    "17410648",    # 이스케이프
    "880372928",   # 더파인더 방탈출
]

def deactivate_closed_cafes(cafe_ids, reason):
    """폐업한 카페를 is_active=false로 표시"""
    init_firestore(settings.firebase_credentials_path)
    db = get_db()

    print("=" * 100)
    print(f"폐업 카페 비활성화 ({reason})")
    print("=" * 100)

    deactivated_count = 0
    failed_count = 0

    for cafe_id in cafe_ids:
        try:
            # 카페 정보 먼저 확인
            cafe_doc = db.collection("cafes").document(cafe_id).get()
            if not cafe_doc.exists:
                print(f"  ⚠️  카페를 찾을 수 없음: {cafe_id}")
                failed_count += 1
                continue

            cafe_data = cafe_doc.to_dict()
            cafe_name = cafe_data.get("name", "Unknown")

            # is_active=false로 업데이트
            db.collection("cafes").document(cafe_id).set(
                {"is_active": False},
                merge=True
            )

            print(f"  ✅ {cafe_name} ({cafe_id}) → is_active=false")
            deactivated_count += 1

        except Exception as e:
            print(f"  ❌ {cafe_id}: {str(e)}")
            failed_count += 1

    print("\n" + "=" * 100)
    print(f"결과: {deactivated_count}개 비활성화, {failed_count}개 실패")
    print("=" * 100)

    return deactivated_count

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["confirmed", "kakao-only", "all"],
        default="confirmed",
        help="비활성화할 카페 범위"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제로 업데이트하지 말고 미리보기만"
    )

    args = parser.parse_args()

    if args.mode == "confirmed":
        cafe_ids = DEFINITELY_CLOSED
        reason = "확인된 폐업 (검증 완료)"
    elif args.mode == "kakao-only":
        cafe_ids = KAKAO_MAP_ONLY
        reason = "카카오맵 링크만 있는 카페"
    else:  # all
        cafe_ids = list(set(DEFINITELY_CLOSED + KAKAO_MAP_ONLY))
        reason = "폐업 + 카카오맵만"

    print(f"\n비활성화할 카페 수: {len(cafe_ids)}")

    if args.dry_run:
        print("\n[DRY-RUN MODE] 실제 변경하지 않음")
        for cafe_id in cafe_ids:
            print(f"  - {cafe_id}")
    else:
        deactivate_closed_cafes(cafe_ids, reason)
