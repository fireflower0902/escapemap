import { NextRequest, NextResponse } from "next/server";
import { getCrawlerJob, startCrawlerJob } from "@/lib/crawler-dashboard-jobs";
import { getDashboardData } from "@/lib/crawler-dashboard-server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  if (process.env.NODE_ENV !== "development") return new NextResponse(null, { status: 404 });
  const params = request.nextUrl.searchParams;
  const date = params.get("date") || new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Seoul" }).format(new Date());
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || !Number.isFinite(Date.parse(date)) || new Date(date).toISOString().slice(0, 10) !== date) {
    return NextResponse.json({ error: "날짜는 YYYY-MM-DD 형식이어야 합니다." }, { status: 400 });
  }
  try {
    const data = await getDashboardData(date, params.get("refresh") === "1");
    return NextResponse.json({ ...data, job: getCrawlerJob() }, { headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ error: "현황판을 불러오지 못했습니다. 개발 서버 로그를 확인하세요." }, { status: 500 });
  }
}

export async function POST(request: NextRequest) {
  if (process.env.NODE_ENV !== "development") return new NextResponse(null, { status: 404 });
  const origin = request.headers.get("origin");
  if (origin) {
    try {
      if (new URL(origin).host !== request.headers.get("host")) {
        return NextResponse.json({ error: "현황판과 같은 주소에서만 검증을 실행할 수 있습니다." }, { status: 403 });
      }
    } catch {
      return NextResponse.json({ error: "요청 출처가 올바르지 않습니다." }, { status: 403 });
    }
  }
  if (getCrawlerJob()?.status === "running") {
    return NextResponse.json({ error: "이미 검증 중입니다. 현재 실행이 끝난 뒤 다시 시작하세요." }, { status: 409 });
  }
  let body;
  try { body = await request.json(); }
  catch { return NextResponse.json({ error: "요청 형식을 확인하세요." }, { status: 400 }); }
  if (!body || typeof body !== "object" || typeof body.script !== "string") {
    return NextResponse.json({ error: "실행할 크롤러를 지정하세요." }, { status: 400 });
  }
  const data = await getDashboardData(new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Seoul" }).format(new Date()), false);
  if (body.script !== "all" && !data.runs.some(run => run.id === body.script)) {
    return NextResponse.json({ error: "등록된 크롤러만 실행할 수 있습니다." }, { status: 400 });
  }
  try {
    return NextResponse.json({ job: startCrawlerJob(body.script, body.allBranches === true) }, { status: 202 });
  } catch {
    return NextResponse.json({ error: "이미 검증 중입니다. 현재 실행이 끝난 뒤 다시 시작하세요." }, { status: 409 });
  }
}
