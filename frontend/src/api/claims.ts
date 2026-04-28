/**
 * ft-029 placeholder: claim-level user override endpoints land in ft-032.
 *
 * For now we only re-export the DTO shapes so consumers (`ClaimCard`,
 * `EvidenceItem`) can import from `@/api/claims` without a circular hop
 * through `@/api/papers`. PATCH / hide / report endpoints will arrive when
 * the user_claim_edit override layer ships.
 */
export type { ClaimDTO, ClaimEvidenceDTO, CounterSignalDTO } from "./papers";
