import { execFile } from "node:child_process";
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { promisify } from "node:util";
import { usesSupabase, loadPostgresLiveData } from "@/lib/supabase-server";
import { getDb } from "@/lib/firestore-server";
import { resolveCafeArea } from "@/lib/areas";
import type { CatalogEntry, CrawlerCheck, DashboardPayload } from "@/lib/crawler-dashboard-types";

const backendDir = path.resolve(process.cwd(), "../backend");
const reportDir = path.join(backendDir, "reports/crawlers");
const execute = promisify(execFile);
let catalogCache: { at: number; entries: CatalogEntry[] } | null = null;
type Doc = Record<string, any>;
type LiveData = { cafes: Doc[]; themes: Doc[]; schedule: Doc; fetchedAt: string };
const liveCache = new Map<string, { at: number; data: LiveData }>();
let liveReadQuotaUntil = 0;

async function loadCatalog(): Promise<CatalogEntry[]> {
  if (catalogCache && Date.now() - catalogCache.at < 60_000) return catalogCache.entries;
  try {
    const { stdout } = await execute(path.join(backendDir, ".venv/bin/python"),
      [path.join(backendDir, "scripts/crawler_catalog.py"), "--stdout"], { timeout: 15_000, maxBuffer: 2_000_000 });
    const entries = JSON.parse(stdout) as CatalogEntry[];
    catalogCache = { at: Date.now(), entries };
    return entries;
  } catch {
    return JSON.parse(await readFile(path.join(reportDir, "catalog.json"), "utf8"));
  }
}

async function reportFiles(directory: string, depth = 0): Promise<string[]> {
  const files = await readdir(directory, { withFileTypes: true }).catch(() => []);
  const groups = await Promise.all(files.map(async file => {
    const full = path.join(directory, file.name);
    if (file.isDirectory() && depth < 4) return reportFiles(full, depth + 1);
    return file.isFile() && file.name.endsWith(".json") && file.name !== "catalog.json" ? [full] : [];
  }));
  return groups.flat();
}

async function loadChecks(): Promise<Map<string, CrawlerCheck[]>> {
  const history = new Map<string, CrawlerCheck[]>();
  const contents = await Promise.all((await reportFiles(reportDir)).map(async file => {
    try { return { file, value: JSON.parse(await readFile(file, "utf8")) }; }
    catch { return null; } // 실행 중인 파일은 다음 새로고침 때 다시 읽습니다.
  }));
  for (const content of contents) {
    if (!content) continue;
    for (const item of Array.isArray(content.value) ? content.value : [content.value]) {
      if (!item || !/^sync_[a-z0-9_]+_db$/.test(item.script ?? "") || !item.checked_at) continue;
      const at = Date.parse(item.checked_at);
      if (!Number.isFinite(at)) continue;
      const items = history.get(item.script) ?? [];
      if (items.some(previous => previous.checked_at === item.checked_at)) continue;
      items.push({
        ...item, themes_fetched: item.themes_fetched ?? 0, slots: item.slots ?? 0,
        cafes_with_slots: item.cafes_with_slots ?? 0, scope: item.scope ?? "실행 실패 / 범위 미확인",
        dates: item.dates ?? [], statuses: item.statuses ?? {}, issues: item.issues ?? [],
        log_errors: item.log_errors ?? [], source: path.relative(reportDir, content.file),
      });
      history.set(item.script, items);
    }
  }
  for (const items of history.values()) items.sort((a, b) => Date.parse(b.checked_at) - Date.parse(a.checked_at));
  return history;
}

async function loadCafeDirectory(): Promise<Doc[]> {
  try {
    const directory = JSON.parse(await readFile(path.join(backendDir, "data/cafe-directory.json"), "utf8"));
    return Array.isArray(directory.cafes) ? directory.cafes.filter((cafe: Doc) => cafe.id && cafe.name && cafe.address) : [];
  } catch { return []; }
}

