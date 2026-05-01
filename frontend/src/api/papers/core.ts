/**
 * ft-034 P0-7: paper list + detail + status / tag / comment / backlink endpoints.
 *
 * Carved out of ``frontend/src/api/papers.ts`` per ft-034 P0-7 — old papers.ts
 * now re-exports from this package.
 */

import { getApi } from "../client";
import type {
  BacklinkDTO,
  BacklinkEdge,
  CommentDTO,
  PaperBriefDTO,
  PaperStatus,
} from "@/types/paper-core";
import type {
  EquationDTO,
  FigureDTO,
  SectionDTO,
  TableDTO,
} from "@/types/paper-material";
import type { ClaimDTO } from "@/types/paper-claim";

// Re-export wire DTO types so legacy consumers can keep importing them from
// the api module (matches the historical surface of papers.ts).
export type {
  BacklinkDTO,
  BacklinkEdge,
  CommentDTO,
  PaperBriefDTO,
  PaperStatus,
};

/**
 * ft-028 extended PaperListItem.
 *
 * `paper_key`, `status`, `tags`, `n_comments` were added 2026-04-28 alongside
 * the Paper-centric schema. Until the backend rolls them out the response may
 * legitimately omit them; treat all four as optional at the wire and fill
 * sensible defaults when consumed (see `normalizePaperListItem`).
 */
export interface PaperListItem {
  arxiv_id: string;
  /** Zotero-style stable key, `[A-Z2-9]{8}`. Backend may add later. */
  paper_key: string;
  title: string;
  status: PaperStatus;
  tags: string[];
  n_comments: number;
  n_sections: number;
  n_figures: number;
  n_tables: number;
  n_claims: number;
  // ft-033 brief 短字段（list 视图用）
  /** 一句话精炼（中文）；空则前端 fallback abstract_en 截断。 */
  tldr_zh: string;
  /** 完整中文摘要（list 卡片 lead 用 — 比 tldr_zh 信息密度高）。 */
  abstract_zh: string;
  /** 作者 keywords（来自 paper 自身，不是 brief.keywords/LLM）。 */
  keywords: string[];
  /** LLM 抽的综述 keywords（chip 主源；paper.keywords 空时 fallback）。 */
  brief_keywords: string[];
  /** AI summary 卡用：brief.key_innovation 前 2 条。 */
  key_innovation: string[];
  /** brief 是否已生成（abstract_zh 非空才算）。 */
  has_brief: boolean;
  /** 原文 abstract（fallback；brief 缺失时前端截断显示）。 */
  abstract_en: string;
  /** ft-031: ISO8601 UTC，brief 速读区按今日/本周/更早分桶用。 */
  created_at: string;
}

/** Wire shape — every ft-028 field is optional during rollout. */
type PaperListItemWire = Partial<PaperListItem> &
  Pick<
    PaperListItem,
    "arxiv_id" | "n_sections" | "n_figures" | "n_tables" | "n_claims"
  >;

function normalizePaperListItem(raw: PaperListItemWire): PaperListItem {
  return {
    arxiv_id: raw.arxiv_id,
    paper_key: raw.paper_key ?? "",
    title: raw.title ?? raw.arxiv_id,
    status: raw.status ?? "new",
    tags: raw.tags ?? [],
    n_comments: raw.n_comments ?? 0,
    n_sections: raw.n_sections,
    n_figures: raw.n_figures,
    n_tables: raw.n_tables,
    n_claims: raw.n_claims,
    tldr_zh: raw.tldr_zh ?? "",
    abstract_zh: raw.abstract_zh ?? "",
    keywords: raw.keywords ?? [],
    brief_keywords: raw.brief_keywords ?? [],
    key_innovation: raw.key_innovation ?? [],
    has_brief: raw.has_brief ?? false,
    abstract_en: raw.abstract_en ?? "",
    created_at: raw.created_at ?? "",
  };
}

export interface PaperDetail {
  arxiv_id: string;
  /** ft-028 stable key, may be missing in legacy responses. */
  paper_key?: string;
  title?: string;
  status?: PaperStatus;
  tags?: string[];
  n_comments?: number;
  /** ft-029: present from backend rpt-013. */
  has_pdf?: boolean;
  /** ft-029: relative path string; may be null for legacy material-only paths. */
  pdf_url?: string | null;
  /** ft-033: 原文 abstract（detail 暴露完整文本）。 */
  abstract?: string;
  /** 作者 keywords（区别于 brief.keywords / LLM 抽出的）。 */
  keywords?: string[];
  /** ft-033: 完整 PaperBrief（未生成 → null）。 */
  brief?: PaperBriefDTO | null;
  sections: SectionDTO[];
  figures: FigureDTO[];
  tables: TableDTO[];
  equations: EquationDTO[];
  claims: ClaimDTO[];
}

// ---------------------------------------------------------------------------
// listPapers (filterable)
// ---------------------------------------------------------------------------

export interface ListPapersOpts {
  /** "all" omits the param; any other value passes through. */
  status?: PaperStatus | "all";
  tag?: string;
  q?: string;
}

