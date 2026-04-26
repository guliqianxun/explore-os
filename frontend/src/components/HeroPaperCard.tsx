import { Link } from "react-router-dom";

import type { PaperListItem } from "@/api/papers";

interface HeroPaperCardProps {
  paper: PaperListItem;
  /** Optional API base for figure thumbnail URL (e.g. http://127.0.0.1:9001). */
  apiBase?: string;
  /** Optional lead paragraph (abstract / first claim text). */
  lead?: string;
}

/**
 * ft-026 PaperListPage hero card. Wide editorial banner: headline title,
 * lead paragraph, author hint (TBD when API exposes), thumbnail (figure 1).
 */
export function HeroPaperCard({ paper, apiBase, lead }: HeroPaperCardProps) {
  const thumb =
    paper.n_figures > 0 && apiBase
      ? `${apiBase}/papers/${encodeURIComponent(paper.arxiv_id)}/figure/1.png`
      : null;

  const ablationHint =
    paper.n_claims > 0 ? `${paper.n_claims} claims` : "claims pending";

  return (
    <Link
      to={`/papers/${encodeURIComponent(paper.arxiv_id)}`}
      className="group block"
    >
      <article
        className="grid grid-cols-1 md:grid-cols-[1fr_280px] gap-6 md:gap-8
                   border-b border-[var(--rule)] pb-10 mb-10
                   transition-colors"
      >
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.14em]
                          font-sans font-medium text-[var(--accent)] mb-3">
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
            {paper.arxiv_id}
          </h2>
          {lead ? (
            <p className="mt-4 font-serif text-[1.05rem] leading-[1.7] text-[var(--fg-soft)]
                          line-clamp-4">
              {lead}
            </p>
          ) : null}
          <div className="mt-5 flex flex-wrap gap-x-4 gap-y-1 text-xs font-sans text-[var(--fg-muted)]">
            <span>{paper.n_sections} sections</span>
            <span>{paper.n_figures} figures</span>
            <span>{paper.n_tables} tables</span>
            <span className="text-[var(--accent)]">{ablationHint}</span>
          </div>
        </div>
        {thumb ? (
          <div className="order-first md:order-last">
            <div className="aspect-[4/3] overflow-hidden rounded-card bg-[var(--bg-soft)]
                            border border-[var(--rule)]">
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
          </div>
        ) : null}
      </article>
    </Link>
  );
}
