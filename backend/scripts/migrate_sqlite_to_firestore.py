"""
SQLite(escape_aggregator.db) → Firebase Firestore 일회성 마이그레이션 스크립트.

마이그레이션 대상:
  - cafes      → Firestore /cafes/{cafe_id}
  - themes     → Firestore /themes/{theme_doc_id}
  - schedules  → Firestore /schedules/{date}
                   구조: { cafes: { cafe_id: { themes: { theme_doc_id: { slots: [...] } }, crawled_at } } }
                   (날짜 문서 1개에 모든 카페·테마·슬롯 포함 → 검색 시 read 1회)

실행:
  cd escape-aggregator/backend
  uv run python scripts/migrate_sqlite_to_firestore.py
  uv run python scripts/migrate_sqlite_to_firestore.py --dry-run   # 실제 업로드 없이 개수만 확인
"""

import argparse
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings
from app.firestore_db import init_firestore, address_to_area, _theme_doc_id

DB_PATH = BACKEND_DIR / "escape_aggregator.db"
BATCH_SIZE = 400  # Firestore 배치 최대 500, 여유 있게 400


def _batch_commit(db, batch, count: int, label: str) -> tuple:
    """배치가 BATCH_SIZE 에 도달하면 커밋하고 새 배치를 반환합니다."""
    if count > 0 and count % BATCH_SIZE == 0:
        batch.commit()
        print(f"  [{label}] {count}개 커밋 완료")
        return db.batch(), count
    return batch, count


def migrate_cafes(db, cur, dry_run: bool) -> dict[int | str, str]:
    """
    cafes 테이블을 Firestore /cafes/{cafe_id} 에 마이그레이션합니다.
    반환: SQLite cafe.id → area 코드 매핑 (themes 마이그레이션에 사용)
    """
    print("\n[ 1단계 ] 카페 마이그레이션...")
    cur.execute("SELECT * FROM cafe WHERE is_active = 1")
    rows = cur.fetchall()

    batch = db.batch() if not dry_run else None
    count = 0
    cafe_area_map: dict[str, str] = {}

    for row in rows:
        cafe_id   = row["id"]
        address   = row["address"] or ""
        area      = address_to_area(address)
        cafe_area_map[cafe_id] = area

        if not dry_run:
            doc_ref = db.collection("cafes").document(cafe_id)
            batch.set(doc_ref, {
                "name":        row["name"],
                "branch_name": row["branch_name"],
                "address":     address,
                "area":        area,
                "phone":       row["phone"],
                "website_url": row["website_url"],
                "engine":      row["engine"],
                "crawled":     bool(row["engine"]),
                "lat":         row["lat"],
                "lng":         row["lng"],
                "is_active":   bool(row["is_active"]),
            })
            count += 1
            batch, count = _batch_commit(db, batch, count, "cafes")

    if not dry_run and count % BATCH_SIZE != 0:
        batch.commit()

    print(f"  완료: 카페 {len(rows)}개 {'(dry-run)' if dry_run else '업로드'}")
    return cafe_area_map


def migrate_themes(db, cur, dry_run: bool) -> dict[int, str]:
    """
    themes 테이블을 Firestore /themes/{theme_doc_id} 에 마이그레이션합니다.
    반환: SQLite theme.id → Firestore theme_doc_id 매핑 (schedules 마이그레이션에 사용)
    """
    print("\n[ 2단계 ] 테마 마이그레이션...")
    cur.execute("SELECT * FROM theme WHERE is_active = 1")
    rows = cur.fetchall()

    batch = db.batch() if not dry_run else None
    count = 0
    theme_id_map: dict[int, str] = {}  # sqlite theme.id → firestore doc_id

    for row in rows:
        cafe_id    = row["cafe_id"]
        theme_name = row["name"]
        doc_id     = _theme_doc_id(cafe_id, theme_name)
        theme_id_map[row["id"]] = doc_id

        if not dry_run:
            doc_ref = db.collection("themes").document(doc_id)
            batch.set(doc_ref, {
                "cafe_id":      cafe_id,
                "name":         theme_name,
                "difficulty":   row["difficulty"],
                "duration_min": row["duration_min"],
                "poster_url":   row["poster_url"],
                "is_active":    bool(row["is_active"]),
            })
            count += 1
            batch, count = _batch_commit(db, batch, count, "themes")

    if not dry_run and count % BATCH_SIZE != 0:
        batch.commit()

    print(f"  완료: 테마 {len(rows)}개 {'(dry-run)' if dry_run else '업로드'}")
    return theme_id_map


