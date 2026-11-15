#!/usr/bin/env python3
"""서울 지역 카페 목록 추출 및 상태 정보 출력"""
import sys
from pathlib import Path
import json
from datetime import date

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

def list_seoul_cafes():
    """서울 지역 카페 목록 출력"""
    init_firestore(settings.firebase_credentials_path)
    db = get_db()

    print("=" * 100)
    print("서울 지역 카페 목록 (Firestore 기준)")
    print("=" * 100)

    total_cafes = 0
    area_summary = {}

    for area_code, area_name in sorted(SEOUL_AREAS.items()):
        cafes_q = db.collection("cafes").where("area", "==", area_code)
        cafes = sorted(
            [{"id": d.id, **d.to_dict()} for d in cafes_q.stream()],
            key=lambda c: c.get("name", "")
        )

        active_cafes = [c for c in cafes if c.get("is_active", True)]
        inactive_cafes = [c for c in cafes if not c.get("is_active", True)]

        area_summary[area_code] = {
            "name": area_name,
            "active": len(active_cafes),
            "inactive": len(inactive_cafes),
            "total": len(cafes),
        }

        total_cafes += len(cafes)

        print(f"\n[{area_code.upper():12}] {area_name:15} | 활성: {len(active_cafes):3} | 비활성: {len(inactive_cafes):3} | 합계: {len(cafes):3}")
        print("-" * 100)

        for cafe in active_cafes:
            cafe_id = cafe["id"]
            name = cafe.get("name", "N/A")
            branch = cafe.get("branch_name") or ""
            address = cafe.get("address", "")[:40]
            engine = cafe.get("engine", "")
            website = cafe.get("website_url", "")
            crawled = cafe.get("crawled", "N/A")

            # 해당 카페의 테마 개수
            themes_q = db.collection("themes").where("cafe_id", "==", cafe_id)
            theme_count = len(list(themes_q.stream()))

            # 오늘 스케줄 확인
            today = str(date.today())
            schedule_doc = db.collection("schedules").document(today).get()
            today_schedule = {}
            if schedule_doc.exists:
                schedule_data = schedule_doc.to_dict() or {}
                cafe_schedule = schedule_data.get("cafes", {}).get(cafe_id, {})
                today_schedule = cafe_schedule.get("themes", {})

            print(f"  • {name:20} {branch:15} | 테마: {theme_count:2} | 엔진: {(engine or ''):20} | {address}...")
            if website:
                print(f"     🔗 {website}")
            if crawled != "N/A":
                print(f"     ⏰ 최종 크롤: {crawled}")
            if today_schedule:
                print(f"     📅 오늘 스케줄: {len(today_schedule)}개 테마")

        if inactive_cafes:
            print(f"\n  [비활성 카페 {len(inactive_cafes)}개]")
            for cafe in inactive_cafes:
                name = cafe.get("name", "N/A")
                print(f"    ❌ {name}")

    print("\n" + "=" * 100)
    print("지역별 요약")
    print("=" * 100)
    for area_code in sorted(SEOUL_AREAS.keys()):
        s = area_summary[area_code]
        print(f"{s['name']:15} | 활성: {s['active']:3} | 비활성: {s['inactive']:3} | 합계: {s['total']:3}")

    total_active = sum(s["active"] for s in area_summary.values())
    total_inactive = sum(s["inactive"] for s in area_summary.values())
    print("-" * 100)
    print(f"{'TOTAL':15} | 활성: {total_active:3} | 비활성: {total_inactive:3} | 합계: {total_cafes:3}")
    print("=" * 100)

    # JSON 출력 (검증용)
    output = {
        "timestamp": str(date.today()),
        "total_cafes": total_cafes,
        "total_active": total_active,
        "total_inactive": total_inactive,
        "areas": area_summary,
    }

    with open("seoul_cafes_snapshot.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ JSON 출력: seoul_cafes_snapshot.json")

if __name__ == "__main__":
    list_seoul_cafes()
