"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Activity, ArrowDownToLine, ArrowUpRight, Check, ChevronLeft, ChevronRight, CircleHelp, Database, Globe2, Loader2, Play, RefreshCw, Search, ShieldCheck, Terminal, X } from "lucide-react";
import { AREAS, AREA_LABELS, areaMatches } from "@/lib/areas";
import type { CrawlerCheck, DashboardCafe, DashboardPayload, DashboardRun } from "@/lib/crawler-dashboard-types";
import styles from "./dashboard.module.css";

const REGIONS = ["all", "seoul", "gyeonggi", "incheon", "busan", "daegu", "gwangju", "daejeon", "ulsan", "sejong", "gangwon", "chungbuk", "chungnam", "jeonbuk", "jeonnam", "gyeongbuk", "gyeongnam", "jeju", "etc"];
const NUMBER = new Intl.NumberFormat("ko-KR");
const number = (value: number | null | undefined) => value == null ? "—" : NUMBER.format(value);
function dateTime(value?: string | null) {
  if (!value || !Number.isFinite(Date.parse(value))) return "기록 없음";
  return new Intl.DateTimeFormat("ko-KR", { timeZone: "Asia/Seoul", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false }).format(new Date(value));
}
const STATUS_LABELS: Record<string, string> = { smoke_pass: "검증 통과", needs_review: "확인 필요", error: "실행 오류", timeout: "시간 초과", untested: "미검증" };
function Badge({ status }: { status: string }) {
  return <span className={`${styles.badge} ${styles[status] ?? ""}`}><i />{STATUS_LABELS[status] ?? status}</span>;
}
function cafeStatus(cafe: DashboardCafe) { return cafe.automaticPaused ? "needs_review" : cafe.checkInScope ? cafe.check?.status ?? "untested" : "untested"; }
function CheckInfo({ check }: { check: CrawlerCheck }) {
  return <div className={styles.checkInfo}>
    <div className={styles.detailPair}><span>마지막 실행</span><strong>{dateTime(check.checked_at)} KST</strong></div>
    <div className={styles.detailPair}><span>테스트 전체 테마 / 시간대</span><strong>{number(check.themes_fetched)} / {number(check.slots)}</strong></div>
    <div className={styles.detailPair}><span>시간대가 수집된 지점</span><strong>{number(check.cafes_with_slots)}개</strong></div>
    <div className={styles.detailPair}><span>조회 날짜</span><strong>{check.dates.join(", ") || "결과 없음"}</strong></div>
    <p className={styles.helper}>범위: {check.scope}<br />이 수치는 해당 크롤러 실행 전체의 합계입니다.</p>
    {check.error && <pre className={styles.errorLog}>{check.error}</pre>}
    {check.issues.length + check.log_errors.length > 0 && <div className={styles.errorLog}>{[...check.issues, ...check.log_errors].map((issue, i) => <p key={i}>{issue}</p>)}</div>}
    <p className={styles.fileName}>{check.source}</p>
  </div>;
}

