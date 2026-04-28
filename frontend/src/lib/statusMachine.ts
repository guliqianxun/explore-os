/**
 * ft-029: paper status state machine — frontend mirror of the backend
 * `apps/papers/status.py` STATUS_TRANSITIONS table.
 *
 * Single source of truth for:
 *   - which targets `ActionBar` exposes given the current status,
 *   - which menu items in `StatusPill` are disabled (canTransition gate),
 *   - which mode (`speed` vs `station`) ReadingStation should default to.
 *
 * If the backend table changes, update this file in lockstep — failing fast in
 * the optimistic mutation is far cheaper than silently letting the UI offer a
 * transition the server will reject.
 */
import type { PaperStatus } from "@/types/paper";

export const PAPER_STATUSES: PaperStatus[] = [
  "new",
  "queued",
  "reading",
  "read_kept",
  "read_dropped",
  "archived",
];

/**
 * Allowed transitions. Mirrors backend STATUS_TRANSITIONS:
 *   new        → queued | reading | read_dropped | archived
 *   queued     → reading | read_dropped | archived
 *   reading    → read_kept | read_dropped | queued | archived
 *   read_kept  → archived | reading
 *   read_dropped → archived | reading
 *   archived   → reading                    (Reopen)
 *
 * A status can also transition to itself (no-op accepted by the backend).
 */
export const STATUS_TRANSITIONS: Record<PaperStatus, PaperStatus[]> = {
  new: ["new", "queued", "reading", "read_dropped", "archived"],
  queued: ["queued", "reading", "read_dropped", "archived"],
  reading: ["reading", "read_kept", "read_dropped", "queued", "archived"],
  read_kept: ["read_kept", "archived", "reading"],
  read_dropped: ["read_dropped", "archived", "reading"],
  archived: ["archived", "reading"],
};

export function canTransition(from: PaperStatus, to: PaperStatus): boolean {
  return STATUS_TRANSITIONS[from]?.includes(to) ?? false;
}

/**
 * D5: ActionBar button set varies by current status.
 *  - active reading: full 4-action verb bar
 *  - terminal read_*:   Archive + Reopen
 *  - archived:          Reopen only
 *  - new/queued (also valid landing states): same as reading until user lands
 */
export interface ActionBarItem {
  label: string;
  /** target status the button transitions to. */
  target: PaperStatus;
  /** styling hint — `primary` for kept, `danger` for dropped. */
  variant?: "default" | "primary" | "danger" | "ghost";
}

export function actionBarFor(status: PaperStatus): ActionBarItem[] {
  switch (status) {
    case "new":
    case "queued":
    case "reading":
      return [
        { label: "Mark kept", target: "read_kept", variant: "primary" },
        { label: "Mark dropped", target: "read_dropped", variant: "danger" },
        { label: "Snooze", target: "queued", variant: "ghost" },
        { label: "Archive", target: "archived", variant: "ghost" },
      ];
    case "read_kept":
    case "read_dropped":
      return [
        { label: "Archive", target: "archived", variant: "ghost" },
        { label: "Reopen", target: "reading", variant: "default" },
      ];
    case "archived":
      return [{ label: "Reopen", target: "reading", variant: "default" }];
  }
}
