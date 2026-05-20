import { useEffect } from "react";

import { CounterSignalBadge } from "./CounterSignalBadge";
import { EquationBlock } from "./EquationBlock";
import type { ClaimDTO, EquationDTO } from "@/api/papers";
import { postEvent } from "@/api/state";

export interface ClaimCardProps {
  claim: ClaimDTO;
  /** Resolves a material_id (e.g. "<arxiv>:eq:3") -> EquationDTO when available. */
  equationsById?: Record<string, EquationDTO>;
  onCiteClick: (materialId: string) => void;
}

/* ft-026 editorial palette — soft pastel chips, not saturated SaaS chips. */
const TYPE_BADGE: Record<string, { fg: string; bg: string }> = {
  proposal: { fg: "var(--proposal)", bg: "var(--proposal-soft)" },
  result: { fg: "var(--result)", bg: "var(--result-soft)" },
  ablation: { fg: "var(--ablation)", bg: "var(--ablation-soft)" },
  theoretical: { fg: "var(--theoretical)", bg: "var(--theoretical-soft)" },
};

function evidenceIcon(materialId: string): string {
  if (materialId.includes(":fig:") || materialId.includes(":figure:")) return "Fig";
  if (materialId.includes(":tbl:") || materialId.includes(":table:")) return "Tbl";
  if (materialId.includes(":eq:") || materialId.includes(":equation:")) return "Eq";
  if (materialId.includes(":sec:") || materialId.includes(":section:")) return "§";
  return "•";
}

function shortRef(materialId: string): string {
  const idx = materialId.indexOf(":");
  return idx >= 0 ? materialId.slice(idx + 1) : materialId;
}

/**
 * ft-026 ClaimCard — drawer-version layout. max-width 540, generous padding,
 * serif body 0.95rem leading-1.65. counter_signal: red left rail.
 *
 * Data structure unchanged.
 */
export function ClaimCard({ claim, equationsById, onCiteClick }: ClaimCardProps) {
  const typeColors =
    TYPE_BADGE[claim.claim_type] ?? { fg: "var(--fg-soft)", bg: "var(--bg-muted)" };

  useEffect(() => {
    postEvent({
      viewpoint_id: claim.claim_id,
      trigger: "VIEW_EVIDENCE",
    }).catch(() => {});
  }, [claim.claim_id]);

  const equationEvidences = claim.evidences.filter(
    (e) => e.material_id.includes(":eq:") || e.material_id.includes(":equation:"),
  );
  const otherEvidences = claim.evidences.filter(
    (e) =>
      !e.material_id.includes(":eq:") && !e.material_id.includes(":equation:"),
  );

  return (
    <article
      className="max-w-[540px] bg-[var(--bg)] border border-[var(--rule)]
                 rounded-card shadow-soft p-5 space-y-4"
    >
      {/* Header chips */}
      <div className="flex items-center gap-2 text-[11px] font-sans">
        <span
          className="px-2 py-0.5 rounded-chip font-medium uppercase tracking-[0.08em]"
          style={{ color: typeColors.fg, backgroundColor: typeColors.bg }}
        >
          {claim.claim_type}
        </span>
        <span className="text-[var(--fg-muted)]">
          conf {claim.confidence.toFixed(2)}
        </span>
        {claim.source_section_path ? (
          <span
            className="px-2 py-0.5 rounded-chip border border-[var(--rule)]
                       text-[var(--fg-muted)] font-normal truncate max-w-[260px]"
            title={claim.source_section_path}
          >
            {claim.source_section_path}
          </span>
        ) : null}
      </div>

      {/* Body */}
      <p className="font-serif text-[0.95rem] leading-[1.65] text-[var(--fg)]">
        {claim.text}
      </p>

      {/* Equations — editorial soft card */}
      {equationEvidences.length > 0 ? (
        <div className="space-y-3">
          {equationEvidences.map((ev) => {
            const eq = equationsById?.[ev.material_id];
            const latex = eq?.latex_or_text ?? ev.material_id;
            return (
              <div
                key={ev.material_id}
                className="bg-[var(--bg-soft)] rounded-card px-4 py-3 overflow-x-auto
                           border border-[var(--rule)] cursor-pointer
                           hover:border-[var(--accent)] transition-colors"
                onClick={() => onCiteClick(ev.material_id)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === "Enter") onCiteClick(ev.material_id);
                }}
              >
                <EquationBlock latex={latex} />
              </div>
            );
          })}
        </div>
      ) : null}

      {/* Cite chips */}
      {otherEvidences.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {otherEvidences.map((ev) => (
            <button
              key={ev.material_id}
              type="button"
              onClick={() => onCiteClick(ev.material_id)}
              className="text-[11px] font-sans px-2 py-1 rounded-chip
                         bg-[var(--bg-soft)] hover:bg-[var(--accent-soft)]
                         text-[var(--fg-soft)] hover:text-[var(--accent)]
                         border border-[var(--rule)] hover:border-[var(--accent)]
                         transition-colors"
              title={ev.material_id}
            >
              <span className="font-medium mr-1 uppercase tracking-[0.06em]">
                {evidenceIcon(ev.material_id)}
              </span>
              {shortRef(ev.material_id)}
            </button>
          ))}
        </div>
      ) : null}

      {/* Counter signals — each badge brings its own editorial red rail */}
      {claim.counter_signals.length > 0 ? (
        <div className="space-y-2">
          {claim.counter_signals.map((cs) => (
            <CounterSignalBadge key={cs.signal_id} signal={cs} />
          ))}
        </div>
      ) : null}
    </article>
  );
}
