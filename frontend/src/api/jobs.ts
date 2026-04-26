import { getApi } from "./client";

export type JobStatus =
  | "pending"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled";

export interface JobInfo {
  job_id: string;
  name: string;
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
