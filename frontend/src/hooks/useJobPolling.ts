// ft-027 follow-up: poll non-terminal jobs every 2s, auto-stop on terminal status.
import { useEffect } from "react";
import { JobInfo, getJob, JobStatus, normalizeJobStatus } from "@/api/jobs";
import { useJobsStore } from "@/stores/jobsStore";

// ft-034 P0-6: 5-value enum lock (was 4-value with ``succeeded``). Legacy wire
// values (``queued`` / ``succeeded``) are mapped via ``normalizeJobStatus``
// before the terminal check so polling stops correctly during the 1-sprint
// deprecation.
const TERMINAL: ReadonlyArray<JobStatus> = ["done", "failed", "cancelled"];

export function isTerminal(status: string): boolean {
  return TERMINAL.includes(normalizeJobStatus(status));
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
