// ft-027 follow-up: poll non-terminal jobs every 2s, auto-stop on terminal status.
// ft-031: detect ``run-sub:*`` terminal-success transitions → desktop notify
// (system toast) + invalidate undecided-count query so NavBar badge refreshes.
import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { JobInfo, getJob, JobStatus, normalizeJobStatus } from "@/api/jobs";
import { useJobsStore } from "@/stores/jobsStore";
import { notify } from "@/lib/notify";
import i18n from "@/i18n";

// ft-034 P0-6: 5-value enum lock (was 4-value with ``succeeded``). Legacy wire
// values (``queued`` / ``succeeded``) are mapped via ``normalizeJobStatus``
// before the terminal check so polling stops correctly during the 1-sprint
// deprecation.
const TERMINAL: ReadonlyArray<JobStatus> = ["done", "failed", "cancelled"];

export function isTerminal(status: string): boolean {
  return TERMINAL.includes(normalizeJobStatus(status));
}

function isSubRun(name: string | undefined): boolean {
  return typeof name === "string" && name.startsWith("run-sub:");
}

function subNameFromJob(name: string | undefined): string {
  if (!name) return "";
  return name.startsWith("run-sub:") ? name.slice("run-sub:".length) : name;
}

/**
 * Polls every active job in store every `intervalMs`. Stops polling each
 * job once it reaches a terminal status. Idempotent — multiple components
 * mounting this hook only spawn one timer due to upsert dedup.
 *
 * ft-031: keeps a Set of job_ids we've already notified for so a re-render
 * of the same terminal job doesn't re-fire the toast.
 */
export function useJobPolling(intervalMs = 2000): void {
  const upsert = useJobsStore((s) => s.upsert);
  const jobs = useJobsStore((s) => s.jobs);
  const qc = useQueryClient();
  const notifiedRef = useRef<Set<string>>(new Set());

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
            if (cancelled) return;
            upsert(fresh);
            // ft-031: 在 stale-cache 边沿触发通知 — 仅当此 job 此次首次进入
            // terminal 状态。失败/取消不弹（spec：只覆盖 sub run 完成）。
            if (
              isTerminal(fresh.status) &&
              normalizeJobStatus(fresh.status) === "done" &&
              isSubRun(fresh.name) &&
              !notifiedRef.current.has(fresh.job_id)
            ) {
              notifiedRef.current.add(fresh.job_id);
              const sub = subNameFromJob(fresh.name);
              await notify({
                title: i18n.t("notifications.sub_complete_title"),
                body: sub
                  ? i18n.t("notifications.sub_complete_body", { name: sub })
                  : i18n.t("notifications.sub_complete_body_default"),
                jobId: fresh.job_id,
              });
              // 未决数 badge 刷新
              qc.invalidateQueries({ queryKey: ["papers", "undecided-count"] });
              qc.invalidateQueries({ queryKey: ["papers"] });
            }
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
  }, [jobs, intervalMs, upsert, qc]);
}
