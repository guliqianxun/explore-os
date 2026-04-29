/**
 * ft-034 P0-6: paper-core types — Paper / status / list-item / brief.
 *
 * Carved out of single-file ``types/paper.ts`` per ft-034 P0-6 spec; the old
 * file now re-exports from here for backwards-compat.
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

/** All meaningful filter values used by the UI (StatusFilterBar).
 *
 * `brief` is the email-style two-section grouped view (主要 = reading|queued,
 * 速读 = new); other values are single-status feeds.
 */
export type StatusFilter = PaperStatus | "all" | "read" | "brief";

/** Alias used by some consumers for clarity ("user_status" vs the URL filter). */
export type PaperUserStatus = PaperStatus;

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

/** ft-033: 完整 PaperBrief（detail 视图、regenerate 返回）. */
export interface PaperBriefDTO {
  abstract_zh: string;
  keywords: string[];
  method_summary_zh: string;
  key_innovation: string[];
  limitations: string[];
  for_you: string;
  tldr_zh: string;
  perspective_used: string;
  model_used: string;
  generated_at: string | null;
}