export default function CrawlerDashboard() {
  const [date, setDate] = useState(() => new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Seoul" }).format(new Date()));
  const [data, setData] = useState<DashboardPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [region, setRegion] = useState("all");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [activity, setActivity] = useState("active");
  const [tab, setTab] = useState<"cafes" | "runs">("cafes");
  const [page, setPage] = useState(0);
  const [automatic, setAutomatic] = useState(false);
  const [selected, setSelected] = useState<{ cafe?: DashboardCafe; run?: DashboardRun } | null>(null);
  const [allBranches, setAllBranches] = useState(false);
  const [starting, setStarting] = useState(false);
  const [copied, setCopied] = useState(false);
  const requestRef = useRef<AbortController | null>(null);
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const running = data?.job?.status === "running";

  const reload = useCallback(async (force = false, quiet = false) => {
    requestRef.current?.abort();
    const controller = new AbortController(); requestRef.current = controller;
    if (!quiet) setLoading(true);
    try {
      const response = await fetch(`/api/dev/crawlers?date=${date}${force ? "&refresh=1" : ""}`, { signal: controller.signal, cache: "no-store" });
      const body = await response.json().catch(() => ({ error: `HTTP ${response.status}` }));
      if (!response.ok) throw new Error(body.error ?? `HTTP ${response.status}`);
      if (!controller.signal.aborted) { setData(body); setError(null); }
    } catch (failure) {
      if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : "불러오기 실패");
    } finally { if (!controller.signal.aborted) setLoading(false); }
  }, [date]);

  useEffect(() => { setData(previous => previous?.date === date ? previous : null); reload(); return () => requestRef.current?.abort(); }, [reload, date]);
  useEffect(() => {
    if (!automatic && !running) return;
    const timer = setInterval(() => reload(false, true), running ? 5_000 : 60_000);
    return () => clearInterval(timer);
  }, [automatic, running, reload]);
  useEffect(() => setPage(0), [region, query, status, activity, tab]);
  useEffect(() => { if (tab === "runs" && ["missing", "unconfigured"].includes(status)) setStatus("all"); }, [tab, status]);
  useEffect(() => {
    if (!selected) return;
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden"; dialogRef.current?.focus();
    function keyboard(event: KeyboardEvent) {
      if (event.key === "Escape") setSelected(null);
      if (event.key === "Tab") {
        const elements = dialogRef.current?.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), input, select, [tabindex="0"]');
        if (!elements?.length) return;
        const first = elements[0], last = elements[elements.length - 1];
        if (event.shiftKey && (document.activeElement === first || document.activeElement === dialogRef.current)) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
    }
    document.addEventListener("keydown", keyboard);
    return () => { document.body.style.overflow = overflow; document.removeEventListener("keydown", keyboard); previous?.focus(); };
  }, [selected]);

  const activeCafes = useMemo(() => (data?.cafes ?? []).filter(cafe => activity === "all" || (activity === "active" ? cafe.active !== false : cafe.active === false)), [data, activity]);
  const regionCafes = useMemo(() => activeCafes.filter(cafe => areaMatches(region, cafe.area)), [activeCafes, region]);
  const filtered = useMemo(() => regionCafes.filter(cafe => {
    const text = `${cafe.name} ${cafe.branch} ${cafe.address} ${cafe.scriptIds.join(" ")}`.toLowerCase();
    if (!text.includes(query.trim().toLowerCase())) return false;
    if (status === "pass") return cafeStatus(cafe) === "smoke_pass";
    if (status === "attention") return ["needs_review", "error", "timeout"].includes(cafeStatus(cafe));
    if (status === "untested") return cafe.coverage === "configured" && cafeStatus(cafe) === "untested";
    if (status === "unconfigured") return cafe.coverage !== "configured";
    if (status === "missing") return cafe.inDatabase === false;
    return true;
  }), [regionCafes, query, status]);
  const runs = useMemo(() => (data?.runs ?? []).filter(run => {
    if (region !== "all" && !run.cafe_ids.some(id => regionCafes.some(cafe => cafe.id === id))) return false;
    if (!`${run.id} ${run.name} ${run.urls.join(" ")}`.toLowerCase().includes(query.trim().toLowerCase())) return false;
    const state = run.latest?.status ?? "untested";
    if (status === "pass") return state === "smoke_pass";
    if (status === "attention") return ["needs_review", "error", "timeout"].includes(state);
    if (status === "untested") return state === "untested";
    return status !== "unconfigured" && status !== "missing";
  }), [data, query, region, regionCafes, status]);
  const pageSize = 25, count = tab === "cafes" ? filtered.length : runs.length;
  const pageCount = Math.max(1, Math.ceil(count / pageSize));
  const safePage = Math.min(page, pageCount - 1);
  const stats = {
    total: regionCafes.length, configured: regionCafes.filter(cafe => cafe.coverage === "configured").length,
    themes: data?.dataFetchedAt ? regionCafes.reduce((sum, cafe) => sum + (cafe.themeCount ?? 0), 0) : null,
    slots: data?.dataFetchedAt ? regionCafes.reduce((sum, cafe) => sum + (cafe.slotCount ?? 0), 0) : null,
    available: data?.dataFetchedAt ? regionCafes.reduce((sum, cafe) => sum + (cafe.available ?? 0), 0) : null,
  };

  const metrics = tab === "cafes" ? [
    ["카페 / 지점", stats.total, "운영 목록 + 수집 설정"], ["크롤러 연결", stats.configured, "등록된 지점 매핑 기준"],
    ["저장된 테마", stats.themes, "활성 테마 메타데이터"], ["저장된 시간대", stats.slots, `${date} 예약 데이터`],
    ["예약 가능", stats.available, "저장된 available 상태"],
  ] : [
    ["크롤러", runs.length, "현재 필터에 해당하는 항목"],
    ["검증 통과", runs.filter(run => run.latest?.status === "smoke_pass").length, "조회·파싱·형식 검사 통과"],
    ["확인 필요", runs.filter(run => run.latest && run.latest.status !== "smoke_pass").length, "경고·오류·시간대 미확인"],
    ["테스트 테마", runs.reduce((sum, run) => sum + (run.latest?.themes_fetched ?? 0), 0), "최신 실행 결과 합계"],
    ["테스트 시간대", runs.reduce((sum, run) => sum + (run.latest?.slots ?? 0), 0), "DB에 저장하지 않은 실측 결과"],
  ];

  async function startCheck(script: string) {
    setStarting(true); setError(null);
    try {
      const response = await fetch("/api/dev/crawlers", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ script, allBranches: selected ? allBranches : false }) });
      const result = await response.json().catch(() => ({ error: `HTTP ${response.status}` }));
      if (!response.ok) throw new Error(result.error);
      setData(previous => previous ? { ...previous, job: result.job } : previous);
    } catch (failure) { setError(failure instanceof Error ? failure.message : "검증 시작 실패"); }
    finally { setStarting(false); }
  }
  function exportCsv() {
    const cell = (value: unknown) => {
      let text = value == null ? "" : String(value);
      if (/^[=+\-@\t\r]/.test(text)) text = "'" + text;
      return '"' + text.replaceAll('"', '""') + '"';
    };
    const rows = [["카페 ID", "카페명", "지점", "지역", "주소", "크롤러 연결", "검증 결과", "DB 등록", "저장 테마", "저장 시간대", "예약 가능", "테스트 테마", "테스트 시간대", "최근 수집", "크롤러"],
      ...filtered.map(cafe => [cafe.id, cafe.name, cafe.branch, AREA_LABELS[cafe.area], cafe.address, cafe.coverage,
        STATUS_LABELS[cafeStatus(cafe)], cafe.inDatabase == null ? "미확인" : cafe.inDatabase ? "등록" : "미등록", cafe.themeCount, cafe.slotCount, cafe.available, cafe.testThemeCount, cafe.testSlotCount, cafe.crawledAt, cafe.scriptIds.join(", ")])];
    const url = URL.createObjectURL(new Blob(["\uFEFF" + rows.map(row => row.map(cell).join(",")).join("\r\n")], { type: "text/csv;charset=utf-8" }));
    const a = document.createElement("a"); a.href = url; a.download = `escapemap-crawlers-${date}.csv`; a.click(); URL.revokeObjectURL(url);
  }
  const detailCafe = selected?.cafe ? data?.cafes.find(cafe => cafe.id === selected.cafe!.id) ?? selected.cafe : null;
  const detailRun = selected?.run ? data?.runs.find(run => run.id === selected.run!.id) ?? selected.run : detailCafe ? data?.runs.find(run => run.id === (detailCafe.check?.script ?? detailCafe.scriptIds[0])) : null;
  const detailCheck = detailCafe?.check ?? detailRun?.latest;
  const command = detailRun ? `uv run python scripts/check_crawlers.py ${detailRun.id.replace(/^sync_|_db$/g, "")} --days 1${allBranches ? " --all-branches --timeout 240" : ""}` : "";

  return <div className={styles.dashboard}>
    <div className={styles.workspace}>
      <div className={styles.masthead}>
        <div><div className={styles.eyebrow}><span className={styles.signal} /> ESCAPEMAP / DEVELOPMENT</div><h1>크롤링 현황판<span>전국 수집 상태를 한눈에.</span></h1></div>
        <div className={styles.headActions}><span className={styles.readonly}><ShieldCheck size={14} /> 운영 DB 읽기 전용</span><a href="/dev/comparison">경쟁사 비교 <ArrowUpRight size={14} /></a><a href="/search?area=all">서비스 보기 <ArrowUpRight size={14} /></a></div>
      </div>
      <div className={styles.topbar}>
        <div className={styles.dateControl}><Database size={16} /><label htmlFor="snapshot-date">예약 데이터 날짜</label><input id="snapshot-date" type="date" value={date} onChange={event => { if (event.target.value) setDate(event.target.value); }} /></div>
        <div className={styles.refreshControls}><label className={styles.autoLabel}><input type="checkbox" checked={automatic} onChange={event => setAutomatic(event.target.checked)} /> 1분마다 확인</label><button onClick={() => reload(true)} disabled={loading}><RefreshCw size={15} className={loading ? styles.spin : ""} /> 새로고침</button></div>
      </div>
      {error && <div className={styles.notice} role="alert">{error}<button onClick={() => reload()}>다시 불러오기</button></div>}
      {data?.warnings.map(warning => <div className={styles.notice} key={warning}>{warning}</div>)}
      <div className={styles.metricStrip}>
        {metrics.map(([label, value, note], i) => <div className={styles.metric} key={String(label)}><span>{label}</span><strong className={i === 4 && tab === "cafes" ? styles.greenText : ""}>{loading && !data ? "…" : number(value as number | null)}<small>{i < 2 && tab === "cafes" ? "곳" : "개"}</small></strong><p>{note}</p></div>)}
      </div>
      {data?.job && <div className={styles.jobPanel} aria-live="polite"><div><span className={styles.jobTitle}>{running ? <Loader2 size={16} className={styles.spin} /> : <Terminal size={16} />}{running ? "읽기 전용 검증 실행 중" : data.job.status === "completed" ? "검증 완료" : "검증 종료 · 확인할 결과가 있습니다"}</span><span>{data.job.script === "all" ? "전체 크롤러 순차 실행" : data.job.script} · {dateTime(data.job.startedAt)}</span></div><details open={running}><summary>실행 로그</summary><pre>{data.job.output || "실행을 준비하고 있습니다…"}</pre></details></div>}
      <div className={styles.mainGrid}>
        <aside className={styles.regions} aria-label="지역별 현황"><div className={styles.sectionLabel}><Globe2 size={14} /> 지역별 카페</div><div className={styles.regionList}>{REGIONS.map(code => {
          const cafes = activeCafes.filter(cafe => areaMatches(code, cafe.area));
          const pass = cafes.filter(cafe => cafeStatus(cafe) === "smoke_pass").length;
          const attention = cafes.filter(cafe => ["needs_review", "error", "timeout"].includes(cafeStatus(cafe))).length;
          return <button key={code} className={`${styles.regionButton} ${(region === code || (code === "seoul" && areaMatches("seoul", region))) ? styles.regionSelected : ""}`} onClick={() => setRegion(code)} aria-pressed={region === code || (code === "seoul" && areaMatches("seoul", region))}><span>{AREA_LABELS[code]}<strong>{number(cafes.length)}</strong></span>{code !== "all" && <div className={styles.regionTrack} title={`검증 통과 ${pass}곳 · 확인 필요 ${attention}곳 · 그 외 미검증/미연결 ${cafes.length-pass-attention}곳`}><i style={{ width: `${cafes.length ? pass / cafes.length * 100 : 0}%` }} /><b style={{ width: `${cafes.length ? attention / cafes.length * 100 : 0}%` }} /></div>}</button>;
        })}</div><p className={styles.regionLegend}><i /> 통과 <b /> 확인 필요 <span /> 미검증·미연결</p></aside>
        <section className={styles.content} aria-label="크롤링 데이터">
          <div className={styles.contentHeader}><div className={styles.tabs}><button aria-pressed={tab === "cafes"} onClick={() => setTab("cafes")} className={tab === "cafes" ? styles.tabActive : ""}>카페 현황 <span>{number(filtered.length)}</span></button><button aria-pressed={tab === "runs"} onClick={() => setTab("runs")} className={tab === "runs" ? styles.tabActive : ""}>크롤러 검증 <span>{number(runs.length)}</span></button></div><button className={styles.iconButton} onClick={exportCsv} disabled={!data} title="현재 카페 목록 CSV 다운로드"><ArrowDownToLine size={16} /><span>CSV</span></button></div>
          <div className={styles.filters}><div className={styles.searchInput}><Search size={16} /><input aria-label="카페 또는 크롤러 검색" placeholder={tab === "cafes" ? "카페명, 지점, 주소, 크롤러 검색" : "크롤러 이름, 사이트 검색"} value={query} onChange={event => setQuery(event.target.value)} />{query && <button aria-label="검색어 지우기" onClick={() => setQuery("")}><X size={14} /></button>}</div><select aria-label="운영 상태" value={activity} onChange={event => setActivity(event.target.value)}><option value="active">운영 + 미등록</option><option value="all">운영 여부 전체</option><option value="inactive">비활성 카페</option></select></div>
          <div className={styles.statusFilters}>{[["all", "전체"], ["pass", "검증 통과"], ["attention", "확인 필요"], ["untested", "연결됨 · 미검증"], ["unconfigured", "미연결"], ["missing", "DB 미등록"]].filter(([id]) => tab === "cafes" || !["unconfigured", "missing"].includes(id)).map(([id, label]) => <button className={status === id ? styles.statusSelected : ""} onClick={() => setStatus(id)} key={id} aria-pressed={status === id}>{label}</button>)}<span>{AREA_LABELS[region]}</span>{(region === "seoul" || areaMatches("seoul", region)) && <select aria-label="서울 세부 지역" value={region} onChange={event => setRegion(event.target.value)}><option value="seoul">서울 전체</option>{AREAS.filter(area => ["gangnam", "hongdae", "sinchon", "konkuk", "jamsil", "itaewon", "myeongdong", "daehakro", "sinlim", "seongsu", "seoul_other"].includes(area.value)).map(area => <option key={area.value} value={area.value}>{area.label}</option>)}</select>}</div>
          <p className={styles.tableNote}><CircleHelp size={13} />{tab === "cafes" ? "회색 중 연결됨은 지점 검증 기록이 없는 상태, 미연결은 등록된 크롤러가 없는 상태입니다. 테마·시간대는 저장된 실제 데이터입니다. 검증 배지는 해당 지점이 포함된 크롤러 실행 결과입니다." : "실제 사이트 응답을 조회한 테스트 기록입니다. 통과는 조회·파싱 검증이며 실제 예약 성공을 뜻하지 않습니다."}</p>
          <div className={styles.tableScroll} aria-busy={loading}>
            {tab === "cafes" ? <table className={styles.table}><thead><tr><th>카페 / 지점</th><th>지역</th><th>수집 설정</th><th className={styles.numeric}>테마</th><th className={styles.numeric}>시간대</th><th className={styles.numeric}>예약 가능</th><th>테스트 테마 / 시간대</th><th>최근 검증</th><th>데이터 수집 시각</th><th><span className={styles.srOnly}>상세 보기</span></th></tr></thead><tbody>{filtered.slice(safePage * pageSize, (safePage + 1) * pageSize).map(cafe => <tr key={cafe.id}><td><button className={styles.cafeLink} onClick={() => { setSelected({ cafe }); setAllBranches(false); }}><strong>{cafe.name} {cafe.branch}</strong><span>{cafe.address}</span></button>{cafe.inDatabase === false && <span className={styles.missingLabel}>DB 미등록</span>}{cafe.inDatabase == null && <span className={styles.missingLabel}>DB 미확인</span>}{cafe.active === false && <span className={styles.missingLabel}>비활성</span>}</td><td><span className={styles.areaTag}>{AREA_LABELS[cafe.area] ?? cafe.area}</span></td><td><span className={cafe.coverage === "configured" ? styles.connected : styles.muted}>{cafe.coverage === "configured" ? "● 연결됨" : cafe.coverage === "not_crawlable" ? "불가로 분류" : "미구현"}</span><small className={styles.engine}>{cafe.engine ?? "엔진 미등록"}</small>{cafe.automaticPaused && <small className={styles.helper} title={cafe.pauseReason ?? undefined}>자동 수집 보류{cafe.pauseReason ? ` · ${cafe.pauseReason}` : ""}</small>}</td><td className={styles.numeric}>{number(cafe.themeCount)}</td><td className={styles.numeric}>{number(cafe.slotCount)}</td><td className={`${styles.numeric} ${cafe.available ? styles.greenText : styles.muted}`}>{number(cafe.available)}</td><td className={styles.testCounts}>{cafe.testThemeCount != null ? <><strong>{number(cafe.testThemeCount)} / {number(cafe.testSlotCount)}</strong><small>이 지점 테스트</small></> : cafe.checkInScope && cafe.check ? <><strong>— / —</strong><small>실행 합계 {number(cafe.check.themes_fetched)} / {number(cafe.check.slots)}</small></> : <span className={styles.muted}>미검증</span>}</td><td><Badge status={cafeStatus(cafe)} /><small className={styles.engine}>{cafe.checkInScope ? `${dateTime(cafe.check?.checked_at)} · 실행 단위` : cafe.check ? "대표 지점만 검증됨" : "실행 기록 없음"}</small></td><td className={styles.timestamp}>{dateTime(cafe.crawledAt)}</td><td><button className={styles.rowAction} onClick={() => { setSelected({ cafe }); setAllBranches(false); }} aria-label={`${cafe.name} ${cafe.branch} 상세 보기`}><ChevronRight size={17} /></button></td></tr>)}</tbody></table> : <table className={`${styles.table} ${styles.runTable}`}><thead><tr><th>크롤러 / 사이트</th><th>검증 결과</th><th className={styles.numeric}>등록 지점</th><th className={styles.numeric}>테스트 테마</th><th className={styles.numeric}>테스트 시간대</th><th>최근 실행</th><th><span className={styles.srOnly}>상세 보기</span></th></tr></thead><tbody>{runs.slice(safePage * pageSize, (safePage + 1) * pageSize).map(run => <tr key={run.id}><td><button className={styles.cafeLink} onClick={() => { setSelected({ run }); setAllBranches(false); }}><strong>{run.id.replace(/^sync_|_db$/g, "")}</strong><span>{run.urls.map(url => url.replace(/^https?:\/\//, "")).join(" · ")}</span></button></td><td><Badge status={run.latest?.status ?? "untested"} /><small className={styles.engine}>{run.latest?.scope.startsWith("all configured") ? "등록 지점 전체" : "대표 지점 / 사이트 범위"}</small></td><td className={styles.numeric}>{run.cafe_ids.length}</td><td className={styles.numeric}>{number(run.latest?.themes_fetched)}</td><td className={styles.numeric}>{number(run.latest?.slots)}</td><td className={styles.timestamp}>{dateTime(run.latest?.checked_at)}</td><td><button className={styles.rowAction} onClick={() => { setSelected({ run }); setAllBranches(false); }} aria-label={`${run.id} 검증 상세`}><ChevronRight size={17} /></button></td></tr>)}</tbody></table>}
            {count === 0 && !loading && <div className={styles.empty}><Search size={25} /><strong>조건에 맞는 항목이 없습니다.</strong><button onClick={() => { setQuery(""); setStatus("all"); setRegion("all"); setActivity("active"); }}>필터 초기화</button></div>}
            {loading && !data && <div className={styles.empty}><Loader2 size={24} className={styles.spin} /><strong>전국 카페와 검증 기록을 불러오는 중…</strong></div>}
          </div>
          <div className={styles.pagination}><span>{count ? `${number(safePage * pageSize + 1)}–${number(Math.min((safePage + 1) * pageSize, count))} / ` : ""}{number(count)}개</span><div><button aria-label="이전 페이지" disabled={safePage === 0} onClick={() => setPage(safePage - 1)}><ChevronLeft size={16} /></button><span>{safePage + 1} / {pageCount}</span><button aria-label="다음 페이지" disabled={safePage >= pageCount - 1} onClick={() => setPage(safePage + 1)}><ChevronRight size={16} /></button></div></div>
        </section>
      </div>
      <div className={styles.footer}><span><Activity size={13} /> DB 조회 {dateTime(data?.dataFetchedAt)} · KST · 자동 조회 시 5분 캐시</span><button onClick={() => startCheck("all")} disabled={running || starting || !data}><Play size={13} /> 전체 크롤러 순차 검증</button></div>
    </div>
    {selected && <div className={styles.overlay} onMouseDown={event => { if (event.target === event.currentTarget) setSelected(null); }}><div className={styles.drawer} role="dialog" aria-modal="true" aria-labelledby="detail-title" tabIndex={-1} ref={dialogRef}>
      <div className={styles.drawerHeader}><div><p>수집 · 검증 상세</p><h2 id="detail-title">{detailCafe ? `${detailCafe.name} ${detailCafe.branch}` : detailRun?.id.replace(/^sync_|_db$/g, "")}</h2></div><button onClick={() => setSelected(null)} aria-label="상세 닫기"><X size={21} /></button></div>
      <div className={styles.drawerBody}>
        {detailCafe && <><p className={styles.address}>{detailCafe.address}</p><div className={styles.detailMetrics}><div><span>저장 테마</span><strong>{number(detailCafe.themeCount)}</strong></div><div><span>저장 시간대</span><strong>{number(detailCafe.slotCount)}</strong></div><div><span>예약 가능</span><strong className={styles.greenText}>{number(detailCafe.available)}</strong></div></div><p className={styles.helper}>{date} 저장 데이터 · 최근 수집 {dateTime(detailCafe.crawledAt)}<br />시간대 0개는 미수집·미오픈·오류 등을 모두 포함할 수 있습니다.</p>{detailCafe.website && <a className={styles.externalLink} href={detailCafe.website} target="_blank" rel="noreferrer">공식 사이트 열기 <ArrowUpRight size={14} /></a>}<div className={styles.detailSection}><h3>저장된 테마</h3>{detailCafe.themes.length ? detailCafe.themes.map(theme => <div key={theme.id} className={styles.themeRow}><span>{theme.name}</span><strong>{theme.slots}개 <small>가능 {theme.available}</small></strong></div>) : <p className={styles.helper}>활성 테마가 저장되어 있지 않습니다.</p>}</div></>}
        <div className={styles.detailSection}><h3>크롤러 검증 기록</h3>{detailCafe?.testThemeCount != null && <div className={styles.detailPair}><span>이 지점 테스트 · 테마 / 시간대</span><strong>{number(detailCafe.testThemeCount)} / {number(detailCafe.testSlotCount)}</strong></div>}{detailCheck ? <><Badge status={detailCheck.status} />{detailCafe && <p className={styles.helper}>{detailCafe.checkInScope ? "이 지점이 포함된 실행입니다. 여러 지점을 검사했다면 배지는 실행 전체의 결과입니다." : "대표 지점 테스트 결과입니다. 이 지점은 아직 개별 검증되지 않았습니다."}</p>}<CheckInfo check={detailCheck} /></> : <p className={styles.helper}>아직 검증 기록이 없습니다.</p>}</div>
        {detailRun ? <div className={styles.testBox}><h3><Terminal size={16} /> 실제 사이트 다시 검증</h3><p>오늘·내일 예약 정보를 읽고 결과를 기록합니다. 운영 DB에는 저장하지 않습니다.</p><label><input type="checkbox" checked={allBranches} onChange={event => setAllBranches(event.target.checked)} /> 이 크롤러의 등록 지점 전체 검사</label><code>{command}</code><div><button onClick={async () => { await navigator.clipboard.writeText(command); setCopied(true); setTimeout(() => setCopied(false), 1500); }}>{copied ? <Check size={14} /> : <Terminal size={14} />}{copied ? "복사됨" : "명령 복사"}</button><button className={styles.primaryButton} disabled={running || starting} onClick={() => startCheck(detailRun.id)}>{starting ? <Loader2 size={14} className={styles.spin} /> : <Play size={14} />}{running ? "검증 진행 중" : "검증 실행"}</button></div></div> : <div className={styles.testBox}><h3>크롤러 연결이 필요합니다.</h3><p>이 카페에 매핑된 크롤러가 없습니다. 지점 ID와 예약 사이트를 확인해 크롤러 설정에 추가하세요.</p><code>cafe_id: {detailCafe?.id}</code></div>}
      </div>
    </div></div>}
  </div>;
}