export async function listPapers(
  opts: ListPapersOpts = {},
): Promise<PaperListItem[]> {
  const api = await getApi();
  const params: Record<string, string> = {};
  if (opts.status && opts.status !== "all") params.status = opts.status;
  if (opts.tag) params.tag = opts.tag;
  if (opts.q) params.q = opts.q;
  const r = await api.get<PaperListItemWire[]>("/papers/", { params });
  return r.data.map(normalizePaperListItem);
}

export async function getPaperDetail(arxivId: string): Promise<PaperDetail> {
  const api = await getApi();
  const r = await api.get<PaperDetail>(`/papers/${encodeURIComponent(arxivId)}/`);
  return r.data;
}

// ---------------------------------------------------------------------------
// ft-028 user_* layer endpoints
//
// `id` accepts either the 8-char paper_key or the arxiv_id; the backend
// resolves both per ft-028 spec § "URL 解析".
// ---------------------------------------------------------------------------

export async function setPaperStatus(
  id: string,
  status: PaperStatus,
): Promise<void> {
  const api = await getApi();
  await api.post(`/papers/${encodeURIComponent(id)}/status/`, { status });
}

/** 覆盖式更新 paper.keywords（作者关键词，区别于 brief.keywords / LLM）. */
export async function setPaperKeywords(
  id: string,
  keywords: string[],
): Promise<string[]> {
  const api = await getApi();
  const r = await api.post<{ keywords: string[] }>(
    `/papers/${encodeURIComponent(id)}/keywords/`,
    { keywords },
  );
  return r.data.keywords;
}

export async function listPaperComments(id: string): Promise<CommentDTO[]> {
  const api = await getApi();
  const r = await api.get<CommentDTO[]>(
    `/papers/${encodeURIComponent(id)}/comments/`,
  );
  return r.data;
}

export async function appendPaperComment(
  id: string,
  text: string,
): Promise<CommentDTO> {
  const api = await getApi();
  const r = await api.post<CommentDTO>(
    `/papers/${encodeURIComponent(id)}/comments/`,
    { text },
  );
  return r.data;
}

export async function listPaperTags(id: string): Promise<string[]> {
  const api = await getApi();
  const r = await api.get<string[]>(`/papers/${encodeURIComponent(id)}/tags/`);
  return r.data;
}

export async function addPaperTag(id: string, tag: string): Promise<void> {
  const api = await getApi();
  await api.post(`/papers/${encodeURIComponent(id)}/tags/`, { tag });
}

export async function removePaperTag(id: string, tag: string): Promise<void> {
  const api = await getApi();
  await api.delete(
    `/papers/${encodeURIComponent(id)}/tags/${encodeURIComponent(tag)}/`,
  );
}

export async function listPaperBacklinks(id: string): Promise<BacklinkDTO> {
  const api = await getApi();
  const r = await api.get<BacklinkDTO>(
    `/papers/${encodeURIComponent(id)}/backlinks/`,
  );
  return r.data;
}

export async function addPaperBacklink(
  id: string,
  dst: string,
  relation?: string,
  note?: string,
): Promise<BacklinkEdge> {
  const api = await getApi();
  const body: { dst: string; relation?: string; note?: string } = { dst };
  if (relation !== undefined) body.relation = relation;
  if (note !== undefined) body.note = note;
  const r = await api.post<BacklinkEdge>(
    `/papers/${encodeURIComponent(id)}/backlinks/`,
    body,
  );
  return r.data;
}

export async function removePaperBacklink(
  id: string,
  bid: number,
): Promise<void> {
  const api = await getApi();
  await api.delete(`/papers/${encodeURIComponent(id)}/backlinks/${bid}/`);
}

// ---------------------------------------------------------------------------
// ft-029: PDF presence + absolute URL helpers + typeahead search
// ---------------------------------------------------------------------------

/**
 * HEAD /api/papers/<id>/pdf/ — returns 200 when a PDF is on disk, 404 otherwise.
 * Used by `useHasPdf` to decide between station and speed mode when the detail
 * payload predates rpt-013 (no `has_pdf`).
 */
export async function headPaperPdf(id: string): Promise<boolean> {
  const api = await getApi();
  try {
    const r = await api.head(`/papers/${encodeURIComponent(id)}/pdf/`, {
      // Don't throw on 404 — that's the negative answer we want.
      validateStatus: (s) => s === 200 || s === 404,
    });
    return r.status === 200;
  } catch {
    return false;
  }
}

/**
 * Returns the absolute URL the PDF can be fetched from. Awaits the axios
 * client only to learn its baseURL — the URL itself contains no auth, so it's
 * safe to feed straight into `<Document file={url}>`.
 */
export async function pdfFileUrl(id: string): Promise<string> {
  const api = await getApi();
  return `${api.defaults.baseURL}/papers/${encodeURIComponent(id)}/pdf/`;
}

/** Typeahead for BacklinkEditor — `?q=<term>&limit=5` icontains. */
export async function searchPapersTypeahead(
  q: string,
  limit = 5,
): Promise<PaperListItem[]> {
  const api = await getApi();
  const params: Record<string, string> = { q, limit: String(limit) };
  const r = await api.get<PaperListItemWire[]>("/papers/", { params });
  return r.data.map(normalizePaperListItem);
}
