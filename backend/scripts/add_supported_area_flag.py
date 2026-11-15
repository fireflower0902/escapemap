#!/usr/bin/env python3
"""전국 카페의 supported_area 플래그와 주소 기반 지역 분류를 보완합니다."""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings
from app.firestore_db import init_firestore, get_db

from app.areas import SEOUL_AREAS, resolve_cafe_area


def add_supported_area_flag(dry_run=True):
    """supported_area 플래그 추가"""
    init_firestore(settings.firebase_credentials_path)
    db = get_db()

    print("=" * 100)
    print("supported_area 플래그 추가")
    print(f"모드: {'DRY-RUN' if dry_run else 'ACTUAL'}")
    print("=" * 100)

    all_cafes = list(db.collection("cafes").stream())
    seoul_count = 0
    non_seoul_count = 0

    for cafe_doc in all_cafes:
        cafe_id = cafe_doc.id
        cafe_data = cafe_doc.to_dict()
        cafe_name = cafe_data.get("name", "Unknown")
        area = resolve_cafe_area(cafe_data.get("area"), cafe_data.get("address"))

        is_supported = True
        status = "✅" if is_supported else "⚠️"

        if area in SEOUL_AREAS:
            seoul_count += 1
        else:
            non_seoul_count += 1

        print(f"{status} {cafe_name:30} ({area:10}) → supported_area={is_supported}")

        if not dry_run:
            db.collection("cafes").document(cafe_id).set(
                {"supported_area": is_supported, "area": area},
                merge=True
            )

    print("\n" + "=" * 100)
    print(f"서울 지역 카페 (supported_area=true): {seoul_count}개")
    print(f"서울 외 카페 (supported_area=true): {non_seoul_count}개")
    print(f"합계: {seoul_count + non_seoul_count}개")
    print("=" * 100)

    if dry_run:
        print("\n[DRY-RUN] 실제로 업데이트하지 않았습니다.")
        print("실제 업데이트 하려면: --no-dry-run 플래그 사용")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-dry-run", action="store_true", help="실제로 업데이트 수행")
    args = parser.parse_args()

    add_supported_area_flag(dry_run=not args.no_dry_run)
