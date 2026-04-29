/**
 * ft-034 P0-6: thin re-export shell.
 *
 * Old single-file ``types/paper.ts`` was carved into ``paper-{core,material,
 * claim,job}.ts`` per ft-034 P0-6. This file keeps existing
 * ``import { ... } from "@/types/paper"`` consumers working through 1 sprint
 * deprecation — new code SHOULD import from the per-domain file directly.
 */

export type {
  BacklinkDTO,
  BacklinkEdge,
  CommentDTO,
  PaperBriefDTO,
  PaperStatus,
  PaperUserStatus,
  StatusFilter,
} from "./paper-core";

export type {
  CitationDTO,
  EquationDTO,
  FigureDTO,
  SectionDTO,
  TableDTO,
} from "./paper-material";

export type {
  ClaimDTO,
  ClaimEvidence,
  ClaimEvidenceDTO,
  ClaimVerdict,
  CounterSignal,
  CounterSignalDTO,
  EvidenceDTO,
} from "./paper-claim";

export type { JobDTO, JobStatus } from "./paper-job";
export { normalizeJobStatus } from "./paper-job";
