import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { ClaimCard } from "@/components/ClaimCard";
import {
  ClaimDTO,
  EquationDTO,
  FigureDTO,
  PaperDetail,
  SectionDTO,
  getPaperDetail,
} from "@/api/papers";
import { getApi } from "@/api/client";

/**
 * Speed-reading card view.
 *
 * Inverts the old "rerender the whole paper as markdown" approach: the
 * extract+interpret pipeline already produces the high-signal artifacts
 * (claims, figures, equations). This page just composes them. Anyone who
 * wants the original PDF text can still reach the backend
 * `/api/papers/<id>/markdown/` endpoint directly, but the UI no longer
 * surfaces it.
 *
 * Layout:
 *   1. Title block (paper title + arxiv id + counts)
 *   2. Abstract (if extractor identified an "Abstract" section)
 *   3. Claims as cards, sorted by type priority
 *      (proposal → result → ablation → theoretical → other)
 *      Each card's evidence chips scroll to the corresponding figure.
 *   4. Figures gallery, with claim-referenced ones first.
 */
const CLAIM_TYPE_ORDER: Record<string, number> = {
  proposal: 0,
  result: 1,
  ablation: 2,
  theoretical: 3,
};

function pickTitle(sections: SectionDTO[], fallback: string): string {
  // Heuristic: the paper title is the first level-2 (or higher-than-Abstract)
  // section produced by docling. Falls back to first section, then arxiv id.
  if (sections.length === 0) return fallback;
  const head = sections[0];
  const looksLikeStandardSection =
    /^(\d+\.|abstract|introduction|references|conclusion|appendix)/i.test(
      head.path,
    );
  if (!looksLikeStandardSection && head.path.length > 0) return head.path;
  return fallback;
}

function pickAbstract(sections: SectionDTO[]): string {
  const abs = sections.find(
    (s) => s.path.trim().toLowerCase() === "abstract",
  );
  return abs?.raw_text ?? "";
}

function partitionFigures(
  figures: FigureDTO[],
  claims: ClaimDTO[],
): { referenced: FigureDTO[]; orphan: FigureDTO[] } {
  const refs = new Set<string>();
  for (const c of claims) {
    for (const ev of c.evidences) {
      if (
        ev.material_id.includes(":fig:") ||
        ev.material_id.includes(":figure:")
      ) {
        refs.add(ev.material_id);
      }
    }
  }
  const referenced = figures.filter((f) => refs.has(f.material_id));
  const orphan = figures.filter((f) => !refs.has(f.material_id));
  return { referenced, orphan };
}

