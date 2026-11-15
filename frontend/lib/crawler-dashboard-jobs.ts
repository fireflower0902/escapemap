import { spawn } from "node:child_process";
import path from "node:path";
import type { DashboardJob } from "@/lib/crawler-dashboard-types";

const state = globalThis as typeof globalThis & { crawlerDashboardJob?: DashboardJob };
export function getCrawlerJob(): DashboardJob | null { return state.crawlerDashboardJob ?? null; }

export function startCrawlerJob(script: string, allBranches: boolean): DashboardJob {
  if (state.crawlerDashboardJob?.status === "running") throw new Error("ALREADY_RUNNING");
  const backend = path.resolve(process.cwd(), "../backend");
  const job: DashboardJob = {
    id: crypto.randomUUID(), script, allBranches, status: "running", startedAt: new Date().toISOString(),
    finishedAt: null, output: "", exitCode: null,
  };
  const args = [path.join(backend, "scripts/check_crawlers.py"), ...(script === "all" ? ["--all"] : [script]),
    "--days", "1", "--timeout", allBranches ? "240" : "90", "--output", path.join(backend, "reports/crawlers/dashboard")];
  if (allBranches) args.push("--all-branches");
  const child = spawn(path.join(backend, ".venv/bin/python"), args, {
    cwd: backend, env: { ...process.env, TZ: "Asia/Seoul", PYTHONUNBUFFERED: "1", CRAWL_SEOUL_ONLY: "false", SKIP_META_WRITES: "false" },
    stdio: ["ignore", "pipe", "pipe"],
  });
  state.crawlerDashboardJob = job;
  const append = (chunk: Buffer) => { job.output = (job.output + chunk.toString()).slice(-8_000); };
  child.stdout.on("data", append);
  child.stderr.on("data", append);
  child.on("error", error => {
    job.status = "failed"; job.finishedAt = new Date().toISOString(); job.output += `\n실행 실패: ${error.message}`;
  });
  child.on("close", code => {
    job.status = code === 0 ? "completed" : "failed";
    job.exitCode = code; job.finishedAt = new Date().toISOString();
  });
  return job;
}
