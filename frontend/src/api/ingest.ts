// ft-027: Ingest entrypoints (upload / arxiv / url).

import { getApi } from "./client";

export interface IngestResponse {
  job_id: string;
  status: string;
  paper_id: string;
  pdf_path: string;
}

export async function ingestUpload(
  file: File,
  paperId?: string,
): Promise<IngestResponse> {
  const api = await getApi();
  const form = new FormData();
  form.append("file", file);
  if (paperId) form.append("paper_id", paperId);
  const r = await api.post<IngestResponse>("/ingest/upload/", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return r.data;
}

export async function ingestArxiv(arxivId: string): Promise<IngestResponse> {
  const api = await getApi();
  const r = await api.post<IngestResponse>("/ingest/arxiv/", {
    arxiv_id: arxivId,
  });
  return r.data;
}

export async function ingestUrl(
  url: string,
  paperId?: string,
): Promise<IngestResponse> {
  const api = await getApi();
  const r = await api.post<IngestResponse>("/ingest/url/", {
    url,
    ...(paperId ? { paper_id: paperId } : {}),
  });
  return r.data;
}
