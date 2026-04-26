import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CounterSignalBadge } from "./CounterSignalBadge";
import { EquationBlock } from "./EquationBlock";
import type { ClaimDTO, EquationDTO } from "@/api/papers";

export interface ClaimCardProps {
  claim: ClaimDTO;
  /** Resolves a material_id (e.g. "<arxiv>:eq:3") -> EquationDTO when available. */
  equationsById?: Record<string, EquationDTO>;
  onCiteClick: (materialId: string) => void;
}

const TYPE_BADGE: Record<string, string> = {
  proposal: "bg-blue-100 text-blue-800 border-blue-200",
  result: "bg-green-100 text-green-800 border-green-200",
  ablation: "bg-orange-100 text-orange-800 border-orange-200",
  theoretical: "bg-purple-100 text-purple-800 border-purple-200",
};

function evidenceIcon(materialId: string): string {
  if (materialId.includes(":fig:") || materialId.includes(":figure:")) return "📊";
  if (materialId.includes(":tbl:") || materialId.includes(":table:")) return "📋";
  if (materialId.includes(":eq:") || materialId.includes(":equation:")) return "∑";
  if (materialId.includes(":sec:") || materialId.includes(":section:")) return "§";
  return "•";
}

function shortRef(materialId: string): string {
  // <arxiv>:fig:3 → fig:3
  const idx = materialId.indexOf(":");
  return idx >= 0 ? materialId.slice(idx + 1) : materialId;
}

export function ClaimCard({ claim, equationsById, onCiteClick }: ClaimCardProps) {
  const typeClass =
    TYPE_BADGE[claim.claim_type] ?? "bg-slate-100 text-slate-700 border-slate-200";

  // Split evidences: equations rendered inline as KaTeX, others as cite badges.
  const equationEvidences = claim.evidences.filter(
    (e) => e.material_id.includes(":eq:") || e.material_id.includes(":equation:"),
  );
  const otherEvidences = claim.evidences.filter(
    (e) =>
      !e.material_id.includes(":eq:") && !e.material_id.includes(":equation:"),
  );

  return (
    <Card className="p-4 space-y-3 border-blue-200/60">
      <div className="flex items-center gap-2 text-xs">
        <span
          className={`px-2 py-0.5 rounded border ${typeClass} font-medium`}
        >
          {claim.claim_type}
        </span>
        <span className="text-muted-foreground">
          conf {claim.confidence.toFixed(2)}
        </span>
        {claim.source_section_path ? (
          <Badge variant="outline" className="font-normal">
            {claim.source_section_path}
          </Badge>
        ) : null}
      </div>

      <p className="text-sm leading-relaxed text-slate-900">{claim.text}</p>

      {equationEvidences.length > 0 ? (
        <div className="space-y-2">
          {equationEvidences.map((ev) => {
            const eq = equationsById?.[ev.material_id];
            const latex = eq?.latex_or_text ?? ev.material_id;
            return (
              <div
                key={ev.material_id}
                className="bg-slate-50 rounded p-2 overflow-x-auto"
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

      {otherEvidences.length > 0 ? (
        <div className="flex flex-wrap gap-1">
          {otherEvidences.map((ev) => (
            <button
              key={ev.material_id}
              type="button"
              onClick={() => onCiteClick(ev.material_id)}
              className="text-xs px-2 py-0.5 rounded bg-slate-200 hover:bg-slate-300 transition"
              title={ev.material_id}
            >
              {evidenceIcon(ev.material_id)} {shortRef(ev.material_id)}
            </button>
          ))}
        </div>
      ) : null}

      {claim.counter_signals.length > 0 ? (
        <div className="space-y-1">
          {claim.counter_signals.map((cs) => (
            <CounterSignalBadge key={cs.signal_id} signal={cs} />
          ))}
        </div>
      ) : null}
    </Card>
  );
}
