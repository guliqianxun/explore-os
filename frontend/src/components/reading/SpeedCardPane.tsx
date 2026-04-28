import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import type {
  ClaimDTO,
  FigureDTO,
  PaperDetail,
  SectionDTO,
} from "@/api/papers";
import { getApi } from "@/api/client";

import { ReadingClaimCard } from "./ClaimCard";

interface SpeedCardPaneProps {
  detail: PaperDetail;
  /** Forwarded to ClaimCard / figure-thumb clicks → PdfViewer ref. */
  onCiteClick: (materialId: string) => void;
  /** Section-path-only clicks (from claim source_section_path). */
  onSectionJump: (sectionPath: string) => void;
}

const CLAIM_TYPE_ORDER: Record<string, number> = {
  proposal: 0,
  result: 1,
  ablation: 2,
  theoretical: 3,
};

function pickAbstract(sections: SectionDTO[]): string {
  const abs = sections.find(
    (s) => s.path.trim().toLowerCase() === "abstract",
  );
  return abs?.raw_text ?? "";
}

/**
 * ft-029 left pane in ReadingStation. Tighter than SpeedReadView (the panel
 * is ~28% wide by default), so figures collapse into a thumbnail grid and
 * claim cards switch to the new ReadingClaimCard with three-state evidence.
 */
export default function SpeedCardPane({
  detail,
  onCiteClick,
  onSectionJump,
}: SpeedCardPaneProps) {
  const sortedClaims = useMemo(() => {
    const claims = [...detail.claims];
    claims.sort((a, b) => {
      const oa = CLAIM_TYPE_ORDER[a.claim_type] ?? 9;
      const ob = CLAIM_TYPE_ORDER[b.claim_type] ?? 9;
      if (oa !== ob) return oa - ob;
      return a.claim_id.localeCompare(b.claim_id);
    });
    return claims;
  }, [detail]);

  const abstract = pickAbstract(detail.sections);
  const title = detail.title || detail.arxiv_id;

  return (
    <div className="h-full overflow-y-auto bg-[var(--bg)] px-4 py-5 space-y-6">
      <header>
        <div className="font-mono text-[10px] tracking-[0.2em] uppercase text-[var(--fg-muted)] mb-2">
          speed read
        </div>
        <h1 className="font-serif text-[1.3rem] leading-[1.25] font-semibold text-[var(--fg)]">
          {title}
        </h1>
        <div className="mt-2 flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] font-sans text-[var(--fg-muted)] uppercase tracking-[0.1em]">
          <span>{detail.sections.length} sec</span>
          <span>{detail.figures.length} fig</span>
          <span>{detail.tables.length} tbl</span>
          <span>{detail.equations.length} eq</span>
          <span
            className={
              detail.claims.length > 0 ? "text-[var(--accent)]" : ""
            }
          >
            {detail.claims.length} claims
          </span>
        </div>
      </header>

      {abstract ? (
        <section>
          <PaneLabel>Abstract</PaneLabel>
          <p className="font-serif text-[0.92rem] leading-[1.65] text-[var(--fg)] whitespace-pre-line">
            {abstract.trim()}
          </p>
        </section>
      ) : null}

      <section>
        <PaneLabel>Key claims · {sortedClaims.length}</PaneLabel>
        {sortedClaims.length === 0 ? (
          <p className="font-serif text-sm text-[var(--fg-muted)] italic">
            No claims yet.
          </p>
        ) : (
          <div className="flex flex-col gap-3">
            {sortedClaims.map((c: ClaimDTO) => (
              <ReadingClaimCard
                key={c.claim_id}
                claim={c}
                detail={detail}
                onCiteClick={onCiteClick}
                onSectionJump={onSectionJump}
              />
            ))}
          </div>
        )}
      </section>

      {detail.figures.length > 0 ? (
        <section>
          <PaneLabel>Figures · {detail.figures.length}</PaneLabel>
          <FigureGrid
            figures={detail.figures}
            arxivId={detail.arxiv_id}
            onCiteClick={onCiteClick}
          />
        </section>
      ) : null}
    </div>
  );
}

function PaneLabel({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="font-sans text-[10px] uppercase tracking-[0.16em] text-[var(--fg-muted)] mb-3 pb-1.5 border-b border-[var(--rule)]">
      {children}
    </h2>
  );
}

function FigureGrid({
  figures,
  arxivId,
  onCiteClick,
}: {
  figures: FigureDTO[];
  arxivId: string;
  onCiteClick: (materialId: string) => void;
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
  const [errored, setErrored] = useState<Set<string>>(new Set());

  return (
    <div className="grid grid-cols-2 gap-2">
      {figures.map((f) => {
        const src = `${apiBase}/papers/${encodeURIComponent(arxivId)}/figure/${f.seq}.png`;
        const isErr = errored.has(f.material_id);
        const label = f.fig_label || `Fig ${f.seq}`;
        return (
          <button
            key={f.material_id}
            type="button"
            onClick={() => onCiteClick(f.material_id)}
            className="group flex flex-col gap-1 text-left
                       border border-[var(--rule)] rounded-card overflow-hidden
                       bg-[var(--bg-soft)] hover:border-[var(--accent)]
                       transition-colors"
            title={f.caption}
          >
            <div className="aspect-[4/3] flex items-center justify-center overflow-hidden">
              {isErr || !apiBase ? (
                <span className="font-mono text-[10px] text-[var(--fg-muted)]">
                  {label}
                </span>
              ) : (
                <img
                  src={src}
                  alt={f.caption || label}
                  loading="lazy"
                  className="w-full h-full object-contain"
                  onError={() =>
                    setErrored((s) => new Set(s).add(f.material_id))
                  }
                />
              )}
            </div>
            <div className="px-2 py-1 font-sans text-[10px] text-[var(--fg-muted)] flex justify-between">
              <span>{label}</span>
              <span>p.{f.page}</span>
            </div>
          </button>
        );
      })}
    </div>
  );
}
