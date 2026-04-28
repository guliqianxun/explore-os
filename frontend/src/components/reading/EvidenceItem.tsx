import { useMemo, useState } from "react";
import { InlineMath, BlockMath } from "react-katex";

import type {
  ClaimEvidenceDTO,
  EquationDTO,
  FigureDTO,
  PaperDetail,
  SectionDTO,
  TableDTO,
} from "@/api/papers";
import { getApi } from "@/api/client";
import { useQuery } from "@tanstack/react-query";

interface EvidenceItemProps {
  ev: ClaimEvidenceDTO;
  detail: PaperDetail;
  /** Triggers the cross-link into the PdfViewer (scroll/highlight/search). */
  onJumpInPdf: (materialId: string) => void;
}

type Resolved =
  | { kind: "section"; sec: SectionDTO }
  | { kind: "figure"; fig: FigureDTO }
  | { kind: "table"; tbl: TableDTO }
  | { kind: "equation"; eq: EquationDTO }
  | { kind: "citation"; raw: string }
  | { kind: "unknown"; raw: string };

function resolveEvidence(
  materialId: string,
  detail: PaperDetail,
): Resolved {
  // Order: figure / table / section / equation / citation; the underlying
  // material_id format is "<arxiv>:<kind>:<key>" so we could parse the
  // segment, but checking each list is robust against minor format drift.
  const fig = detail.figures.find((f) => f.material_id === materialId);
  if (fig) return { kind: "figure", fig };
  const tbl = detail.tables.find((t) => t.material_id === materialId);
  if (tbl) return { kind: "table", tbl };
  const sec = detail.sections.find((s) => s.material_id === materialId);
  if (sec) return { kind: "section", sec };
  const eq = detail.equations.find((e) => e.material_id === materialId);
  if (eq) return { kind: "equation", eq };
  if (
    materialId.includes(":cite:") ||
    materialId.includes(":citation:") ||
    materialId.includes(":bib:")
  ) {
    return { kind: "citation", raw: materialId };
  }
  return { kind: "unknown", raw: materialId };
}

/**
 * ft-029 D2.evidence — renders a single piece of evidence backing a claim.
 * Five templates per material kind (section / figure / table / equation /
 * citation). All emit a right-aligned `[→ jump in PDF]` button; PdfViewer
 * picks the right cross-ref behavior (scroll+box vs text search).
 */
export function EvidenceItem({ ev, detail, onJumpInPdf }: EvidenceItemProps) {
  const resolved = useMemo(
    () => resolveEvidence(ev.material_id, detail),
    [ev.material_id, detail],
  );

  return (
    <li className="border-l-2 border-[var(--rule)] pl-3 py-1 space-y-1">
      <EvidenceBody resolved={resolved} ev={ev} detail={detail} />
      <div className="flex justify-end">
        <button
          type="button"
          onClick={() => onJumpInPdf(ev.material_id)}
          className="font-sans text-[10px] uppercase tracking-[0.14em]
                     text-[var(--fg-muted)] hover:text-[var(--accent)]
                     transition-colors"
          title={ev.material_id}
        >
          → jump in PDF
        </button>
      </div>
    </li>
  );
}

function EvidenceBody({
  resolved,
  ev,
  detail,
}: {
  resolved: Resolved;
  ev: ClaimEvidenceDTO;
  detail: PaperDetail;
}) {
  switch (resolved.kind) {
    case "section":
      return <SectionEvidence sec={resolved.sec} />;
    case "figure":
      return <FigureEvidence fig={resolved.fig} arxivId={detail.arxiv_id} />;
    case "table":
      return <TableEvidence tbl={resolved.tbl} />;
    case "equation":
      return <EquationEvidence eq={resolved.eq} />;
    case "citation":
      return <CitationEvidence raw={resolved.raw} />;
    case "unknown":
      return (
        <div className="font-sans text-xs text-[var(--fg-muted)]">
          {ev.material_id}
        </div>
      );
  }
}

function SectionEvidence({ sec }: { sec: SectionDTO }) {
  const text = sec.raw_text.length > 400
    ? sec.raw_text.slice(0, 400) + "…"
    : sec.raw_text;
  return (
    <div className="space-y-1">
      <div className="font-sans text-[11px] uppercase tracking-[0.1em] text-[var(--fg-muted)]">
        § {sec.path} <span className="normal-case tracking-normal">(section)</span>
      </div>
      <div className="font-serif text-[0.88rem] leading-[1.6] text-[var(--fg-soft)] whitespace-pre-line">
        {text}
      </div>
    </div>
  );
}