export default function PaperDetailPage() {
  const { arxivId = "" } = useParams<{ arxivId: string }>();

  const detailQ = useQuery<PaperDetail>({
    queryKey: ["paper", arxivId, "detail"],
    queryFn: () => getPaperDetail(arxivId),
    enabled: !!arxivId,
  });
  const apiBaseQ = useQuery({
    queryKey: ["api-base"],
    queryFn: async () => {
      const api = await getApi();
      return api.defaults.baseURL ?? "";
    },
    staleTime: Infinity,
  });

  const detail = detailQ.data;
  const apiBase = apiBaseQ.data ?? "";
  const rootRef = useRef<HTMLDivElement | null>(null);

  const equationsById = useMemo(() => {
    const m: Record<string, EquationDTO> = {};
    (detail?.equations ?? []).forEach((e) => (m[e.material_id] = e));
    return m;
  }, [detail]);

  const sortedClaims = useMemo(() => {
    const claims = [...(detail?.claims ?? [])];
    claims.sort((a, b) => {
      const oa = CLAIM_TYPE_ORDER[a.claim_type] ?? 9;
      const ob = CLAIM_TYPE_ORDER[b.claim_type] ?? 9;
      if (oa !== ob) return oa - ob;
      return a.claim_id.localeCompare(b.claim_id);
    });
    return claims;
  }, [detail]);

  const { referenced: refFigs, orphan: orphanFigs } = useMemo(
    () => partitionFigures(detail?.figures ?? [], detail?.claims ?? []),
    [detail],
  );

  // Highlight the figure whose evidence chip was most recently clicked.
  const [highlightId, setHighlightId] = useState<string | null>(null);
  useEffect(() => {
    if (!highlightId) return;
    const t = setTimeout(() => setHighlightId(null), 1500);
    return () => clearTimeout(t);
  }, [highlightId]);

  const onCiteClick = (materialId: string) => {
    const root = rootRef.current;
    if (!root) return;
    const el = root.querySelector<HTMLElement>(`[data-mid="${materialId}"]`);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      setHighlightId(materialId);
    }
  };

  if (!arxivId) {
    return (
      <div className="p-6 font-serif text-sm text-[var(--counter-fg)]">
        Missing arxiv id.
      </div>
    );
  }

  if (detailQ.isLoading) {
    return (
      <div className="p-12 font-serif text-[var(--fg-muted)]">Loading…</div>
    );
  }
  if (detailQ.error) {
    return (
      <div className="p-12 font-serif text-[var(--counter-fg)]">
        Failed: {(detailQ.error as Error).message}
      </div>
    );
  }
  if (!detail) {
    return (
      <div className="p-12 font-serif text-[var(--fg-muted)]">No data.</div>
    );
  }

  const title = pickTitle(detail.sections, arxivId);
  const abstract = pickAbstract(detail.sections);

  return (
    <div
      ref={rootRef}
      className="relative h-full overflow-y-auto bg-[var(--bg)]"
    >
      {/* Top bar */}
      <div className="sticky top-0 z-20 bg-[var(--bg)] border-b border-[var(--rule)]">
        <div className="max-w-[920px] mx-auto px-8 md:px-12 py-3 flex items-center justify-between">
          <Link
            to="/"
            className="font-sans text-xs uppercase tracking-[0.14em]
                       text-[var(--fg-muted)] hover:text-[var(--accent)]
                       transition-colors"
          >
            ← Today&rsquo;s brief
          </Link>
          <span className="font-mono text-[11px] text-[var(--fg-muted)] truncate max-w-[280px]">
            {arxivId}
          </span>
        </div>
      </div>

      <main className="max-w-[920px] mx-auto px-6 md:px-12 py-12 space-y-12">
        {/* Title block */}
        <header>
          <div className="font-mono text-[10px] tracking-[0.2em] uppercase text-[var(--fg-muted)] mb-3">
            speed read
          </div>
          <h1 className="font-serif text-[2.1rem] md:text-[2.6rem] leading-[1.15] font-semibold text-[var(--fg)]">
            {title}
          </h1>
          <div className="mt-4 flex flex-wrap gap-x-5 gap-y-1 text-xs font-sans text-[var(--fg-muted)]">
            <span>{detail.sections.length} sections</span>
            <span>{detail.figures.length} figures</span>
            <span>{detail.tables.length} tables</span>
            <span>{detail.equations.length} equations</span>
            <span
              className={
                detail.claims.length > 0 ? "text-[var(--accent)]" : ""
              }
            >
              {detail.claims.length} claims
            </span>
          </div>
        </header>

        {/* Abstract */}
        {abstract ? (
          <section>
            <SectionLabel>Abstract</SectionLabel>
            <p className="font-serif text-[1.05rem] leading-[1.75] text-[var(--fg)] whitespace-pre-line">
              {abstract.trim()}
            </p>
          </section>
        ) : null}

        {/* Claims */}
        <section>
          <SectionLabel>
            Key claims · {sortedClaims.length}
          </SectionLabel>
          {sortedClaims.length === 0 ? (
            <p className="font-serif text-sm text-[var(--fg-muted)] italic">
              No claims yet — interpret stage hasn&rsquo;t produced any.
            </p>
          ) : (
            <div className="flex flex-col gap-5">
              {sortedClaims.map((c) => (
                <ClaimCard
                  key={c.claim_id}
                  claim={c}
                  equationsById={equationsById}
                  onCiteClick={onCiteClick}
                />
              ))}
            </div>
          )}
        </section>

        {/* Figures */}
        {detail.figures.length > 0 ? (
          <section>
            <SectionLabel>
              Figures · {detail.figures.length}
              {refFigs.length > 0 ? (
                <span className="ml-2 text-[var(--fg-muted)] font-normal normal-case tracking-normal">
                  ({refFigs.length} cited by claims)
                </span>
              ) : null}
            </SectionLabel>
            <div className="flex flex-col gap-8">
              {[...refFigs, ...orphanFigs].map((f) => (
                <FigureBlock
                  key={f.material_id}
                  fig={f}
                  apiBase={apiBase}
                  arxivId={arxivId}
                  highlighted={highlightId === f.material_id}
                />
              ))}
            </div>
          </section>
        ) : null}
      </main>
    </div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="font-sans text-[11px] uppercase tracking-[0.16em] text-[var(--fg-muted)] mb-4 pb-2 border-b border-[var(--rule)]">
      {children}
    </h2>
  );
}

function FigureBlock({
  fig,
  apiBase,
  arxivId,
  highlighted,
}: {
  fig: FigureDTO;
  apiBase: string;
  arxivId: string;
  highlighted: boolean;
}) {
  const src = `${apiBase}/papers/${encodeURIComponent(arxivId)}/figure/${fig.seq}.png`;
  const label = fig.fig_label || `Figure ${fig.seq}`;
  return (
    <figure
      data-mid={fig.material_id}
      className={`bg-[var(--bg)] border rounded-card transition-shadow duration-200 ${
        highlighted
          ? "border-[var(--accent)] shadow-lift"
          : "border-[var(--rule)] shadow-soft"
      }`}
    >
      <div className="overflow-hidden rounded-t-card bg-[var(--bg-soft)]">
        <img
          src={src}
          alt={fig.caption || label}
          loading="lazy"
          className="w-full h-auto block"
          onError={(e) => {
            (e.currentTarget as HTMLImageElement).style.display = "none";
          }}
        />
      </div>
      <figcaption className="px-5 py-3 font-serif text-[0.92rem] leading-[1.55] text-[var(--fg-soft)]">
        <span className="font-semibold text-[var(--fg)] mr-1">{label}.</span>
        {fig.caption}
      </figcaption>
    </figure>
  );
}
