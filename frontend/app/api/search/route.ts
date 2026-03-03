/**
 * /api/search — Vercel CDN 캐싱 레이어
 *
 * 동작 원리:
 *   1. 첫 번째 사용자 요청 → FastAPI 백엔드에서 Firestore 데이터 읽기
 *   2. Vercel CDN이 응답을 1시간 캐시 (s-maxage=3600)
 *   3. 이후 같은 (date, area) 요청은 Firebase 접근 없이 CDN 캐시로 응답
 *   4. 1시간 후 만료 → 다음 요청 시 자동 갱신 (stale-while-revalidate)
 *
 * 환경변수:
 *   BACKEND_URL  — FastAPI 서버 주소 (기본값: http://localhost:8000)
 */
import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const date = searchParams.get("date") ?? "";
  const area = searchParams.get("area") ?? "";

  const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";

  try {
    const res = await fetch(
      `${backendUrl}/api/v1/search?date=${date}&area=${area}`,
      { cache: "no-store" }  // 백엔드 호출은 캐시 안 함 (CDN 캐시가 담당)
    );
    if (!res.ok) {
      return NextResponse.json(
        { error: `Backend error: ${res.status}` },
        { status: res.status }
      );
    }
    const data = await res.json();

    return NextResponse.json(data, {
      headers: {
        // Vercel CDN: 1시간 캐시, 만료 후 24시간은 stale 응답하며 백그라운드 갱신
        "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=86400",
      },
    });
  } catch {
    return NextResponse.json(
      { error: "Failed to fetch data from backend" },
      { status: 502 }
    );
  }
}