async function loadLiveData(date: string, force: boolean): Promise<LiveData> {
  const cached = liveCache.get(date);
  if (!force && cached && Date.now() - cached.at < 300_000) return cached.data;
  if (usesSupabase()) {
    const data = await loadPostgresLiveData(date);
    if (liveCache.size >= 6) liveCache.delete(liveCache.keys().next().value!);
    liveCache.set(date, { at: Date.now(), data });
    return data;
  }
  if (Date.now() < liveReadQuotaUntil) throw Object.assign(new Error("Firestore read quota exceeded"), { code: 8 });
  const db = getDb();
  const [cafes, themes, schedule] = await Promise.all([
    db.collection("cafes").get(),
    db.collection("themes").where("is_active", "==", true).get(),
    db.collection("schedules").doc(date).get(),
  ]).catch(error => {
    if (error?.code === 8 || /quota exceeded/i.test(error?.message ?? "")) liveReadQuotaUntil = Date.now() + 60_000;
    throw error;
  });
  const data = {
    cafes: cafes.docs.map(doc => ({ ...doc.data(), id: doc.id })),
    themes: themes.docs.map(doc => ({ ...doc.data(), id: doc.id })),
    schedule: schedule.data()?.cafes ?? {}, fetchedAt: new Date().toISOString(),
  };
  if (liveCache.size >= 6) liveCache.delete(liveCache.keys().next().value!);
  liveCache.set(date, { at: Date.now(), data });
  return data;
}

function selectedIds(entry: CatalogEntry, check: CrawlerCheck | null): string[] {
  if (!check) return [];
  if (check.requested_cafe_ids?.length) return check.requested_cafe_ids;
  if (check.per_cafe && Object.keys(check.per_cafe).length) return Object.keys(check.per_cafe);
  if (check.scope.startsWith("all configured")) return entry.cafe_ids;
  const ids = new Set<string>();
  for (const [key, value] of Object.entries(check.selected ?? {})) {
    if (!Array.isArray(value)) continue;
    for (const item of value) {
      if (typeof item === "string") {
        for (const id of entry.selections?.[key]?.[item] ?? []) ids.add(id);
      } else if (item?.cafe_id) ids.add(String(item.cafe_id));
      else if (item?.shop_map) for (const id of Object.values(item.shop_map)) ids.add(String(id));
    }
  }
  return ids.size ? [...ids] : entry.cafe_ids.length === 1 && check.scope.startsWith("first configured") ? entry.cafe_ids : [];
}

function timestamp(value: any): string | null {
  if (!value) return null;
  if (typeof value.toDate === "function") return value.toDate().toISOString();
  const text = String(value).replace(" ", "T");
  return /(?:Z|[+-]\d{2}:\d{2})$/.test(text) ? text : text + "+09:00";
}

