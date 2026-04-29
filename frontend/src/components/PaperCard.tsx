import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { getPaperDetail, type PaperDetail, type PaperListItem } from "@/api/papers";
import { VerdictActions } from "@/components/VerdictActions";

interface PaperCardProps {
  paper: PaperListItem;
  /** Optional API base for figure thumbnail URL. */
  apiBase?: string;
  /** abstract_zh — shown behind the "show 中文 abstract" toggle. */
  lead?: string;
  /** paper.keywords — author-supplied (not LLM). chips below title. */
  keywords?: string[];
  /** paper.abstract — English original, visible by default. */
  abstractEn?: string;
}

/**
 * Compact academic-feed card with poster-style figure wrap (墙报式).
 *   Figure thumb floats top-right; title / keywords / abstract flow around it.
 *   Meta cards + verdict actions clear the float and sit below.
 */
export function PaperCard({
  paper, apiBase, lead, keywords, abstractEn,
}: PaperCardProps) {
  const [showZh, setShowZh] = useState(false);
  const thumb =
    paper.n_figures > 0 && apiBase
      ? `${apiBase}/papers/${encodeURIComponent(paper.arxiv_id)}/figure/1.png`
      : null;

  const displayTitle = paper.title || paper.arxiv_id;
  const detailHref = `/papers/${encodeURIComponent(paper.arxiv_id)}`;

  return (
    <article className="py-5 border-b border-[var(--rule)] last:border-b-0">
      <div className="font-mono text-[10px] tracking-[0.04em]
                      text-[var(--fg-muted)] mb-1.5 truncate">
        {paper.arxiv_id}
      </div>

      {/* Floated figure wraps with the body content below */}
      {thumb ? (
        <Link
          to={detailHref}
          aria-hidden="true"
          tabIndex={-1}
          className="float-right ml-5 mb-2 w-[180px] block"
        >
          <div className="aspect-[4/3] overflow-hidden rounded-card
                          bg-[var(--bg-soft)] border border-[var(--rule)]">
            <img
              src={thumb}
              alt=""
              loading="lazy"
              className="w-full h-full object-cover"
              onError={(e) => {
                (e.currentTarget as HTMLImageElement).style.display = "none";
              }}
            />
          </div>
        </Link>
      ) : null}

      <Link to={detailHref} className="group block">
        <h3 className="font-serif text-[1.18rem] leading-[1.3] font-semibold
                       text-[var(--fg)] group-hover:text-[var(--accent)]
                       transition-colors">
          {displayTitle}
        </h3>
        {keywords && keywords.length > 0 ? (
          <div className="mt-2 flex flex-wrap gap-1">
            {keywords.slice(0, 6).map((k) => (
              <span
                key={k}
                className="px-1.5 py-px rounded-chip
                           bg-[var(--bg-soft)] text-[10.5px] font-sans
                           text-[var(--fg-soft)] lowercase"
              >
                {k}
              </span>
            ))}
          </div>
        ) : null}
        {abstractEn ? (
          <p className="mt-2 font-serif text-[0.92rem] leading-[1.6]
                        text-[var(--fg-soft)] whitespace-pre-line line-clamp-5">
            {abstractEn.trim()}
          </p>
        ) : null}
      </Link>

      {lead ? (
        <div className="mt-2">
          <button
            type="button"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setShowZh((v) => !v);
            }}
            className="text-[10px] font-sans uppercase tracking-[0.14em]
                       text-[var(--fg-soft)] hover:text-[var(--accent)]
                       transition-colors"
          >
            {showZh ? "▾ Hide 中文 abstract" : "▸ Show 中文 abstract"}
          </button>
          {showZh ? (
            <p className="mt-1.5 font-serif text-[0.92rem] leading-[1.6]
                          text-[var(--fg)] whitespace-pre-line
                          border-l-2 border-[var(--rule)] pl-3">
              {lead}
            </p>
          ) : null}
        </div>
      ) : null}

      <div className="clear-both" />
      <MetaCards paper={paper} />
      <div className="mt-3">
        <VerdictActions paper={paper} />
      </div>
    </article>
  );
}