function FigureEvidence({
  fig,
  arxivId,
}: {
  fig: FigureDTO;
  arxivId: string;
}) {
  const apiBaseQ = useQuery({
    queryKey: ["api-base"],
    queryFn: async () => {
      const api = await getApi();
      return api.defaults.baseURL ?? "";
    },
    staleTime: Infinity,
  });
  const apiBase = apiBaseQ.data ?? "";
  const src = apiBase
    ? `${apiBase}/papers/${encodeURIComponent(arxivId)}/figure/${fig.seq}.png`
    : "";
  const label = fig.fig_label || `Fig ${fig.seq}`;
  return (
    <div className="space-y-1">
      <div className="font-sans text-[11px] uppercase tracking-[0.1em] text-[var(--fg-muted)] flex justify-between">
        <span>
          {label} <span className="normal-case tracking-normal">(figure)</span>
        </span>
        <span className="text-[var(--fg-muted)]">page {fig.page}</span>
      </div>
      {src ? (
        <img
          src={src}
          alt={fig.caption || label}
          loading="lazy"
          className="max-w-full max-h-[140px] object-contain border border-[var(--rule)] rounded-card bg-[var(--bg-soft)]"
          onError={(e) => {
            (e.currentTarget as HTMLImageElement).style.display = "none";
          }}
          title={fig.caption}
        />
      ) : null}
      {fig.caption ? (
        <div className="font-serif text-[0.8rem] leading-[1.5] text-[var(--fg-muted)] line-clamp-2">
          {fig.caption}
        </div>
      ) : null}
    </div>
  );
}

function TableEvidence({ tbl }: { tbl: TableDTO }) {
  const label = tbl.tbl_label || `Tab ${tbl.seq}`;
  const text = tbl.raw_text.length > 240
    ? tbl.raw_text.slice(0, 240) + "…"
    : tbl.raw_text;
  return (
    <div className="space-y-1">
      <div className="font-sans text-[11px] uppercase tracking-[0.1em] text-[var(--fg-muted)] flex justify-between">
        <span>
          {label} <span className="normal-case tracking-normal">(table)</span>
        </span>
        <span className="text-[var(--fg-muted)]">page {tbl.page}</span>
      </div>
      {tbl.caption ? (
        <div className="font-serif text-[0.85rem] leading-[1.5] text-[var(--fg-soft)]">
          {tbl.caption}
        </div>
      ) : null}
      {text ? (
        <pre className="font-mono text-[0.75rem] leading-[1.45] text-[var(--fg-muted)] overflow-x-auto bg-[var(--bg-soft)] rounded p-2 whitespace-pre-wrap">
          {text}
        </pre>
      ) : null}
    </div>
  );
}

function EquationEvidence({ eq }: { eq: EquationDTO }) {
  const [errored, setErrored] = useState(false);
  const isInline = eq.inline_or_display === "inline";
  return (
    <div className="space-y-1">
      <div className="font-sans text-[11px] uppercase tracking-[0.1em] text-[var(--fg-muted)]">
        Eq {eq.seq} <span className="normal-case tracking-normal">(equation)</span>
      </div>
      <div className="bg-[var(--bg-soft)] rounded px-2 py-1 overflow-x-auto">
        {errored ? (
          <code className="font-mono text-[0.8rem]">{eq.latex_or_text}</code>
        ) : (
          <KatexSafe
            latex={eq.latex_or_text}
            inline={isInline}
            onError={() => setErrored(true)}
          />
        )}
      </div>
    </div>
  );
}

/** Wrapper around react-katex that swallows errors via a ref'd boundary. */
function KatexSafe({
  latex,
  inline,
  onError,
}: {
  latex: string;
  inline: boolean;
  onError: () => void;
}) {
  try {
    return inline ? (
      <InlineMath math={latex} errorColor="var(--counter-fg)" />
    ) : (
      <BlockMath math={latex} errorColor="var(--counter-fg)" />
    );
  } catch {
    onError();
    return <code className="font-mono text-[0.8rem]">{latex}</code>;
  }
}

function CitationEvidence({ raw }: { raw: string }) {
  // material_id like "<arxiv>:cite:Smith2020"; show the bibkey + raw id hover.
  const bibkey = raw.split(":").slice(2).join(":") || raw;
  return (
    <div className="space-y-0.5" title={raw}>
      <div className="font-sans text-[11px] uppercase tracking-[0.1em] text-[var(--fg-muted)]">
        [{bibkey}]{" "}
        <span className="normal-case tracking-normal">(citation)</span>
      </div>
    </div>
  );
}
