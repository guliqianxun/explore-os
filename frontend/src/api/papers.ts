import { getApi } from "./client";

export interface PaperListItem {
  arxiv_id: string;
  n_sections: number;
  n_figures: number;
  n_tables: number;
  n_claims: number;
}

export interface SectionDTO {
  material_id: string;
  paper_arxiv_id: string;
  seq: number;
  path: string;
  level: number;
  char_offset_start: number;
  char_offset_end: number;
  raw_text: string;
}

export interface FigureDTO {
  material_id: string;
  paper_arxiv_id: string;
  seq: number;
  fig_label: string;
  page: number;
  bbox: number[] | null;
  caption: string;
  image_path: string;
}

export interface TableDTO {
  material_id: string;
  paper_arxiv_id: string;
  seq: number;
  tbl_label: string;
  page: number;
  bbox: number[] | null;
  caption: string;
  raw_text: string;
}

export interface EquationDTO {
  material_id: string;
  seq: number;
  page: number;
  latex_or_text: string;
  inline_or_display: string;
}

export interface ClaimEvidenceDTO {
  material_id: string;
  relation: string;
}

export interface CounterSignalDTO {
  signal_id: string;
  text: string;
  signal_type: string;
  evidence_material_id: string;
}

export interface ClaimDTO {
  claim_id: string;
  paper_arxiv_id: string;
  text: string;
  text_en: string;
  claim_type: string;
  source_section_path: string;
  confidence: number;
  evidences: ClaimEvidenceDTO[];
  counter_signals: CounterSignalDTO[];
}

export interface PaperDetail {
  arxiv_id: string;
  sections: SectionDTO[];
  figures: FigureDTO[];
  tables: TableDTO[];
  equations: EquationDTO[];
  claims: ClaimDTO[];
}

export async function listPapers(): Promise<PaperListItem[]> {
  const api = await getApi();
  const r = await api.get<PaperListItem[]>("/papers/");
  return r.data;
}

export async function getPaperDetail(arxivId: string): Promise<PaperDetail> {
  const api = await getApi();
  const r = await api.get<PaperDetail>(`/papers/${encodeURIComponent(arxivId)}/`);
  return r.data;
}

export async function getPaperMarkdown(arxivId: string): Promise<string> {
  const api = await getApi();
  const r = await api.get<string>(
    `/papers/${encodeURIComponent(arxivId)}/markdown/`,
    { responseType: "text", transformResponse: (v) => v },
  );
  return r.data;
}

export async function getPaperClaims(arxivId: string): Promise<ClaimDTO[]> {
  const api = await getApi();
  const r = await api.get<ClaimDTO[]>(
    `/papers/${encodeURIComponent(arxivId)}/claims/`,
  );
  return r.data;
}

/** Returns the absolute URL of a figure PNG (for `<img src=...>`). */
export async function figureUrl(arxivId: string, seq: number): Promise<string> {
  const api = await getApi();
  return `${api.defaults.baseURL}/papers/${encodeURIComponent(arxivId)}/figure/${seq}.png`;
}
