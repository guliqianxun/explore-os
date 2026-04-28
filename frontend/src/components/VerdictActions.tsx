import type { MouseEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import type { PaperListItem } from "@/api/papers";
import type { PaperStatus } from "@/types/paper";
import { setPaperStatus } from "@/api/papers";
import { cn } from "@/lib/utils";

interface VerdictActionsProps {
  paper: PaperListItem;
  /** Lets the caller piggy-back on a successful mutation. */
  onChanged?: () => void;
  /** Layout hint — defaults to horizontal row. */
  className?: string;
}

const VERDICT_LABELS: Record<PaperStatus, string> = {
  new: "New",
  queued: "Queued",
  reading: "Reading",
  read_kept: "Kept",
  read_dropped: "Dropped",
  archived: "Archived",
};

interface VerdictContext {
  /**
   * Captured cache snapshot keyed by stable JSON for rollback. Each entry is
   * `[serializedQueryKey, items]`; on error we restore each entry verbatim.
   */
  previous: Array<[string, PaperListItem[]]>;
}

/**
 * ft-028 Inbox verdict triplet: [Skip] [Queue] [Read now].
 *
 *  - Skip      → status = read_dropped
 *  - Queue     → status = queued
 *  - Read now  → status = reading + nav to /papers/<arxiv_id>
 *
 * Optimistic update mutates every cached `["papers", ...]` query so the
 * StatusFilterBar and the active card both update without a refetch round-trip.
 */
export function VerdictActions({
  paper,
  onChanged,
  className,
}: VerdictActionsProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const mutation = useMutation<void, Error, PaperStatus, VerdictContext>({
    mutationFn: async (next) => {
      // Prefer the stable key when the backend has assigned one; fall back
      // to arxiv_id (the legacy URL still resolves per ft-028 § URL 解析).
      const id = paper.paper_key || paper.arxiv_id;
      await setPaperStatus(id, next);
    },
    onMutate: async (next) => {
      await queryClient.cancelQueries({ queryKey: ["papers"] });
      const snapshots = queryClient.getQueriesData<PaperListItem[]>({
        queryKey: ["papers"],
      });
      const previous: Array<[string, PaperListItem[]]> = [];
      for (const [key, items] of snapshots) {
        if (!items) continue;
        previous.push([JSON.stringify(key), items]);
        queryClient.setQueryData<PaperListItem[]>(
          key,
          items.map((p) =>
            p.arxiv_id === paper.arxiv_id ? { ...p, status: next } : p,
          ),
        );
      }
      return { previous };
    },
    onError: (_err, _next, ctx) => {
      // Restore each snapshot we captured. If the cache shape moved under us
      // the subsequent invalidate will heal anything we miss.
      if (ctx) {
        for (const [serialized, items] of ctx.previous) {
          const key = JSON.parse(serialized) as readonly unknown[];
          queryClient.setQueryData<PaperListItem[]>(key, items);
        }
      }
      void queryClient.invalidateQueries({ queryKey: ["papers"] });
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["papers"] });
      onChanged?.();
    },
  });

  // Archived papers are terminal: show a quiet badge instead of buttons.
  if (paper.status === "archived") {
    return (
      <div
        className={cn(
          "inline-flex items-center px-2.5 py-1 rounded-chip border",
          "border-[var(--rule)] bg-[var(--bg-soft)]",
          "font-sans text-[10px] tracking-[0.18em] uppercase text-[var(--fg-muted)]",
          className,
        )}
      >
        {VERDICT_LABELS.archived}
      </div>
    );
  }

  const handle = (next: PaperStatus, navigateTo?: string) => {
    if (mutation.isPending) return;
    mutation.mutate(next, {
      onSuccess: () => {
        if (navigateTo) navigate(navigateTo);
      },
    });
  };

  // Stop propagation so clicks don't bubble to the parent <Link> wrapper
  // (PaperCard / HeroPaperCard wrap the whole article in a Link to detail).
  const stopBubble = (e: MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  return (
    <div
      onClick={stopBubble}
      className={cn("inline-flex items-center gap-1.5", className)}
    >
      <VerdictButton
        label="Skip"
        active={paper.status === "read_dropped"}
        disabled={mutation.isPending}
        onClick={() => handle("read_dropped")}
      />
      <VerdictButton
        label="Queue"
        active={paper.status === "queued"}
        disabled={mutation.isPending}
        onClick={() => handle("queued")}
      />
      <VerdictButton
        label="Read now"
        accent
        active={paper.status === "reading"}
        disabled={mutation.isPending}
        onClick={() =>
          handle("reading", `/papers/${encodeURIComponent(paper.arxiv_id)}`)
        }
      />
    </div>
  );
}

interface VerdictButtonProps {
  label: string;
  active?: boolean;
  accent?: boolean;
  disabled?: boolean;
  onClick: () => void;
}

function VerdictButton({
  label,
  active = false,
  accent = false,
  disabled = false,
  onClick,
}: VerdictButtonProps) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={cn(
        "px-2.5 py-1 rounded-chip border font-sans",
        "text-[10px] tracking-[0.18em] uppercase transition-colors",
        "disabled:opacity-50 disabled:cursor-not-allowed",
        accent
          ? active
            ? "border-[var(--accent)] bg-[var(--accent)] text-[var(--accent-fg)]"
            : "border-[var(--accent)] text-[var(--accent)] hover:bg-[var(--accent)] hover:text-[var(--accent-fg)]"
          : active
            ? "border-[var(--fg)] bg-[var(--fg)] text-[var(--bg)]"
            : "border-[var(--rule)] text-[var(--fg-soft)] hover:border-[var(--fg)] hover:text-[var(--fg)]",
      )}
    >
      {label}
    </button>
  );
}
