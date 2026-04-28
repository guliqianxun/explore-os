import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { setPaperStatus } from "@/api/papers";
import type { PaperStatus } from "@/types/paper";
import { actionBarFor } from "@/lib/statusMachine";
import { cn } from "@/lib/utils";

interface ActionBarProps {
  paperKey: string;
  status: PaperStatus;
  /** When true, navigate back to / after the mutation lands. */
  navigateBackOnDone?: boolean;
}

/**
 * ft-029 D5 — bottom action bar. Plain-text buttons (no icons), set varies by
 * current status (statusMachine.actionBarFor). All button clicks fire the same
 * setPaperStatus mutation and optimistically invalidate ["papers"].
 */
export function ActionBar({
  paperKey,
  status,
  navigateBackOnDone = true,
}: ActionBarProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const mut = useMutation({
    mutationFn: (next: PaperStatus) => setPaperStatus(paperKey, next),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["papers"] });
      void queryClient.invalidateQueries({ queryKey: ["paper", paperKey] });
    },
  });

  const items = actionBarFor(status);

  const handle = (target: PaperStatus) => {
    if (mut.isPending) return;
    mut.mutate(target, {
      onSuccess: () => {
        if (navigateBackOnDone && target !== "reading") {
          // Try to preserve any ?status= filter from the previous list.
          navigate("/");
        }
      },
    });
  };

  return (
    <div className="flex items-center gap-2 px-4 py-2 border-t border-[var(--rule)] bg-[var(--bg)]">
      {items.map((it) => (
        <button
          key={it.target + it.label}
          type="button"
          disabled={mut.isPending}
          onClick={() => handle(it.target)}
          className={cn(
            "px-3 py-1.5 rounded font-sans text-sm font-medium",
            "border transition-colors",
            "disabled:opacity-50 disabled:cursor-not-allowed",
            it.variant === "primary" &&
              "border-[var(--accent)] bg-[var(--accent)] text-[var(--accent-fg)] hover:opacity-90",
            it.variant === "danger" &&
              "border-[var(--counter-fg)] text-[var(--counter-fg)] hover:bg-[var(--counter-soft,rgba(200,40,40,0.08))]",
            it.variant === "ghost" &&
              "border-transparent text-[var(--fg-muted)] hover:text-[var(--fg)]",
            (!it.variant || it.variant === "default") &&
              "border-[var(--rule)] text-[var(--fg)] hover:border-[var(--fg)]",
          )}
        >
          {it.label}
        </button>
      ))}
      {mut.isError ? (
        <span className="font-sans text-[10px] text-[var(--counter-fg)] ml-2">
          {(mut.error as Error).message}
        </span>
      ) : null}
    </div>
  );
}
