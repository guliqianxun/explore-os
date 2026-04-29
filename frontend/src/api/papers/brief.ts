/**
 * ft-034 P0-7: brief endpoint helpers (regenerate).
 *
 * Brief DTO lives in ``@/types/paper-core`` (it's part of the core paper shape);
 * this module keeps the regenerate fetcher per ft-033.
 */

import { getApi } from "../client";
import type { PaperBriefDTO } from "@/types/paper-core";

// Re-export so legacy ``import { type PaperBriefDTO } from "@/api/papers"``
// still works.
export type { PaperBriefDTO };

/** ft-033: POST /api/papers/<id>/brief/regenerate/ — 同步 LLM 生成. */
export async function regeneratePaperBrief(id: string): Promise<PaperBriefDTO> {
  const api = await getApi();
  const r = await api.post<PaperBriefDTO>(
    `/papers/${encodeURIComponent(id)}/brief/regenerate/`,
  );
  return r.data;
}
