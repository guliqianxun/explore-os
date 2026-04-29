import { getApi } from "./client";
import { normalizeJobStatus, type JobStatus } from "@/types/paper-job";

// ft-034 P0-6: re-export canonical 5-value enum from the type module.
// 老 import ``import { JobStatus } from "@/api/jobs"`` 不变；底层 lock 来自
// ``@/types/paper-job``。前端短期兼容老值（queued / succeeded）走
// ``normalizeJobStatus``。
export type { JobStatus };
export { normalizeJobStatus };

export interface JobInfo {
  job_id: string;
  name: string;
  /** Wire status — may be legacy ``queued`` / ``succeeded`` until v1.3 drop;
   *  consumers should run ``normalizeJobStatus`` before comparing if the
   *  origin is the trigger response (which bypasses JobSerializer). */
  status: JobStatus | string;
  created_at: string;
  started_at: string;
  finished_at: string;
  result?: unknown;
  error: string;
}

export interface TriggerResponse {
  job_id: string;
  status: string;
}

export async function triggerExtract(
  arxivId: string,
  pdfPath?: string,
): Promise<TriggerResponse> {
  const api = await getApi();
  const r = await api.post<TriggerResponse>(
    `/papers/${encodeURIComponent(arxivId)}/extract/`,
    pdfPath ? { pdf_path: pdfPath } : {},
  );
  return r.data;
}

export async function triggerInterpret(
  arxivId: string,
  pdfPath?: string,
): Promise<TriggerResponse> {
  const api = await getApi();
  const r = await api.post<TriggerResponse>(
    `/papers/${encodeURIComponent(arxivId)}/interpret/`,
    pdfPath ? { pdf_path: pdfPath } : {},
  );
  return r.data;
}

export async function triggerRender(
  arxivId: string,
  format: "excalidraw" | "svg" = "excalidraw",
): Promise<TriggerResponse> {
  const api = await getApi();
  const r = await api.post<TriggerResponse>(
    `/papers/${encodeURIComponent(arxivId)}/render/`,
    { format },
  );
  return r.data;
}

export async function getJob(jobId: string): Promise<JobInfo> {
  const api = await getApi();
  const r = await api.get<JobInfo>(`/jobs/${encodeURIComponent(jobId)}/`);
  return r.data;
}
