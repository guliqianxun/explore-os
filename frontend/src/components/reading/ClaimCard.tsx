import { useEffect, useRef, useState } from "react";

import type { ClaimDTO, PaperDetail } from "@/api/papers";
import { postEvent } from "@/api/state";
import { CounterSignalBadge } from "@/components/CounterSignalBadge";

import { EvidenceItem } from "./EvidenceItem";

export interface ReadingClaimCardProps {
  claim: ClaimDTO;
  detail: PaperDetail;
  /** Section-path chip click → cite jump (PdfViewer searchText). */
  onSectionJump: (sectionPath: string) => void;
  /** Per-evidence jump-in-PDF button. */
  onCiteClick: (materialId: string) => void;
}

const TYPE_BADGE: Record<string, { fg: string; bg: string }> = {
  proposal: { fg: "var(--proposal)", bg: "var(--proposal-soft)" },
  result: { fg: "var(--result)", bg: "var(--result-soft)" },
  ablation: { fg: "var(--ablation)", bg: "var(--ablation-soft)" },
  theoretical: { fg: "var(--theoretical)", bg: "var(--theoretical-soft)" },
};

/**
 * ft-029 Reading-station ClaimCard with three states (D2):
 *   A. collapsed (default) — header + body + section chip + cite chips
 *   B. expanded — full evidence list (5 templates)
 *   C. editing → ft-032 placeholder (toast)
 *
 * NOTE: this is the *station* variant; the speed-read view keeps the older,
 * width-540 ClaimCard from `@/components/ClaimCard`. Different visual budget,
 * different interactions. Sharing the file would force one to compromise.
 */