export async function getDashboardData(date: string, force: boolean): Promise<DashboardPayload> {
  const [catalogResult, checksResult, liveResult, directoryResult] = await Promise.allSettled([
    loadCatalog(), loadChecks(), loadLiveData(date, force), loadCafeDirectory(),
  ]);
  const warnings: string[] = [];
  const catalog = catalogResult.status === "fulfilled" ? catalogResult.value : [];
  const checks = checksResult.status === "fulfilled" ? checksResult.value : new Map<string, CrawlerCheck[]>();
  const live = liveResult.status === "fulfilled" ? liveResult.value : null;
  const directory = directoryResult.status === "fulfilled" ? directoryResult.value : [];
  if (!catalog.length) warnings.push("크롤러 목록을 불러오지 못했습니다. backend에서 crawler_catalog.py를 실행하세요.");
  if (checksResult.status === "rejected") warnings.push("검증 결과 파일을 읽지 못했습니다.");
  const quotaExceeded = liveResult.status === "rejected" && (liveResult.reason?.code === 8 || /quota exceeded/i.test(liveResult.reason?.message ?? ""));
  if (!live) warnings.push((quotaExceeded ? "Firestore 읽기 할당량을 초과했습니다. " : (usesSupabase() ? "Supabase 데이터를 불러오지 못했습니다. " : "Firestore 데이터를 불러오지 못했습니다. ")) + " 저장 수치는 미확인으로 표시합니다. 카페명·주소·지역은 최근 저장한 기본정보를 사용하며, 검증 기록은 로컬 결과입니다.");
  const runs = catalog.map(entry => {
    const latest = checks.get(entry.id)?.[0] ?? null;
    return { ...entry, latest, testedCafeIds: selectedIds(entry, latest) };
  });
  const cafeDocs = new Map<string, Doc>((live?.cafes ?? directory).map(cafe => [cafe.id, cafe]));
  const registered = new Set(cafeDocs.keys());
  const scriptsByCafe = new Map<string, typeof runs>();
  for (const run of runs) for (const id of run.cafe_ids) {
    const group = scriptsByCafe.get(id) ?? [];
    group.push(run); scriptsByCafe.set(id, group);
    if (!cafeDocs.has(id)) {
      const meta = run.cafes.find(cafe => cafe.cafe_id === id) ?? {};
      cafeDocs.set(id, { id, name: meta.name ?? meta.cafe_name ?? `카페 ${id}`,
        branch_name: meta.branch_name, address: meta.address, area: meta.area,
        website_url: run.urls[0] });
    }
  }
  const themesByCafe = new Map<string, Doc[]>();
  for (const theme of live?.themes ?? []) {
    const group = themesByCafe.get(theme.cafe_id) ?? [];
    group.push(theme); themesByCafe.set(theme.cafe_id, group);
  }
  const cafes = [...cafeDocs.values()].map(cafe => {
    const scripts = scriptsByCafe.get(cafe.id) ?? [];
    // 다른 지점의 새 실행으로 이전에 검증한 지점의 기록이 사라지지 않도록 이력을 조회.
    const scoped = scripts.flatMap(run => (checks.get(run.id) ?? [])
      .filter(check => selectedIds(run, check).includes(cafe.id)))
      .sort((a, b) => Date.parse(b.checked_at) - Date.parse(a.checked_at));
    const linked = scripts.filter(run => run.latest)
      .sort((a, b) => Date.parse(b.latest!.checked_at) - Date.parse(a.latest!.checked_at));
    const check = scoped[0] ?? linked[0]?.latest ?? null;
    const sourceRun = scripts.find(run => run.id === check?.script);
    const perCafe = check?.per_cafe?.[cafe.id];
    const singleCafe = check && sourceRun && selectedIds(sourceRun, check).length === 1 && scoped.length > 0;
    const stored = live?.schedule[cafe.id];
    const metaThemes = themesByCafe.get(cafe.id) ?? [];
    const scheduleThemes = Object.entries(stored?.themes ?? {}) as [string, Doc][];
    const allSlots = scheduleThemes.flatMap(([, theme]) => theme.slots ?? []);
    const inDatabase = live ? registered.has(cafe.id) : null;
    const cannotCrawl = cafe.not_crawlable === true || cafe.engine === "not_crawlable";
    return {
      id: cafe.id, name: cafe.name?.trim() || cafe.engine || `카페 ${cafe.id}`, branch: cafe.branch_name ?? "",
      address: cafe.address ?? "주소 미등록", area: resolveCafeArea(cafe.area, cafe.address),
      active: inDatabase ? cafe.is_active !== false : typeof cafe.is_active === "boolean" ? cafe.is_active : null, inDatabase,
      website: /^https?:\/\//.test(cafe.website_url ?? "") ? cafe.website_url : null,
      engine: cafe.engine ?? null,
      coverage: cannotCrawl ? "not_crawlable" as const : scripts.length ? "configured" as const : "unconfigured" as const,
      scriptIds: scripts.map(run => run.id), check, checkInScope: scoped.length > 0,
      themeCount: live ? metaThemes.length : null, slotCount: live ? allSlots.length : null,
      testThemeCount: perCafe?.themes ?? (singleCafe ? check!.themes_fetched : null),
      testSlotCount: perCafe?.slots ?? (singleCafe ? check!.slots : null),
      available: live ? allSlots.filter(slot => slot.status === "available").length : null,
      full: live ? allSlots.filter(slot => slot.status === "full").length : null,
      closed: live ? allSlots.filter(slot => slot.status === "closed").length : null,
      crawledAt: timestamp(stored?.crawled_at),
      themes: metaThemes.map(theme => {
        const slots = stored?.themes?.[theme.id]?.slots ?? [];
        return { id: theme.id, name: theme.name, slots: slots.length,
          available: slots.filter((slot: Doc) => slot.status === "available").length };
      }),
    };
  }).sort((a, b) => (a.name + a.branch).localeCompare(b.name + b.branch, "ko"));
  return { date, loadedAt: new Date().toISOString(), dataFetchedAt: live?.fetchedAt ?? null, warnings, cafes, runs };
}
