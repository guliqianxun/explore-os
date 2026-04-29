/**
 * ft-034 P0-6: claim DTOs (claim + evidence + counter-signal).
 *
 * Carved out of single-file ``types/paper.ts``; alias ``ClaimEvidence`` /
 * ``CounterSignal`` (no DTO suffix) preserved for ft-029 consumers.
 */

/** `material_id` of an evidence target — points into sections/figures/tables/equations. */
export interface ClaimEvidence {
  material_id: string;
  /** "supports" | "qualifies" | etc. — string-typed, not enum-locked. */
  relation: string;
}

/** Alias matching backend serializer name. */
export type ClaimEvidenceDTO = ClaimEvidence;

export interface CounterSignal {
  signal_id: string;
  text: string;
  signal_type: string;
  evidence_material_id: string;
}

/** Alias matching backend serializer name. */
export type CounterSignalDTO = CounterSignal;

/**
 * ft-029: ClaimVerdict 是 frontend-only 的三态显示标签，
 * 由 ``deriveClaimVerdict`` 从 evidences + counter_signals 推导。
 */
export type ClaimVerdict = "supported" | "contested" | "uncertain";

export interface EvidenceDTO {
  material_id: string;
  relation: string;
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
