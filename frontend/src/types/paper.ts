/**
 * ft-028 central paper-domain types. Re-exported by `@/api/papers` to keep
 * existing consumers stable; new code SHOULD import from here.
 *
 * Field names are FROZEN per ft-028.md#dto-contracts — do NOT rename.
 */

export type PaperStatus =
  | "new"
  | "queued"
  | "reading"
  | "read_kept"
  | "read_dropped"
  | "archived";

/** All meaningful filter values used by the UI (StatusFilterBar). */
export type StatusFilter = PaperStatus | "all" | "read";

export interface CommentDTO {
  id: number;
  text: string;
  /** ISO 8601 timestamp. */
  created_at: string;
  hidden: boolean;
}

export interface BacklinkEdge {
  id: number;
  /** Filled on incoming edges (other paper points to me). */
  src_key?: string;
  src_title?: string;
  /** Filled on outgoing edges (I point to other paper). */
  dst_key?: string;
  dst_title?: string;
  relation: string;
  note: string;
  created_at: string;
}

export interface BacklinkDTO {
  outgoing: BacklinkEdge[];
  incoming: BacklinkEdge[];
}

// ---------------------------------------------------------------------------
// ft-029: PDF + evidence + counter_signal additions
//
// `has_pdf` / `pdf_url` come from PaperDetailView (rpt-013). `pdf_url` may be
// null for legacy detail responses without a Paper row — frontend should drive
// off `has_pdf` and not assume `pdf_url` is non-null.
// ---------------------------------------------------------------------------

/** `material_id` of an evidence target — points into sections/figures/tables/equations. */
export interface ClaimEvidence {
  material_id: string;
  /** "supports" | "qualifies" | etc. — string-typed, not enum-locked. */
  relation: string;
}

export interface CounterSignal {
  signal_id: string;
  text: string;
  signal_type: string;
  evidence_material_id: string;
}
