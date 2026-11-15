/** 서버 전용 PostgreSQL 조회. 비밀번호는 NEXT_PUBLIC 변수로 노출하지 않는다. */
import { Pool } from "pg";
import { SUPABASE_CA } from "@/lib/supabase-ca";
import { AREA_VALUES } from "@/lib/areas";
const shared = globalThis as typeof globalThis & { escapePostgresPoolV2?: Pool };
export function usesSupabase() { return process.env.CRAWL_STORAGE === "supabase"; }
function getPool() {
  if (process.env.CLOUDFLARE_DEPLOYMENT === "true") {
    // Workers sockets belong to one request; never reuse a global connection.
    return { async query(text:string, values?:unknown[]) {
      const {getCloudflareContext}=await import("@opennextjs/cloudflare");
      const bindings=getCloudflareContext().env as unknown as {HYPERDRIVE?:{connectionString:string}};
      const uri=bindings.HYPERDRIVE?.connectionString;
      if(!uri)throw new Error("Cloudflare Hyperdrive binding missing");
      // Hyperdrive provides the private transport and validates origin TLS.
      const pool=new Pool({connectionString:uri,max:1,connectionTimeoutMillis:10000,statement_timeout:10000});
      try{return await pool.query(text,values);}finally{await pool.end();}
    }};
  }
  if (!shared.escapePostgresPoolV2) {
    const uri = process.env.SUPABASE_DATABASE_URL;
    if (!uri) throw new Error("Supabase server configuration missing");
    const parsed = new URL(uri);
    for (const key of ["sslmode", "sslcert", "sslkey", "sslrootcert"]) parsed.searchParams.delete(key);
    shared.escapePostgresPoolV2 = new Pool({ connectionString: parsed.toString(), ssl: { rejectUnauthorized: true, ca: SUPABASE_CA }, max: 3,
      connectionTimeoutMillis: 10_000, idleTimeoutMillis: 20_000, statement_timeout: 10_000 });
    shared.escapePostgresPoolV2.on("error", () => console.error("PostgreSQL idle connection error"));
  }
  return shared.escapePostgresPoolV2;
}
export async function loadPostgresLiveData(date: string, area = "all", includeInactive = true) {
  if (!AREA_VALUES.includes(area)) throw new Error("Invalid region");
  const regions = area === "all" ? null : area === "seoul" ? ["gangnam","hongdae","sinchon","konkuk","jamsil","itaewon","myeongdong","daehakro","sinlim","seongsu","seoul_other"] : area === "chungnam" ? ["chungnam","cheonan"] : [area];
  const pool = getPool();
  const cafeRows = await pool.query("SELECT * FROM escape.cafes WHERE ($1::text[] IS NULL OR area=ANY($1)) AND ($2::boolean OR is_active=true) ORDER BY name,branch_name", [regions, includeInactive]);
  const cafes = cafeRows.rows.map(({ metadata, updated_at, ...row }) => ({ ...metadata, ...row }));
  const ids = cafes.map(cafe => cafe.id);
  const freshness = Math.max(1,Math.min(86400,Number(process.env.CRAWL_FRESHNESS_SECONDS) || 5400));
  const [themeRows, slotRows] = await Promise.all([
    pool.query("SELECT * FROM escape.themes WHERE cafe_id=ANY($1::text[]) AND is_active=true", [ids]),
    pool.query(`SELECT s.*, c.last_success_at FROM escape.reservation_slots s
      JOIN escape.cafe_date_checks c ON c.cafe_id=s.cafe_id AND c.service_date=s.service_date
      WHERE s.service_date=$1::date AND s.cafe_id=ANY($2::text[]) AND c.status='success'
      AND c.last_success_at >= now()-($3 * interval '1 second') ORDER BY s.start_minute`,[date, ids, freshness]),
  ]);
  const themes = themeRows.rows.map(({ metadata, updated_at, ...row }) => ({ ...metadata, ...row }));
  const schedule: Record<string, any> = {};
  for (const row of slotRows.rows) {
    const cafe = schedule[row.cafe_id] ??= { themes: {}, crawled_at: row.last_success_at.toISOString() };
    const theme = cafe.themes[row.theme_id] ??= { slots: [] };
    const past = new Date(row.starts_at).getTime() <= Date.now();
    theme.slots.push({ time: `${String(Math.floor(row.start_minute/60)).padStart(2,"0")}:${String(row.start_minute%60).padStart(2,"0")}`,
      status: past && row.status === "available" ? "closed" : row.status, booking_url: row.booking_url });
  }
  return { cafes, themes, schedule, fetchedAt: new Date().toISOString() };
}
export function assembleSearch(date: string, area: string, data: Awaited<ReturnType<typeof loadPostgresLiveData>>) {
  const byCafe = new Map<string, typeof data.themes>();
  for (const theme of data.themes) { const list = byCafe.get(theme.cafe_id) ?? []; list.push(theme); byCafe.set(theme.cafe_id,list); }
  const cafes = data.cafes.map(cafe => ({ id:cafe.id, name:cafe.name, branch_name:cafe.branch_name ?? null, address:cafe.address, area:cafe.area, crawled_at:data.schedule[cafe.id]?.crawled_at ?? null,
    website_url:cafe.website_url ?? null, crawled:!!data.schedule[cafe.id],
    themes:(byCafe.get(cafe.id) ?? []).sort((a,b)=>a.name.localeCompare(b.name,"ko")).map(theme=>({ id:theme.id,name:theme.name,
      genre:theme.genre ?? null,min_players:theme.min_players ?? null,max_players:theme.max_players ?? null,
      rating:typeof theme.rating === "number" ? theme.rating : null,difficulty:theme.difficulty ?? null,duration_min:theme.duration_min ?? null,poster_url:theme.poster_url ?? null,
      slots:data.schedule[cafe.id]?.themes[theme.id]?.slots ?? [] })) }));
  return {date,area,cafes,total:cafes.length};
}

export async function loadPostgresCatalog() {
  const pool=getPool();
  const [cafes,themes]=await Promise.all([pool.query("SELECT * FROM escape.cafes"),pool.query("SELECT * FROM escape.themes")]);
  const merge=({metadata,updated_at,...row}:Record<string,any>)=>({...metadata,...row});
  return {cafes:cafes.rows.map(merge),themes:themes.rows.map(merge)};
}