type TabName = "materials" | "claims" | "summary";

/**
 * 3-tab meta strip. Click a tab to expand a panel below with the full
 * content (lazy-fetches paper detail on first click). Click again to close.
 */
export function MetaCards({ paper }: { paper: PaperListItem }) {
  const [active, setActive] = useState<TabName | null>(null);

  const detailQ = useQuery({
    queryKey: ["paperDetail", paper.arxiv_id],
    queryFn: () => getPaperDetail(paper.arxiv_id),
    enabled: active !== null,
    staleTime: 60_000,
  });

  const toggle = (t: TabName) => setActive((prev) => (prev === t ? null : t));

  return (
    <div className="mt-3">
      <div className="grid grid-cols-3 gap-2">
        <TabButton
          active={active === "materials"}
          onClick={() => toggle("materials")}
          label="Materials"
          summary={`${paper.n_figures} fig · ${paper.n_tables} tbl · ${paper.n_sections} sec`}
        />
        <TabButton
          active={active === "claims"}
          onClick={() => toggle("claims")}
          label="Claims"
          summary={
            paper.n_comments > 0
              ? `${paper.n_claims} claims · ${paper.n_comments} notes`
              : `${paper.n_claims} claims`
          }
        />
        <TabButton
          active={active === "summary"}
          onClick={() => toggle("summary")}
          label="AI Summary"
          summary={paper.has_brief ? "ready" : "not generated"}
        />
      </div>
      {active !== null ? (
        <div className="mt-2 rounded-card border border-[var(--rule)]
                        bg-[var(--bg-soft)]/40 p-3">
          {detailQ.isLoading ? (
            <p className="text-[12px] italic text-[var(--fg-muted)]">Loading…</p>
          ) : detailQ.error ? (
            <p className="text-[12px] text-[var(--counter-fg)]">
              Failed: {(detailQ.error as Error).message}
            </p>
          ) : detailQ.data ? (
            <TabPanel
              tab={active}
              detail={detailQ.data}
              apiBase={undefined}
              keyInnovation={paper.key_innovation}
            />
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function TabButton({
  active, onClick, label, summary,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  summary: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`block w-full text-left rounded-card border px-2.5 py-1.5
                  transition-colors ${
                    active
                      ? "border-[var(--accent)] bg-[var(--bg-soft)]"
                      : "border-[var(--rule)] hover:border-[var(--accent)]"
                  }`}
    >
      <div className="text-[9.5px] font-sans uppercase tracking-[0.12em]
                      text-[var(--fg-muted)] mb-0.5">
        {label}
      </div>
      <div className="text-[12px] font-mono text-[var(--fg)] truncate">
        {summary}
      </div>
    </button>
  );
}

function TabPanel({
  tab, detail, keyInnovation,
}: {
  tab: TabName;
  detail: PaperDetail;
  apiBase?: string;
  keyInnovation?: string[];
}) {
  if (tab === "materials") {
    return <MaterialsPanel detail={detail} />;
  }
  if (tab === "claims") {
    return <ClaimsPanel detail={detail} />;
  }
  return <SummaryPanel detail={detail} fallbackInnovation={keyInnovation ?? []} />;
}

function MaterialsPanel({ detail }: { detail: PaperDetail }) {
  const figs = detail.figures ?? [];
  const tbls = detail.tables ?? [];
  const eqs = detail.equations ?? [];
  if (figs.length === 0 && tbls.length === 0 && eqs.length === 0) {
    return (
      <p className="text-[12px] italic text-[var(--fg-muted)]">
        No materials extracted.
      </p>
    );
  }
  return (
    <div className="space-y-2 text-[12px]">
      {figs.length > 0 ? (
        <Section label={`Figures (${figs.length})`}>
          <ul className="space-y-1 text-[var(--fg-soft)]">
            {figs.slice(0, 6).map((f, i) => (
              <li key={i} className="line-clamp-1">
                <span className="font-mono text-[10.5px] text-[var(--fg-muted)] mr-2">
                  Fig {f.seq ?? i + 1}
                </span>
                {f.caption || "(no caption)"}
              </li>
            ))}
          </ul>
        </Section>
      ) : null}
      {tbls.length > 0 ? (
        <Section label={`Tables (${tbls.length})`}>
          <ul className="space-y-1 text-[var(--fg-soft)]">
            {tbls.slice(0, 6).map((t, i) => (
              <li key={i} className="line-clamp-1">
                <span className="font-mono text-[10.5px] text-[var(--fg-muted)] mr-2">
                  Tbl {t.seq ?? i + 1}
                </span>
                {t.caption || "(no caption)"}
              </li>
            ))}
          </ul>
        </Section>
      ) : null}
      {eqs.length > 0 ? (
        <Section label={`Equations (${eqs.length})`}>
          <ul className="space-y-0.5 text-[var(--fg-soft)] flex flex-wrap gap-x-3 gap-y-0.5">
            {eqs.slice(0, 12).map((e, i) => (
              <li key={i} className="font-mono text-[11px]">
                {e.eq_label || `eq ${i + 1}`}
              </li>
            ))}
          </ul>
        </Section>
      ) : null}
    </div>
  );
}

function ClaimsPanel({ detail }: { detail: PaperDetail }) {
  const claims = detail.claims ?? [];
  if (claims.length === 0) {
    return (
      <p className="text-[12px] italic text-[var(--fg-muted)]">
        No claims extracted yet.
      </p>
    );
  }
  return (
    <ul className="space-y-2 text-[12px] text-[var(--fg-soft)] leading-[1.5]">
      {claims.slice(0, 8).map((c) => (
        <li key={c.claim_id}>
          <div className="text-[var(--fg)] line-clamp-2">{c.text || c.text_en}</div>
          <div className="mt-0.5 font-mono text-[10.5px] text-[var(--fg-muted)]">
            {c.claim_type} · {c.evidences?.length ?? 0} evid
            {c.counter_signals?.length ? ` · ${c.counter_signals.length} counter` : ""}
          </div>
        </li>
      ))}
    </ul>
  );
}

function SummaryPanel({
  detail, fallbackInnovation,
}: {
  detail: PaperDetail;
  fallbackInnovation: string[];
}) {
  const brief = detail.brief;
  if (!brief) {
    if (fallbackInnovation.length === 0) {
      return (
        <p className="text-[12px] italic text-[var(--fg-muted)]">
          Brief not generated.
        </p>
      );
    }
    return (
      <ul className="space-y-1 text-[12px] text-[var(--fg-soft)]">
        {fallbackInnovation.map((line, i) => (
          <li key={i}>· {line}</li>
        ))}
      </ul>
    );
  }
  return (
    <div className="space-y-2 text-[12px] leading-[1.55]">
      {brief.method_summary_zh ? (
        <Section label="Method">
          <p className="text-[var(--fg)]">{brief.method_summary_zh}</p>
        </Section>
      ) : null}
      {brief.key_innovation && brief.key_innovation.length > 0 ? (
        <Section label="Key innovations">
          <ul className="space-y-0.5 text-[var(--fg-soft)]">
            {brief.key_innovation.map((line, i) => (
              <li key={i}>· {line}</li>
            ))}
          </ul>
        </Section>
      ) : null}
      {brief.limitations && brief.limitations.length > 0 ? (
        <Section label="Limitations">
          <ul className="space-y-0.5 text-[var(--fg-soft)]">
            {brief.limitations.map((line, i) => (
              <li key={i}>· {line}</li>
            ))}
          </ul>
        </Section>
      ) : null}
      {brief.for_you ? (
        <Section label={`For you (${brief.perspective_used || "researcher"})`}>
          <p className="text-[var(--fg)] italic">{brief.for_you}</p>
        </Section>
      ) : null}
    </div>
  );
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-[9.5px] font-sans uppercase tracking-[0.12em]
                      text-[var(--fg-muted)] mb-1">
        {label}
      </div>
      {children}
    </div>
  );
}
