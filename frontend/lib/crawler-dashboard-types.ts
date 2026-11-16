export type CheckStatus = "smoke_pass" | "needs_review" | "error" | "timeout" | "untested";
export type CafeCoverage = "configured" | "unconfigured" | "not_crawlable";
export type CatalogEntry = {
  id: string; name: string; urls: string[]; cafe_ids: string[];
  cafes: Record<string, string>[];
  selections: Record<string, Record<string, string[]>>;
};
export type CrawlerCheck = {
  script: string; checked_at: string; status: CheckStatus; scope: string;
  themes_fetched: number; slots: number; cafes_with_slots: number;
  dates: string[]; statuses: Record<string, number>; issues: string[]; log_errors: string[];
  requested_cafe_ids?: string[]; error?: string; selected?: Record<string, unknown>;
  per_cafe?: Record<string, { themes: number; slots: number; statuses: Record<string, number>; dates: string[] }>;
  source: string;
};
export type DashboardRun = CatalogEntry & { latest: CrawlerCheck | null; testedCafeIds: string[] };
export type DashboardCafe = {
  id: string; name: string; branch: string; address: string; area: string;
  active: boolean | null; inDatabase: boolean | null; website: string | null; engine: string | null;
  automaticPaused?: boolean; pauseReason?: string | null;
  coverage: CafeCoverage; scriptIds: string[]; check: CrawlerCheck | null; checkInScope: boolean;
  themeCount: number | null; slotCount: number | null; available: number | null;
  testThemeCount: number | null; testSlotCount: number | null;
  full: number | null; closed: number | null; crawledAt: string | null;
  themes: { id: string; name: string; slots: number; available: number }[];
};
export type DashboardPayload = {
  date: string; loadedAt: string; dataFetchedAt: string | null;
  warnings: string[]; cafes: DashboardCafe[]; runs: DashboardRun[]; job?: DashboardJob | null;
};
export type DashboardJob = {
  id: string; script: string; allBranches: boolean; status: "running" | "completed" | "failed";
  startedAt: string; finishedAt: string | null; output: string; exitCode: number | null;
};
