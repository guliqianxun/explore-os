import { useEffect, useRef, useState } from "react";
import { List } from "lucide-react";

import type { SectionDTO } from "@/api/papers";

interface FloatingTOCProps {
  sections: SectionDTO[];
  activeMaterialId: string | null;
  onSelect: (s: SectionDTO) => void;
}

/**
 * ft-026 left-bottom floating table-of-contents button. Click → popover
 * with section list. Click outside / ESC closes.
 */
export function FloatingTOC({
  sections,
  activeMaterialId,
  onSelect,
}: FloatingTOCProps) {
  const [open, setOpen] = useState(false);
  const popRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    const onClick = (e: MouseEvent) => {
      if (!popRef.current) return;
      if (!popRef.current.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("mousedown", onClick);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mousedown", onClick);
    };
  }, [open]);

  return (
    <div ref={popRef} className="fixed bottom-6 left-6 z-30 reading-mode-hide">
      {open ? (
        <div
          className="mb-3 w-[320px] max-h-[60vh] overflow-y-auto
                     bg-[var(--bg)] border border-[var(--rule)]
                     rounded-card shadow-lift p-3"
        >
          <div className="text-[11px] uppercase tracking-[0.14em] text-[var(--fg-muted)]
                          font-sans font-medium px-2 pb-2 border-b border-[var(--rule)]">
            Contents
          </div>
          {sections.length === 0 ? (
            <p className="px-2 py-3 text-sm text-[var(--fg-muted)] font-serif">
              No sections.
            </p>
          ) : (
            <ul className="py-2">
              {sections.map((s) => {
                const active = s.material_id === activeMaterialId;
                const indent = Math.max(0, (s.level ?? 1) - 1) * 12;
                return (
                  <li key={s.material_id}>
                    <button
                      type="button"
                      onClick={() => {
                        onSelect(s);
                        setOpen(false);
                      }}
                      style={{ paddingLeft: 8 + indent }}
                      className={`w-full text-left text-sm font-serif py-1.5 pr-2 rounded
                                  hover:bg-[var(--bg-soft)] truncate
                                  ${active
                                    ? "text-[var(--accent)] font-semibold"
                                    : "text-[var(--fg-soft)]"}`}
                      title={s.path}
                    >
                      {s.path || `§${s.seq + 1}`}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      ) : null}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label="Table of contents"
        className="h-11 w-11 rounded-full bg-[var(--bg)] border border-[var(--rule)]
                   shadow-soft hover:shadow-lift hover:border-[var(--accent)]
                   text-[var(--fg-soft)] hover:text-[var(--accent)]
                   flex items-center justify-center transition"
      >
        <List className="h-5 w-5" />
      </button>
    </div>
  );
}
