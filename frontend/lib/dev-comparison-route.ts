import { NextRequest, NextResponse } from "next/server";
import { readFile, writeFile, mkdir } from "node:fs/promises";
import path from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { usesSupabase, loadPostgresCatalog } from "@/lib/supabase-server";
import { getDb } from "@/lib/firestore-server";
export const dynamic = "force-dynamic";
export const runtime = "nodejs";
const directory = path.resolve(process.cwd(), "../backend/reports/competitors");
const sources = ["bbabang", "roomescape"];
async function read(name: string) { try { return JSON.parse(await readFile(path.join(directory, name + ".json"), "utf8")); } catch { return null; } }
export async function GET(request: NextRequest) {
  if (process.env.NODE_ENV !== "development") return new NextResponse(null, { status: 404 });
  const download = request.nextUrl.searchParams.get("download");
  if (download) {
    const allowed = ["README.md", "official-verification.md", "crawler-recovery-2026-11-15.md", "research-index.md", "ours-cafes.md", "ours-themes.md", "bbabang-cafes.md", "bbabang-themes.md", "roomescape-cafes.md", "roomescape-themes.md", "check-cafes.md", "check-themes.md"];
    if (!allowed.includes(download)) return new NextResponse(null, { status: 404 });
    try { return new NextResponse(await readFile(path.join(directory, download), "utf8"), { headers: { "Content-Type": "text/markdown; charset=utf-8", "Content-Disposition": `attachment; filename="${download}"` } }); }
    catch { return new NextResponse(null, { status: 404 }); }
  }
  await mkdir(directory, { recursive: true });
  let ours = await read("ours");
  let refreshWarning: string | null = null;
  if (!ours || request.nextUrl.searchParams.get("refresh") === "1") {
    try {
      if (usesSupabase()) {
        const catalog=await loadPostgresCatalog();
        ours={source:"ours",collected_at:new Date().toISOString(),...catalog};
      } else {
      const db = getDb();
      const [cafes, themes] = await Promise.all([db.collection("cafes").get(), db.collection("themes").get()]);
      ours = { source: "ours", collected_at: new Date().toISOString(), cafes: cafes.docs.map(d => ({ ...d.data(), id: d.id })), themes: themes.docs.map(d => ({ ...d.data(), id: d.id })) };
      }
      await writeFile(path.join(directory, "ours.json"), JSON.stringify(ours, null, 2));
    } catch (failure) {
      refreshWarning = `DB 목록 갱신 실패 (${failure instanceof Error ? failure.name : "Error"}); 이전 목록을 표시합니다.`;
      if (!ours) return NextResponse.json({ error: "우리 DB 목록을 읽지 못했습니다." }, { status: 503 });
    }
  }
  const comparisons = await read("comparison");
  return NextResponse.json({ ours, warnings: refreshWarning ? [refreshWarning] : [], sources: await Promise.all(sources.map(read)), comparison: comparisons, verification: await read("verified-additions") }, { headers: { "Cache-Control": "no-store" } });
}
export async function POST(request: NextRequest) {
  if (process.env.NODE_ENV !== "development") return new NextResponse(null, { status: 404 });
  const origin = request.headers.get("origin");
  if (origin && new URL(origin).host !== request.headers.get("host")) return NextResponse.json({ error: "다른 출처의 요청입니다." }, { status: 403 });
  let data;
  try { data = await request.json(); } catch { return NextResponse.json({ error: "JSON 형식을 확인하세요." }, { status: 400 }); }
  if (data?.action === "compare") {
    const backend = path.resolve(directory, "../..");
    try {
      await promisify(execFile)(path.join(backend, ".venv/bin/python"), [path.join(backend, "scripts/compare_competitors.py")], { cwd: backend, timeout: 120000, maxBuffer: 100000 });
      return NextResponse.json({ compared: true });
    } catch { return NextResponse.json({ error: "비교 실행에 실패했습니다. 수집 파일을 확인하세요." }, { status: 500 }); }
  }
  if (!data || !sources.includes(data.source) || !Array.isArray(data.cafes) || !Array.isArray(data.themes)) return NextResponse.json({ error: "source, cafes, themes가 필요합니다." }, { status: 400 });
  const allowed = ["id", "name", "cafe_name", "cafe_id", "address", "source_region", "source_url", "region", "active", "scope", "requested_region"];
  const clean = (rows: unknown[]) => rows.filter(row => row && typeof row === "object").map(row => Object.fromEntries(allowed.filter(key => key in (row as object)).map(key => [key, String((row as Record<string, unknown>)[key]).slice(0, 2000)])));
  const result = { source: data.source, collected_at: new Date().toISOString(), cafes: clean(data.cafes), themes: clean(data.themes), coverage: data.coverage ?? { complete: false } };
  await mkdir(directory, { recursive: true });
  await writeFile(path.join(directory, data.source + ".json"), JSON.stringify(result, null, 2));
  return NextResponse.json({ saved: true, cafes: result.cafes.length, themes: result.themes.length });
}
