import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { setPaperStatus } from "@/api/papers";
import type { PaperStatus } from "@/types/paper";
import { PAPER_STATUSES, canTransition } from "@/lib/statusMachine";
import { cn } from "@/lib/utils";

interface StatusPillProps {
  paperKey: string;
  status: PaperStatus;
}

/**
 * ft-029 D8 — top-right power-user direct status switcher. Shows the full
 * 5-state set; transitions ruled out by `canTransition` are disabled rather
 * than hidden so the user can see they exist.
 */
export function StatusPill({ paperKey, status }: StatusPillProps) {
  const [open, setOpen] = useState(false);
  const queryClient = useQueryClient();
  const wrapRef = useRef<HTMLDivElement | null>(null);

  const mut = useMutation({
    mutationFn: (next: PaperStatus) => setPaperStatus(paperKey, next),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["papers"] });
      void queryClient.invalidateQueries({ queryKey: ["paper", paperKey] });
    },
  });

  // Click-outside.
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  const onPick = (s: PaperStatus) => {
    setOpen(false);
    if (s === status) return;
    if (!canTransition(status, s)) return;
    mut.mutate(s);
  };

  return (
    <div ref={wrapRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="px-2.5 py-1 rounded-chip border border-[var(--rule)]
                   bg-[var(--bg)] hover:border-[var(--fg)]
                   font-sans text-[11px] uppercase tracking-[0.14em]
                   text-[var(--fg-soft)]"
      >
        {status} ▾
      </button>
      {open ? (
        <div
          className="absolute right-0 top-full mt-1 w-40 z-30
                     bg-[var(--bg)] border border-[var(--rule)] rounded
                     shadow-lift py-1"
        >
          {PAPER_STATUSES.map((s) => {
            const allowed = s === status || canTransition(status, s);
            const active = s === status;
            return (
              <button
                key={s}
                type="button"
                disabled={!allowed}
                onClick={() => onPick(s)}
                className={cn(
                  "block w-full text-left px-3 py-1.5 font-sans text-xs",
                  "uppercase tracking-[0.14em]",
                  active && "text-[var(--accent)]",
                  !active && allowed && "text-[var(--fg)] hover:bg-[var(--bg-soft)]",
                  !allowed && "text-[var(--fg-muted)] opacity-50 cursor-not-allowed",
                )}
              >
                {s}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
