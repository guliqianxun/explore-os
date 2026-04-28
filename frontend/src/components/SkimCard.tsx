import { Link } from "react-router-dom";

import type { PaperListItem } from "@/api/papers";
import { VerdictActions } from "@/components/VerdictActions";

interface SkimCardProps {
  paper: PaperListItem;
  /** Optional lead paragraph (one-liner). */
  lead?: string;
}

/**
 * Brief-view 速读 row — single-line title + meta + verdict actions.
 *
 * Used in PaperListPage `filter='brief'` for the "速读" group (status=new).
 * Density target: 5–8 rows per viewport vs PaperCard's ~2.
 */
export function SkimCard({ paper, lead }: SkimCardProps) {
  const displayTitle = paper.title || paper.arxiv_id;
  return (
    <article
      className="flex items-start gap-3 py-3
                 border-b border-[var(--rule)] last:border-b-0"
    >
      <div className="flex-1 min-w-0">
        <Link
          to={`/papers/${encodeURIComponent(paper.arxiv_id)}`}
          className="group block"
        >
          <div className="flex items-baseline gap-3">
            <h3
              className="font-serif text-[1rem] leading-snug font-medium
                         text-[var(--fg)] group-hover:text-[var(--accent)]
                         transition-colors truncate"
            >
              {displayTitle}
            </h3>
            <span className="font-mono text-[10px] text-[var(--fg-muted)] shrink-0">
              {paper.arxiv_id}
            </span>
          </div>
          {lead ? (
            <p
              className="mt-1 font-serif text-[0.9rem] leading-snug
                         text-[var(--fg-soft)] line-clamp-1"
            >
              {lead}
            </p>
          ) : null}
          <div className="mt-1 flex flex-wrap gap-x-3 text-[10px] font-sans uppercase tracking-[0.08em] text-[var(--fg-muted)]">
            <span>{paper.n_sections} sec</span>
            <span>{paper.n_figures} fig</span>
            {paper.n_claims > 0 ? (
              <span className="text-[var(--accent)]">{paper.n_claims} claims</span>
            ) : null}
            {paper.n_comments > 0 ? <span>{paper.n_comments} notes</span> : null}
          </div>
        </Link>
      </div>
      <div className="shrink-0">
        <VerdictActions paper={paper} />
      </div>
    </article>
  );
}
