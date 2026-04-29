/**
 * ft-034 P0-6 + review-B D5: JobStatus canonical 5-value enum.
 *
 * Backend lock (ft-034 P0-6): ``pending | running | done | failed | cancelled``.
 * 老 backend dataclass 仍 emit ``queued`` / ``succeeded`` 一段时间内 (1 sprint
 * deprecation)；DTO 边界已经 mapping 翻译了 (apps/api/serializers/jobs.py)，
 * 但 trigger 接口直接吐 ``info.status`` 不走 serializer，前端做兜底。
 */

export type JobStatus = "pending" | "running" | "done" | "failed" | "cancelled";

const _LEGACY_MAP: Record<string, JobStatus> = {
  queued: "pending",
  succeeded: "done",
};

/**
 * Translate any wire status string → canonical JobStatus. Unknown values
 * pass through as-is (cast widens to ``JobStatus``) so unrecognised states
 * still render rather than crashing the polling hook.
 */
export function normalizeJobStatus(raw: string): JobStatus {
  return (_LEGACY_MAP[raw] ?? (raw as JobStatus));
}

export interface JobDTO {
  job_id: string;
  name: string;
  status: JobStatus;
  created_at: string;
  started_at: string;
  finished_at: string;
  result?: unknown;
  error: string;
}