export function ReadingClaimCard({
  claim,
  detail,
  onSectionJump,
  onCiteClick,
}: ReadingClaimCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  const viewEvidenceReported = useRef(false);

  useEffect(() => {
    viewEvidenceReported.current = false;
  }, [claim.claim_id]);

  useEffect(() => {
    if (expanded && !viewEvidenceReported.current) {
      viewEvidenceReported.current = true;
      postEvent({
        viewpoint_id: claim.claim_id,
        trigger: "VIEW_EVIDENCE",
      }).catch(() => {});
    }
  }, [expanded, claim.claim_id]);

  const typeColors =
    TYPE_BADGE[claim.claim_type] ?? {
      fg: "var(--fg-soft)",
      bg: "var(--bg-muted)",
    };

  const handleEdit = () => {
    showFt032Toast("Claim editing lands in ft-032.");
  };
  const handleHide = () => {
    setMenuOpen(false);
    showFt032Toast("Hide claim lands in ft-032.");
  };
  const handleCopy = async () => {
    setMenuOpen(false);
    try {
      await navigator.clipboard.writeText(claim.text);
    } catch {
      // Fall through silently — clipboard API may be unavailable.
    }
  };

  return (
    <article
      className="bg-[var(--bg)] border border-[var(--rule)] rounded-card
                 shadow-soft p-4 space-y-3"
    >
      {/* Header: triangle + type chip + confidence + spacer + ⋯ */}
      <div className="flex items-center gap-2 text-[11px] font-sans">
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="text-[var(--fg-muted)] hover:text-[var(--fg)] w-4 text-center"
          aria-label={expanded ? "Collapse claim" : "Expand claim"}
        >
          {expanded ? "▾" : "▸"}
        </button>
        <span
          className="px-2 py-0.5 rounded-chip font-medium uppercase tracking-[0.08em]"
          style={{ color: typeColors.fg, backgroundColor: typeColors.bg }}
        >
          {claim.claim_type}
        </span>
        <span className="text-[var(--fg-muted)]">
          conf {claim.confidence.toFixed(2)}
        </span>
        <div className="flex-1" />
        <button
          type="button"
          onClick={handleEdit}
          disabled
          title="Edit claim — needs ft-032"
          className="px-1.5 text-[var(--fg-muted)] disabled:opacity-50 disabled:cursor-not-allowed"
        >
          ✎
        </button>
        <div className="relative">
          <button
            type="button"
            onClick={() => setMenuOpen((v) => !v)}
            className="px-1.5 text-[var(--fg-muted)] hover:text-[var(--fg)]"
            aria-label="More actions"
          >
            ⋯
          </button>
          {menuOpen ? (
            <div
              className="absolute right-0 top-full mt-1 w-40 z-10
                         bg-[var(--bg)] border border-[var(--rule)] rounded shadow-lift
                         text-xs font-sans"
              onMouseLeave={() => setMenuOpen(false)}
            >
              <button
                type="button"
                onClick={handleCopy}
                className="block w-full text-left px-3 py-1.5 hover:bg-[var(--bg-soft)]"
              >
                Copy claim text
              </button>
              <button
                type="button"
                onClick={handleHide}
                className="block w-full text-left px-3 py-1.5 text-[var(--fg-muted)] hover:bg-[var(--bg-soft)]"
                title="Hide — needs ft-032"
              >
                Hide claim…
              </button>
            </div>
          ) : null}
        </div>
      </div>

      {/* Body */}
      <p className="font-serif text-[0.95rem] leading-[1.6] text-[var(--fg)]">
        {claim.text}
      </p>

      {/* Source-section chip (single) */}
      {claim.source_section_path ? (
        <button
          type="button"
          onClick={() => onSectionJump(claim.source_section_path)}
          className="inline-block px-2 py-0.5 rounded-chip border border-[var(--rule)]
                     font-sans text-[11px] text-[var(--fg-muted)]
                     hover:border-[var(--accent)] hover:text-[var(--accent)]
                     transition-colors max-w-full truncate text-left"
          title={`Jump in PDF: ${claim.source_section_path}`}
        >
          § {claim.source_section_path}
        </button>
      ) : null}

      {/* Evidence section — collapsed shows count, expanded shows fan-out */}
      {claim.evidences.length > 0 ? (
        <div className="pt-2 border-t border-[var(--rule)]">
          {expanded ? (
            <>
              <div className="font-sans text-[10px] uppercase tracking-[0.16em] text-[var(--fg-muted)] mb-2">
                Evidence ({claim.evidences.length})
              </div>
              <ul className="space-y-3 list-none p-0 m-0">
                {claim.evidences.map((ev) => (
                  <EvidenceItem
                    key={ev.material_id}
                    ev={ev}
                    detail={detail}
                    onJumpInPdf={onCiteClick}
                  />
                ))}
              </ul>
            </>
          ) : (
            <button
              type="button"
              onClick={() => setExpanded(true)}
              className="font-sans text-[11px] text-[var(--fg-muted)]
                         hover:text-[var(--accent)] transition-colors"
            >
              ▸ {claim.evidences.length} evidence
              {claim.evidences.length === 1 ? "" : "s"}
            </button>
          )}
        </div>
      ) : null}

      {/* Counter-signals — always visible (red-rail design from ft-026) */}
      {claim.counter_signals.length > 0 ? (
        <div className="space-y-2 pt-1">
          {claim.counter_signals.map((cs) => (
            <CounterSignalBadge key={cs.signal_id} signal={cs} />
          ))}
        </div>
      ) : null}
    </article>
  );
}

/**
 * Lightweight DOM-only toast — avoids dragging in a toast lib for a feature
 * that disappears the moment ft-032 lands. Stacks up to 3 messages bottom-right.
 */
function showFt032Toast(message: string) {
  if (typeof document === "undefined") return;
  let host = document.getElementById("__ft032_toast_host");
  if (!host) {
    host = document.createElement("div");
    host.id = "__ft032_toast_host";
    host.style.position = "fixed";
    host.style.right = "16px";
    host.style.bottom = "16px";
    host.style.zIndex = "9999";
    host.style.display = "flex";
    host.style.flexDirection = "column";
    host.style.gap = "8px";
    host.style.pointerEvents = "none";
    document.body.appendChild(host);
  }
  const toast = document.createElement("div");
  toast.textContent = message;
  toast.style.background = "var(--bg, #fff)";
  toast.style.color = "var(--fg, #222)";
  toast.style.border = "1px solid var(--rule, #ddd)";
  toast.style.borderRadius = "6px";
  toast.style.padding = "8px 12px";
  toast.style.fontSize = "12px";
  toast.style.fontFamily = "system-ui, sans-serif";
  toast.style.boxShadow = "0 4px 14px rgba(0,0,0,0.08)";
  toast.style.transition = "opacity 300ms ease-out";
  host.appendChild(toast);
  window.setTimeout(() => {
    toast.style.opacity = "0";
  }, 2200);
  window.setTimeout(() => {
    toast.remove();
  }, 2600);
}
