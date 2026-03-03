"""
카페 관련 API 엔드포인트.
데이터 소스: Firebase Firestore (cafes / themes / schedules 컬렉션)

필요한 Firestore 복합 인덱스:
  - cafes: (area ASC, is_active ASC)  ← Firebase Console에서 자동 생성됨
"""
import asyncio
from datetime import date as Date

from fastapi import APIRouter, HTTPException, Query

from app.firestore_db import get_db, AREA_ADDRESS_MAP

router = APIRouter()


# ── 내부 헬퍼 ────────────────────────────────────────────────────────────────


def _get_cafes_sync(db, area: str | None) -> list[dict]:
    """Firestore에서 카페 목록을 가져옵니다 (동기)."""
    q = db.collection("cafes").where("is_active", "==", True)
    if area and area in AREA_ADDRESS_MAP:
        q = q.where("area", "==", area)
    docs = list(q.stream())
    return sorted(
        [{"id": d.id, **d.to_dict()} for d in docs],
        key=lambda c: (c.get("address") or "", c.get("name") or ""),
    )


def _get_themes_by_cafe_sync(db, cafe_ids: list[str]) -> dict[str, list[dict]]:
    """cafe_ids 에 해당하는 테마를 cafe_id 기준으로 그룹화하여 반환합니다 (동기)."""
    themes_by_cafe: dict[str, list[dict]] = {}
    for i in range(0, len(cafe_ids), 30):
        batch = cafe_ids[i : i + 30]
        for doc in (
            db.collection("themes")
            .where("cafe_id", "in", batch)
            .where("is_active", "==", True)
            .stream()
        ):
            d = doc.to_dict()
            themes_by_cafe.setdefault(d["cafe_id"], []).append({"id": doc.id, **d})
    return themes_by_cafe


def _get_slots_for_date_sync(db, date_str: str, cafe_ids: list[str]) -> dict[str, list[dict]]:
    """특정 날짜의 슬롯을 theme_doc_id 기준으로 그룹화하여 반환합니다 (동기).

    schedules/{date} 단일 문서를 1회 read 후 Python에서 cafe_ids 필터링.
    """
    try:
        doc = db.collection("schedules").document(date_str).get()
        if not doc.exists:
            return {}
        cafes_data = (doc.to_dict() or {}).get("cafes", {})
    except Exception:
        return {}

    cafe_ids_set = set(cafe_ids)
    slots_by_theme: dict[str, list[dict]] = {}

    for cid, cafe_data in cafes_data.items():
        if cid not in cafe_ids_set:
            continue
        for theme_doc_id, theme_data in (cafe_data.get("themes") or {}).items():
            slots_by_theme[theme_doc_id] = [
                {
                    "time_slot":   s["time"],
                    "status":      s["status"],
                    "booking_url": s.get("booking_url"),
                }
                for s in (theme_data.get("slots") or [])
            ]

    return slots_by_theme


# ── 엔드포인트 ───────────────────────────────────────────────────────────────


@router.get("/cafes")
async def get_cafes(
    area: str | None = Query(None, description="지역 코드 (예: gangnam, hongdae, busan)"),
):
    """
    지역 기준으로 방탈출 카페 목록을 반환합니다.

    예시:
      GET /api/v1/cafes
      GET /api/v1/cafes?area=gangnam
    """
    db = get_db()
    cafes = await asyncio.to_thread(_get_cafes_sync, db, area)
    return {"cafes": cafes, "total": len(cafes), "area": area}


@router.get("/search")
async def search(
    date: Date = Query(..., description="조회 날짜 (YYYY-MM-DD)"),
    area: str | None = Query(None, description="지역 코드"),
):
    """
    날짜 + 지역으로 카페·테마·예약 가능 시간대를 한 번에 반환합니다.
    프론트 검색 페이지가 이 엔드포인트를 호출합니다.

    예시:
      GET /api/v1/search?date=2026-03-15&area=gangnam
    """
    db = get_db()
    date_str = str(date)

    def _query():
        # 1. 카페 목록
        cafes = _get_cafes_sync(db, area)
        cafe_ids = [c["id"] for c in cafes]
        if not cafe_ids:
            return []

        # 2. 테마 목록 (cafe_id 기준 그룹화)
        themes_by_cafe = _get_themes_by_cafe_sync(db, cafe_ids)

        # 3. 해당 날짜 슬롯 (theme_doc_id 기준 그룹화)
        slots_by_theme = _get_slots_for_date_sync(db, date_str, cafe_ids)

        # 4. 응답 구조 조립
        cafes_out = []
        for cafe in cafes:
            cafe_themes = sorted(
                themes_by_cafe.get(cafe["id"], []),
                key=lambda t: t.get("name") or "",
            )

            if cafe_themes:
                themes_out = []
                for theme in cafe_themes:
                    slots = slots_by_theme.get(theme["id"], [])
                    slots_out = sorted(
                        [
                            {
                                "time":        s["time_slot"],
                                "status":      s["status"],
                                "booking_url": s.get("booking_url"),
                            }
                            for s in slots
                        ],
                        key=lambda x: x["time"],
                    )
                    themes_out.append({
                        "id":           theme["id"],
                        "name":         theme["name"],
                        "difficulty":   theme.get("difficulty"),
                        "duration_min": theme.get("duration_min"),
                        "poster_url":   theme.get("poster_url"),
                        "slots":        slots_out,
                    })
                cafes_out.append({
                    "id":          cafe["id"],
                    "name":        cafe.get("name"),
                    "branch_name": cafe.get("branch_name"),
                    "address":     cafe.get("address"),
                    "website_url": cafe.get("website_url"),
                    "crawled":     True,
                    "themes":      themes_out,
                })
            elif cafe.get("website_url"):
                # 아직 크롤링 안 된 카페 — 공식 사이트가 있는 경우만 포함
                cafes_out.append({
                    "id":          cafe["id"],
                    "name":        cafe.get("name"),
                    "branch_name": cafe.get("branch_name"),
                    "address":     cafe.get("address"),
                    "website_url": cafe.get("website_url"),
                    "crawled":     False,
                    "themes":      [],
                })

        return cafes_out

    cafes_out = await asyncio.to_thread(_query)
    return {
        "date":  date_str,
        "area":  area,
        "cafes": cafes_out,
        "total": len(cafes_out),
    }


@router.get("/cafes/{cafe_id}")
async def get_cafe_detail(cafe_id: str):
    """특정 카페의 상세 정보를 반환합니다."""
    db = get_db()

    def _query():
        doc = db.collection("cafes").document(cafe_id).get()
        return {"id": doc.id, **doc.to_dict()} if doc.exists else None

    cafe = await asyncio.to_thread(_query)
    if not cafe:
        raise HTTPException(status_code=404, detail="카페를 찾을 수 없습니다.")
    return cafe


@router.get("/cafes/{cafe_id}/themes")
async def get_cafe_themes(cafe_id: str):
    """특정 카페의 테마 목록을 반환합니다."""
    db = get_db()

    def _query():
        docs = list(
            db.collection("themes")
            .where("cafe_id", "==", cafe_id)
            .where("is_active", "==", True)
            .stream()
        )
        return [{"id": d.id, **d.to_dict()} for d in docs]

    themes = await asyncio.to_thread(_query)
    return {"cafe_id": cafe_id, "themes": themes}
