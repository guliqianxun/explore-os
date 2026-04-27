// ft-027 follow-up: poll non-terminal jobs every 2s, auto-stop on terminal status.
import { useEffect } from "react";
import { JobInfo, getJob, JobStatus } from "@/api/jobs";
import { useJobsStore } from "@/stores/jobsStore";

const TERMINAL: ReadonlyArray<JobStatus> = ["succeeded", "failed", "cancelled"];

export function isTerminal(status: string): boolean {
  return TERMINAL.includes(status as JobStatus);
}

/**
 * Polls every active job in store every `intervalMs`. Stops polling each
 * job once it reaches a terminal status. Idempotent — multiple components
 * mounting this hook only spawn one timer due to upsert dedup.
 */
export function useJobPolling(intervalMs = 2000): void {
  const upsert = useJobsStore((s) => s.upsert);
  const jobs = useJobsStore((s) => s.jobs);

  useEffect(() => {
    const activeIds = Object.values(jobs)
      .filter((j) => !isTerminal(j.status))
      .map((j) => j.job_id);
    if (activeIds.length === 0) return;

    let cancelled = false;
    const tick = async () => {
      await Promise.all(
        activeIds.map(async (id) => {
          try {
            const fresh: JobInfo = await getJob(id);
            if (!cancelled) upsert(fresh);
          } catch {
            // network glitch — ignore, next tick will retry
          }
        }),
      );
    };
    tick();
    const t = setInterval(tick, intervalMs);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, [jobs, intervalMs, upsert]);
}
