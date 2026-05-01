import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import type { PaperListItem } from "@/api/papers";
import { MetaCards } from "@/components/PaperCard";
import { PaperLinks } from "@/components/PaperLinks";
import { VerdictActions } from "@/components/VerdictActions";

interface HeroPaperCardProps {
  paper: PaperListItem;
  apiBase?: string;
  /** abstract_zh — Chinese behind toggle. */
  lead?: string;
  /** paper.keywords — author-supplied. */
  keywords?: string[];
  /** paper.abstract — English original, visible by default. */
  abstractEn?: string;
}

/**
 * Hero variant of the wall-poster card. Larger title + figure thumb,
 * same float-right wrap pattern so the abstract flows around the figure.
 */
export function HeroPaperCard({
  paper, apiBase, lead, keywords, abstractEn,
}: HeroPaperCardProps) {
  const { t } = useTranslation();
  const [showZh, setShowZh] = useState(false);
  const thumb =
    paper.n_figures > 0 && apiBase
      ? `${apiBase}/papers/${encodeURIComponent(paper.arxiv_id)}/figure/1.png`
      : null;

  const displayTitle = paper.title || paper.arxiv_id;
  const detailHref = `/papers/${encodeURIComponent(paper.arxiv_id)}`;

  return (
    <article className="border-b border-[var(--rule)] pb-8 mb-8">
      <div className="flex items-center justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 text-[10.5px] uppercase tracking-[0.14em]
                        font-sans font-medium text-[var(--accent)]">
          <span>Featured</span>
          <span className="text-[var(--fg-muted)]">·</span>
          <span className="text-[var(--fg-muted)] normal-case tracking-normal font-mono">
            {paper.arxiv_id}
          </span>
        </div>
        <PaperLinks arxivId={paper.arxiv_id} />
      </div>

      {/* Floated figure for poster wrap */}
      {thumb ? (
        <Link
          to={detailHref}
          aria-hidden="true"
          tabIndex={-1}
          className="float-right ml-6 mb-3 w-[260px] block"
        >
          <div className="aspect-[4/3] overflow-hidden rounded-card
                          bg-[var(--bg-soft)] border border-[var(--rule)]">
            <img
              src={thumb}
              alt=""
              loading="lazy"
              className="w-full h-full object-cover transition-transform duration-500
                         hover:scale-[1.02]"
              onError={(e) => {
                (e.currentTarget as HTMLImageElement).style.display = "none";
              }}
            />
          </div>
        </Link>
      ) : null}

      <Link to={detailHref} className="group block">
        <h2 className="font-serif text-[1.7rem] md:text-[1.9rem] leading-[1.18]
                       font-semibold text-[var(--fg)]
                       group-hover:text-[var(--accent)] transition-colors">
          {displayTitle}
        </h2>
        {keywords && keywords.length > 0 ? (
          <div className="mt-3 flex flex-wrap gap-1">
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
          <p className="mt-3 font-serif text-[1rem] leading-[1.7]
                        text-[var(--fg)] whitespace-pre-line">
            {abstractEn.trim()}
          </p>
        ) : null}
      </Link>

      {lead ? (
        <div className="mt-3">
          <button
            type="button"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setShowZh((v) => !v);
            }}
            className="text-[10px] font-sans uppercase tracking-[0.16em]
                       text-[var(--fg-soft)] hover:text-[var(--accent)]
                       transition-colors"
          >
            {showZh ? t("papers.tabs.hide_zh") : t("papers.tabs.show_zh")}
          </button>
          {showZh ? (
            <p className="mt-2 font-serif text-[0.96rem] leading-[1.7]
                          text-[var(--fg)] whitespace-pre-line
                          border-l-2 border-[var(--rule)] pl-3">
              {lead}
            </p>
          ) : null}
        </div>
      ) : null}

      <div className="clear-both" />
      <MetaCards paper={paper} />
      <div className="mt-4">
        <VerdictActions paper={paper} />
      </div>
    </article>
  );
}