def migrate_schedules(db, cur, theme_id_map: dict[int, str], dry_run: bool) -> None:
    """
    schedules 테이블에서 (theme_id, date, time_slot) 기준 최신 스냅샷만
    Firestore /schedules/{date} 에 마이그레이션합니다.

    새 스키마:
      schedules/{date} → {
        cafes: {
          cafe_id: {
            themes: { theme_doc_id: { slots: [{time, status, booking_url}] } },
            crawled_at: str
          }
        }
      }

    날짜 1개 = Firestore 문서 1개 → 검색 시 read 1회로 충분.
    """
    print("\n[ 3단계 ] 스케줄 마이그레이션 (새 스키마: 날짜별 단일 문서)...")

    cur.execute("""
        SELECT s.*
        FROM schedule s
        INNER JOIN (
            SELECT theme_id, date, time_slot, MAX(crawled_at) AS latest_at
            FROM schedule
            GROUP BY theme_id, date, time_slot
        ) latest
        ON s.theme_id = latest.theme_id
           AND s.date = latest.date
           AND s.time_slot = latest.time_slot
           AND s.crawled_at = latest.latest_at
    """)
    rows = cur.fetchall()
    print(f"  대상 레코드: {len(rows)}개")

    # 메모리에서 구조 조립: date → cafe_id → theme_doc_id → [slots]
    date_cafe_theme: dict[str, dict[str, dict[str, list]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))
    )
    skipped = 0

    for row in rows:
        sqlite_theme_id = row["theme_id"]
        theme_doc_id    = theme_id_map.get(sqlite_theme_id)
        if not theme_doc_id:
            skipped += 1
            continue

        date_str  = str(row["date"])
        time_slot = str(row["time_slot"])[:5]   # "HH:MM:SS" → "HH:MM"

        try:
            cafe_id = row["cafe_id"] or ""
        except (IndexError, KeyError):
            cafe_id = ""

        if not cafe_id and "__" in theme_doc_id:
            cafe_id = theme_doc_id.split("__")[0]

        date_cafe_theme[date_str][cafe_id][theme_doc_id].append({
            "time":        time_slot,
            "status":      row["status"],
            "booking_url": row["booking_url"],
        })

    print(f"  날짜 수: {len(date_cafe_theme)}개")

    if dry_run:
        total_writes = len(date_cafe_theme)
        print(f"  예상 writes: {total_writes}개 날짜 문서 (dry-run — 실제 업로드 없음)")
        print(f"  건너뜀: {skipped}개")
        return

    # Firestore batch write: 날짜 1개 = 문서 1개
    batch = db.batch()
    count = 0

    for date_str, cafes_data in date_cafe_theme.items():
        all_cafes_payload = {
            cafe_id: {
                "themes": {
                    theme_doc_id: {"slots": slots}
                    for theme_doc_id, slots in themes.items()
                },
                "crawled_at": datetime.now().isoformat(),
            }
            for cafe_id, themes in cafes_data.items()
        }
        doc_ref = db.collection("schedules").document(date_str)
        batch.set(doc_ref, {"cafes": all_cafes_payload}, merge=True)
        count += 1
        batch, count = _batch_commit(db, batch, count, "schedules")

    if count % BATCH_SIZE != 0:
        batch.commit()

    print(f"  완료: {count}개 날짜 문서 업로드, {skipped}개 건너뜀")


def main(dry_run: bool = False) -> None:
    print("=" * 60)
    print("SQLite → Firestore 마이그레이션 (새 스키마)")
    print(f"  DB 경로: {DB_PATH}")
    print(f"  Dry-run: {dry_run}")
    print("=" * 60)

    if not DB_PATH.exists():
        print(f"[ERROR] DB 파일을 찾을 수 없습니다: {DB_PATH}")
        sys.exit(1)

    if not dry_run:
        init_firestore(settings.firebase_credentials_path)
        from app.firestore_db import get_db
        db = get_db()
    else:
        db = None

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        migrate_cafes(db, cur, dry_run)
        theme_id_map = migrate_themes(db, cur, dry_run)
        migrate_schedules(db, cur, theme_id_map, dry_run)
    finally:
        conn.close()

    print("\n" + "=" * 60)
    print("마이그레이션 완료!" if not dry_run else "Dry-run 완료 (실제 업로드 없음)")
    print("=" * 60)
    print("\n다음 단계:")
    print("  1. Firebase Console → Firestore → 데이터 확인")
    print("  2. FastAPI 서버 재시작 후 GET /api/v1/search?date=YYYY-MM-DD&area=gangnam 테스트")
    if not dry_run:
        print("  3. (선택) Firebase Console에서 기존 schedules/{date}/slots 서브컬렉션 삭제")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SQLite → Firestore 마이그레이션")
    parser.add_argument("--dry-run", action="store_true", help="실제 업로드 없이 개수만 확인")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
