import { useState } from "react";
import { Link } from "react-router-dom";

import type { PaperListItem } from "@/api/papers";
import { VerdictActions } from "@/components/VerdictActions";

interface HeroPaperCardProps {
  paper: PaperListItem;
  /** Optional API base for figure thumbnail URL (e.g. http://127.0.0.1:9001). */
  apiBase?: string;
  /** Optional lead paragraph (abstract / first claim text). */
  lead?: string;
  /** ft-033: 领域关键词 chips（来自 PaperBrief.keywords，最多 5 个）. */
  keywords?: string[];
  /** ft-033: 英文原文 abstract，折叠区在 lead 下方按需展开. */
  abstractEn?: string;
}

/**
 * ft-026 PaperListPage hero card. Wide editorial banner: headline title,
 * lead paragraph, author hint (TBD when API exposes), thumbnail (figure 1).
 *
 * ft-028 embeds `<VerdictActions />` directly under the meta row so the
 * top-of-feed paper can be triaged without leaving the list view.
 */
export function HeroPaperCard({
  paper, apiBase, lead, keywords, abstractEn,
}: HeroPaperCardProps) {
  const [showEn, setShowEn] = useState(false);
  const thumb =
    paper.n_figures > 0 && apiBase
      ? `${apiBase}/papers/${encodeURIComponent(paper.arxiv_id)}/figure/1.png`
      : null;

  const ablationHint =
    paper.n_claims > 0 ? `${paper.n_claims} claims` : "claims pending";

  const displayTitle = paper.title || paper.arxiv_id;

  return (
    <article
      className="grid grid-cols-1 md:grid-cols-[2fr_1fr] gap-6 md:gap-8
                 border-b border-[var(--rule)] pb-10 mb-10
                 transition-colors"
    >
      <div className="min-w-0">
        <Link
          to={`/papers/${encodeURIComponent(paper.arxiv_id)}`}
          className="group block"
        >
          <div
            className="flex items-center gap-2 text-[11px] uppercase tracking-[0.14em]
                       font-sans font-medium text-[var(--accent)] mb-3"
          >
            <span>Featured</span>
            <span className="text-[var(--fg-muted)]">·</span>
            <span className="text-[var(--fg-muted)] normal-case tracking-normal font-mono">
              {paper.arxiv_id}
            </span>
          </div>
          <h2
            className="font-serif text-[2.1rem] md:text-[2.4rem] leading-[1.15]
                       font-semibold text-[var(--fg)]
                       group-hover:text-[var(--accent)] transition-colors"
          >
            {displayTitle}
          </h2>
          {lead ? (
            <p
              className="mt-4 font-serif text-[1.05rem] leading-[1.7] text-[var(--fg)]
                         whitespace-pre-line"
            >
              {lead}
            </p>
          ) : null}
          {abstractEn ? (
            <div className="mt-3">
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setShowEn((v) => !v);
                }}
                className="text-[10px] font-sans uppercase tracking-[0.16em]
                           text-[var(--fg-soft)] hover:text-[var(--accent)]
                           transition-colors"
              >
                {showEn ? "▾ Hide original abstract" : "▸ Show original abstract"}
              </button>
              {showEn ? (
                <p
                  className="mt-2 font-serif text-[0.95rem] leading-[1.7]
                             text-[var(--fg-soft)] whitespace-pre-line
                             border-l-2 border-[var(--rule)] pl-3"
                >
                  {abstractEn.trim()}
                </p>
              ) : null}
            </div>
          ) : null}
          {keywords && keywords.length > 0 ? (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {keywords.slice(0, 5).map((k) => (
                <span
                  key={k}
                  className="px-2 py-0.5 rounded-chip border border-[var(--rule)]
                             text-[10px] font-sans uppercase tracking-[0.12em]
                             text-[var(--fg-muted)]"
                >
                  {k}
                </span>
              ))}
            </div>
          ) : null}
          <div className="mt-5 flex flex-wrap gap-x-4 gap-y-1 text-xs font-sans text-[var(--fg-muted)]">
            <span>{paper.n_sections} sections</span>
            <span>{paper.n_figures} figures</span>
            <span>{paper.n_tables} tables</span>
            <span className="text-[var(--accent)]">{ablationHint}</span>
            {paper.n_comments > 0 ? <span>{paper.n_comments} notes</span> : null}
          </div>
        </Link>
        <div className="mt-5">
          <VerdictActions paper={paper} />
        </div>
      </div>
      {thumb ? (
        <Link
          to={`/papers/${encodeURIComponent(paper.arxiv_id)}`}
          className="order-first md:order-last group"
          aria-hidden="true"
          tabIndex={-1}
        >
          <div
            className="aspect-[4/3] overflow-hidden rounded-card bg-[var(--bg-soft)]
                       border border-[var(--rule)]"
          >
            <img
              src={thumb}
              alt=""
              loading="lazy"
              className="w-full h-full object-cover transition-transform duration-500
                         group-hover:scale-[1.02]"
              onError={(e) => {
                (e.currentTarget as HTMLImageElement).style.display = "none";
              }}
            />
          </div>
        </Link>
      ) : null}
    </article>
  );
}
