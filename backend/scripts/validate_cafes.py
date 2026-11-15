#!/usr/bin/env python3
"""카페 유효성 검증 - 폐업/변경 여부 확인"""
import sys
from pathlib import Path
import json

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings
from app.firestore_db import init_firestore, get_db

SEOUL_AREAS = {
    "gangnam": "강남/서초",
    "hongdae": "마포/홍대",
    "sinchon": "서대문/신촌",
    "konkuk": "광진/건대",
    "jamsil": "송파/강동/잠실",
    "itaewon": "용산/이태원",
    "myeongdong": "중구/종로/명동",
    "daehakro": "종로/대학로",
    "sinlim": "관악/신림",
}

def validate_cafes():
    """문제가 있을 것 같은 카페들 리스트업"""
    init_firestore(settings.firebase_credentials_path)
    db = get_db()

    print("=" * 100)
    print("카페 유효성 검증 리포트")
    print("=" * 100)

    suspicious_cafes = {
        "no_themes": [],        # 테마 0개
        "no_crawled": [],       # crawled=False
        "kakao_map_only": [],   # website_url이 카카오맵만
    }

    for area_code in SEOUL_AREAS.keys():
        cafes_q = db.collection("cafes").where("area", "==", area_code)
        cafes = [{"id": d.id, **d.to_dict()} for d in cafes_q.stream()]

        for cafe in cafes:
            cafe_id = cafe["id"]
            name = cafe.get("name", "N/A")
            website = cafe.get("website_url", "")
            crawled = cafe.get("crawled", False)

            # 테마 개수
            themes_q = db.collection("themes").where("cafe_id", "==", cafe_id)
            theme_count = len(list(themes_q.stream()))

            # 1. 테마 0개
            if theme_count == 0:
                suspicious_cafes["no_themes"].append({
                    "cafe_id": cafe_id,
                    "name": name,
                    "area": area_code,
                    "website": website,
                    "crawled": crawled,
                })

            # 2. crawled=False
            if crawled is False:
                suspicious_cafes["no_crawled"].append({
                    "cafe_id": cafe_id,
                    "name": name,
                    "area": area_code,
                    "website": website,
                })

            # 3. website_url이 카카오맵만
            if website and "place.map.kakao.com" in website and theme_count == 0:
                suspicious_cafes["kakao_map_only"].append({
                    "cafe_id": cafe_id,
                    "name": name,
                    "area": area_code,
                    "website": website,
                })

    # 출력
    print("\n[1] 테마가 0개인 카페 (폐업 가능성 높음)")
    print("-" * 100)
    for cafe in suspicious_cafes["no_themes"]:
        print(f"  • {cafe['name']:30} ({cafe['area']}) | 🔗 {cafe['website'][:50]}")
    print(f"합계: {len(suspicious_cafes['no_themes'])}개\n")

    print("[2] crawled=False인 카페 (크롤링 실패)")
    print("-" * 100)
    for cafe in suspicious_cafes["no_crawled"]:
        print(f"  • {cafe['name']:30} ({cafe['area']}) | 🔗 {cafe['website'][:50]}")
    print(f"합계: {len(suspicious_cafes['no_crawled'])}개\n")

    print("[3] 카카오맵 링크만 있는 카페 (폐업 가능성)")
    print("-" * 100)
    for cafe in suspicious_cafes["kakao_map_only"]:
        print(f"  • {cafe['name']:30} ({cafe['area']}) | 🔗 {cafe['website']}")
    print(f"합계: {len(suspicious_cafes['kakao_map_only'])}개\n")

    # JSON 저장
    with open("suspicious_cafes.json", "w", encoding="utf-8") as f:
        json.dump(suspicious_cafes, f, ensure_ascii=False, indent=2)
    print(f"✅ JSON 저장: suspicious_cafes.json")

    print("\n" + "=" * 100)
    print("검증 방법:")
    print("  1. 각 카페의 website_url로 접속")
    print("  2. 아직 운영 중인지 확인 (예약 화면, SNS, 전화)")
    print("  3. 테마 목록이 변경되었는지 확인")
    print("  4. agent-browser로 자동화 검증 가능")
    print("=" * 100)

if __name__ == "__main__":
    validate_cafes()
