/**
 * ft-034 P0-7: claim endpoint helpers (per-paper claim list).
 *
 * Claim DTOs live in ``@/types/paper-claim``; this module re-exports + adds
 * the fetcher.
 */

import { getApi } from "../client";
import type { ClaimDTO } from "@/types/paper-claim";

// Re-export DTO types so consumers can keep importing them via
// ``@/api/papers``.
export type {
  ClaimDTO,
  ClaimEvidence,
  ClaimEvidenceDTO,
  ClaimVerdict,
  CounterSignal,
  CounterSignalDTO,
  EvidenceDTO,
} from "@/types/paper-claim";

export async function getPaperClaims(arxivId: string): Promise<ClaimDTO[]> {
  const api = await getApi();
  const r = await api.get<ClaimDTO[]>(
    `/papers/${encodeURIComponent(arxivId)}/claims/`,
  );
  return r.data;
}
