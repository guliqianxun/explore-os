import { Link } from "react-router-dom";

import type { PaperListItem } from "@/api/papers";
import { VerdictActions } from "@/components/VerdictActions";

interface PaperCardProps {
  paper: PaperListItem;
  /** Optional API base for figure thumbnail URL. */
  apiBase?: string;
  /** Optional lead paragraph (abstract / first claim text). */
  lead?: string;
  /** ft-033: 领域关键词 chips（最多 4 个）. */
  keywords?: string[];
}

/**
 * ft-026 feed-style PaperCard. Editorial: serif title, lead snippet,
 * meta line (claim count + figures), small thumbnail of figure 1.
 *
 * ft-028 adds a `<VerdictActions />` triplet on the right that mutates
 * `UserPaperStatus` without leaving the list view.
 */
export function PaperCard({ paper, apiBase, lead, keywords }: PaperCardProps) {
  const thumb =
    paper.n_figures > 0 && apiBase
      ? `${apiBase}/papers/${encodeURIComponent(paper.arxiv_id)}/figure/1.png`
      : null;

  const displayTitle = paper.title || paper.arxiv_id;

  return (
    <article
      className="grid grid-cols-[1fr_120px] gap-5 py-7
                 border-b border-[var(--rule)] last:border-b-0"
    >
      <div className="min-w-0">
        <Link
          to={`/papers/${encodeURIComponent(paper.arxiv_id)}`}
          className="group block"
        >
          <div className="font-mono text-[11px] text-[var(--fg-muted)] mb-2 truncate">
            {paper.arxiv_id}
          </div>
          <h3
            className="font-serif text-[1.35rem] leading-[1.25] font-semibold
                       text-[var(--fg)] group-hover:text-[var(--accent)]
                       transition-colors"
          >
            {displayTitle}
          </h3>
          {lead ? (
            <p
              className="mt-3 font-serif text-[0.98rem] leading-[1.65]
                         text-[var(--fg-soft)] line-clamp-2"
            >
              {lead}
            </p>
          ) : null}
          {keywords && keywords.length > 0 ? (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {keywords.slice(0, 4).map((k) => (
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
          <div className="mt-3 flex flex-wrap gap-x-4 text-xs font-sans text-[var(--fg-muted)]">
            <span>{paper.n_sections} sec</span>
            <span>{paper.n_figures} fig</span>
            <span>{paper.n_tables} tbl</span>
            <span className={paper.n_claims > 0 ? "text-[var(--accent)]" : ""}>
              {paper.n_claims} claims
            </span>
            {paper.n_comments > 0 ? <span>{paper.n_comments} notes</span> : null}
          </div>
        </Link>
        <div className="mt-4">
          <VerdictActions paper={paper} />
        </div>
      </div>
      {thumb ? (
        <Link
          to={`/papers/${encodeURIComponent(paper.arxiv_id)}`}
          className="self-start"
          aria-hidden="true"
          tabIndex={-1}
        >
          <div
            className="aspect-[4/3] overflow-hidden rounded-card
                       bg-[var(--bg-soft)] border border-[var(--rule)]"
          >
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
      ) : (
        <div />
      )}
    </article>
  );
}
