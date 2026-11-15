/**
 * /api/search — Firestore 직접 쿼리 + Vercel CDN 캐싱
 *
 * 동작 원리:
 *   1. 첫 번째 사용자 요청 → Firestore에서 직접 읽기 (cafes, themes, schedules 3회)
 *   2. Vercel CDN이 응답을 1시간 캐시 (s-maxage=3600)
 *   3. 이후 같은 (date, area) 요청은 Firestore 접근 없이 CDN 캐시로 응답
 *   4. 1시간 후 만료 → 다음 요청 시 자동 갱신 (stale-while-revalidate)
 *
 * 환경변수:
 *   FIREBASE_SERVICE_ACCOUNT_JSON — Firebase 서비스 계정 JSON 전체 내용
 */
import { NextRequest, NextResponse } from "next/server";
import { usesSupabase, loadPostgresLiveData, assembleSearch } from "@/lib/supabase-server";
import { AREA_VALUES, areaMatches, resolveCafeArea } from "@/lib/areas";

const CACHE_HEADERS = {
  "Cache-Control": "public, s-maxage=30, stale-while-revalidate=30",
};

const VALID_AREAS = new Set(AREA_VALUES);

type ThemeDoc = {
  id: string; cafe_id: string; name: string;
  difficulty?: number; duration_min?: number; poster_url?: string;
};
type CafeDoc = {
  id: string; name: string; branch_name?: string;
  address: string; website_url?: string; area?: string;
};

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const date = searchParams.get("date") ?? "";
  const area = searchParams.get("area")?.trim().toLowerCase() || "all";
  if (!VALID_AREAS.has(area)) {
    return NextResponse.json({ error: "지원하지 않는 지역 코드입니다." }, { status: 400 });
  }

  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || !Number.isFinite(Date.parse(date)) || new Date(date).toISOString().slice(0,10) !== date) {
    return NextResponse.json({ error: "날짜는 YYYY-MM-DD 형식이어야 합니다." }, { status: 400 });
  }
  try {
    if (usesSupabase()) {
      const data = await loadPostgresLiveData(date, area, false);
      return NextResponse.json(assembleSearch(date, area, data), { headers: CACHE_HEADERS });
    }
    const {getDb}=await import("@/lib/firestore-server");
    const db = getDb();

    // 1. 카페 목록 (area 필터)
    // 과거 서울 전용 플래그나 etc 분류와 무관하게 주소로 전국 지역을 보완.
    const cafesQuery = db.collection("cafes").where("is_active", "==", true);
    const cafeDocs = await cafesQuery.get();
    const cafes = (cafeDocs.docs.map((d) => ({ id: d.id, ...d.data() })) as CafeDoc[]).filter(
      cafe => areaMatches(area, resolveCafeArea(cafe.area, cafe.address))
    ).sort(
      (a, b) => ((a.address ?? "") + (a.name ?? "")).localeCompare((b.address ?? "") + (b.name ?? ""))
    );

    const cafeIds = cafes.map((c) => c.id);
    if (cafeIds.length === 0) {
      return NextResponse.json({ date, area, cafes: [], total: 0 }, { headers: CACHE_HEADERS });
    }

    // 2. 테마 목록 (30개씩 배치 쿼리)
    const themesByCafe: Record<string, ThemeDoc[]> = {};
    for (let i = 0; i < cafeIds.length; i += 30) {
      const batch = cafeIds.slice(i, i + 30);
      const themeDocs = await db.collection("themes")
        .where("cafe_id", "in", batch)
        .where("is_active", "==", true)
        .get();
      for (const doc of themeDocs.docs) {
        const d = doc.data() as ThemeDoc;
        if (!themesByCafe[d.cafe_id]) themesByCafe[d.cafe_id] = [];
        themesByCafe[d.cafe_id].push({ ...d, id: doc.id });
      }
    }

    // 3. 날짜별 슬롯 — schedules/{date} 단일 문서 1회 read
    const slotsByTheme: Record<string, { time: string; status: string; booking_url: string | null }[]> = {};
    if (date) {
      const scheduleDoc = await db.collection("schedules").doc(date).get();
      if (scheduleDoc.exists) {
        const cafesData = ((scheduleDoc.data() ?? {}).cafes ?? {}) as Record<string, any>;
        const cafeIdSet = new Set(cafeIds);
        for (const [cid, cafeData] of Object.entries(cafesData)) {
          if (!cafeIdSet.has(cid)) continue;
          for (const [themeDocId, themeData] of Object.entries((cafeData as any).themes ?? {})) {
            slotsByTheme[themeDocId] = ((themeData as any).slots ?? []).map((s: any) => ({
              time: s.time,
              status: s.status,
              booking_url: s.booking_url ?? null,
            }));
          }
        }
      }
    }

    // 4. 응답 조립
    const cafesOut = [];
    for (const cafe of cafes) {
      const cafeThemes = (themesByCafe[cafe.id] ?? []).sort((a, b) =>
        (a.name ?? "").localeCompare(b.name ?? "")
      );

      if (cafeThemes.length > 0) {
        cafesOut.push({
          id: cafe.id,
          name: cafe.name,
          branch_name: cafe.branch_name ?? null,
          address: cafe.address,
          website_url: cafe.website_url ?? null,
          crawled: true,
          themes: cafeThemes.map((theme) => ({
            id: theme.id,
            name: theme.name,
            difficulty: theme.difficulty ?? null,
            duration_min: theme.duration_min ?? null,
            poster_url: theme.poster_url ?? null,
            slots: (slotsByTheme[theme.id] ?? []).sort((a, b) => a.time.localeCompare(b.time)),
          })),
        });
      } else if (cafe.website_url) {
        cafesOut.push({
          id: cafe.id,
          name: cafe.name,
          branch_name: cafe.branch_name ?? null,
          address: cafe.address,
          website_url: cafe.website_url,
          crawled: false,
          themes: [],
        });
      }
    }

    return NextResponse.json(
      { date, area, cafes: cafesOut, total: cafesOut.length },
      { headers: CACHE_HEADERS }
    );
  } catch (err) {
    console.error("[/api/search] database query failed", {name:err instanceof Error?err.name:"Error",code:typeof err === "object" && err && "code" in err ? String(err.code) : "unknown"});
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
