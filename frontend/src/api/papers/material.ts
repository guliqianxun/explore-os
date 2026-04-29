/**
 * ft-034 P0-7: material endpoint helpers (figure URL).
 *
 * Material DTOs themselves live in ``@/types/paper-material``; this module
 * holds the URL construction + future material endpoints (table CSV download
 * etc.) — currently small, but the split mirrors backend's
 * ``apps/api/views/materials.py``.
 */

import { getApi } from "../client";

// Re-export DTOs from the type file so consumers can do
// ``import type { FigureDTO } from "@/api/papers"`` (legacy surface).
export type {
  CitationDTO,
  EquationDTO,
  FigureDTO,
  SectionDTO,
  TableDTO,
} from "@/types/paper-material";

/** Returns the absolute URL of a figure PNG (for `<img src=...>`). */
export async function figureUrl(arxivId: string, seq: number): Promise<string> {
  const api = await getApi();
  return `${api.defaults.baseURL}/papers/${encodeURIComponent(arxivId)}/figure/${seq}.png`;
}
