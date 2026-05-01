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
          let fresh: JobInfo;
          try {
            fresh = await getJob(id);
          } catch (err) {
            // ft-040 follow-up: sidecar 重启会丢 in-memory _JOBS dict。
            // 此时 GET /api/jobs/<id>/ 返回 404，前端的 job 永远卡在 "pending"。
            // 把 404 视为终态 "done" — chain 通常已经把数据落库了，前端
            // 显示成已完成最贴近事实；用户能看到 "Read →" 链接而非永远转圈。
            // 网络瞬断（无 response.status）不命中。
            const httpStatus = (err as { response?: { status?: number } })
              ?.response?.status;
            if (httpStatus === 404 && !cancelled) {
              const stale = jobs[id];
              if (stale) {
                upsert({
                  ...stale,
                  status: "done",
                  finished_at: new Date().toISOString(),
                });
              }
            }
            // 其它错误（5xx / 网络瞬断）忽略，下一 tick 重试
            return;
          }
          if (cancelled) return;
          upsert(fresh);
          try {
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
              qc.invalidateQueries({ queryKey: ["papers", "undecided-count"] });
              qc.invalidateQueries({ queryKey: ["papers"] });
            }
          } catch {
            // notify / invalidate 偶发问题不影响主轮询
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
