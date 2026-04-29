import { useCallback, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";

import { listPapers, type PaperListItem } from "@/api/papers";
import { getApi } from "@/api/client";
import { HeroPaperCard } from "@/components/HeroPaperCard";
import { PaperCard } from "@/components/PaperCard";
import { SkimCard } from "@/components/SkimCard";
import { StatusFilterBar } from "@/components/StatusFilterBar";
import type { PaperStatus, StatusFilter } from "@/types/paper";

/**
 * ft-026 PaperListPage. Editorial feed:
 *   - "Today's brief" headline + date
 *   - Hero card (latest / first paper)
 *   - Remaining cards stacked feed-style
 *
 * ft-028 layered on top:
 *   - Sticky `StatusFilterBar` (chips: New / Queued / Reading / Read / All)
 *   - URL-state via `?status=` (default `new`)
 *   - `Read` chip aggregates `read_kept + read_dropped` (two-fetch fanout
 *     until backend supports `?status=read` natively)
 *   - Empty state for `status=new` links straight to `?status=all`
 */

const FILTER_VALUES: StatusFilter[] = [
  "brief",
  "all",
  "new",
  "queued",
  "reading",
  "read",
  "read_kept",
  "read_dropped",
  "archived",
];

function parseStatusParam(raw: string | null): StatusFilter {
  if (!raw) return "brief";
  return (FILTER_VALUES as string[]).includes(raw)
    ? (raw as StatusFilter)
    : "brief";
}

/** Fetcher that handles the `read` aggregate by issuing two requests. */
async function fetchPapersForFilter(
  filter: StatusFilter,
): Promise<PaperListItem[]> {
  if (filter === "read") {
    const [kept, dropped] = await Promise.all([
      listPapers({ status: "read_kept" }),
      listPapers({ status: "read_dropped" }),
    ]);
    return [...kept, ...dropped];
  }
  if (filter === "all" || filter === "brief") {
    // Brief view filters client-side to [new, queued, reading].
    return listPapers({ status: "all" });
  }
  return listPapers({ status: filter });
}

export default function PaperListPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const filter = parseStatusParam(searchParams.get("status"));

  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ["papers", filter],
    queryFn: () => fetchPapersForFilter(filter),
  });

  // Counts: backend doesn't expose a `/papers/counts/` endpoint yet, so we
  // fetch all papers once (cheap on a single-user desktop) and bucket
  // client-side. This keeps the chips honest across status changes too.
  const allQ = useQuery({
    queryKey: ["papers", "all"],
    queryFn: () => listPapers({ status: "all" }),
  });

  const counts = useMemo(() => {
    const out: Partial<Record<StatusFilter, number>> = {};
    const all = allQ.data;
    if (!all) return out;
    out.all = all.length;
    const buckets: Record<PaperStatus, number> = {
      new: 0,
      queued: 0,
      reading: 0,
      read_kept: 0,
      read_dropped: 0,
      archived: 0,
    };
    for (const p of all) buckets[p.status] += 1;
    out.new = buckets.new;
    out.queued = buckets.queued;
    out.reading = buckets.reading;
    out.read_kept = buckets.read_kept;
    out.read_dropped = buckets.read_dropped;
    out.archived = buckets.archived;
    out.read = buckets.read_kept + buckets.read_dropped;
    return out;
  }, [allQ.data]);

  const handleFilterChange = useCallback(
    (next: StatusFilter) => {
      const params = new URLSearchParams(searchParams);
      if (next === "new") {
        params.delete("status");
      } else {
        params.set("status", next);
      }
      setSearchParams(params, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  const apiBaseQ = useQuery({
    queryKey: ["api-base"],
    queryFn: async () => {
      const api = await getApi();
      return api.defaults.baseURL ?? "";
    },
    staleTime: Infinity,
  });
  const apiBase = apiBaseQ.data ?? "";

  const today = useMemo(
    () =>
      new Date().toLocaleDateString("en-US", {
        year: "numeric",
        month: "long",
        day: "numeric",
      }),
    [],
  );

  const isBrief = filter === "brief";

  // Brief view: split into two groups by status.
  // 主要 = reading|queued (user has signaled intent)
  // 速读 = new (undecided)
  // archived/read_* are hidden in brief.
  const briefGroups = useMemo(() => {
    if (!isBrief || !data) return null;
    const primary = data.filter(
      (p) => p.status === "reading" || p.status === "queued",
    );
    const skim = data.filter((p) => p.status === "new");
    return { primary, skim };
  }, [isBrief, data]);

  const [hero, ...rest] = data ?? [];

  return (
    <div className="h-full overflow-y-auto bg-[var(--bg)]">
      <div className="max-w-[920px] mx-auto px-8 md:px-12 py-12">
        {/* Masthead */}
        <header
          className="flex items-end justify-between border-b-2 border-[var(--fg)]
                     pb-4 mb-6"
        >
          <div>
            <div
              className="font-mono text-[10px] tracking-[0.2em] uppercase
                         text-[var(--fg-muted)] mb-2"
            >
              explore-os
            </div>
            <h1
              className="font-serif text-4xl md:text-5xl font-semibold
                         text-[var(--fg)] leading-none"
            >
              Today&rsquo;s brief
            </h1>
          </div>
          <div className="flex flex-col items-end gap-2">
            <span className="font-serif italic text-sm text-[var(--fg-muted)]">
              {today}
            </span>
            <button
              type="button"
              onClick={() => refetch()}
              disabled={isFetching}
              className="text-[11px] font-sans uppercase tracking-[0.14em]
                         px-3 py-1 rounded-chip border border-[var(--rule)]
                         text-[var(--fg-soft)] hover:border-[var(--accent)]
                         hover:text-[var(--accent)] transition disabled:opacity-50"
            >
              {isFetching ? "Refreshing" : "Refresh"}
            </button>
          </div>
        </header>

        {/* Sticky status filter — sits just under the masthead. */}
        <div
          className="sticky top-0 z-10 -mx-8 md:-mx-12 px-8 md:px-12 py-3
                     bg-[var(--bg)]/95 backdrop-blur border-b border-[var(--rule)]
                     mb-8"
        >
          <StatusFilterBar
            current={filter}
            counts={counts}
            onChange={handleFilterChange}
          />
        </div>

        {/* Body */}
        {isLoading ? (
          <p className="font-serif text-[var(--fg-muted)]">Loading…</p>
        ) : error ? (
          <p className="font-serif text-[var(--counter-fg)]">
            Failed to load papers: {(error as Error).message}
          </p>
        ) : !data || data.length === 0 ? (
          <EmptyState filter={filter} onViewAll={() => handleFilterChange("all")} />
        ) : isBrief && briefGroups ? (
          <BriefView
            primary={briefGroups.primary}
            skim={briefGroups.skim}
            apiBase={apiBase}
            today={today}
            onViewAll={() => handleFilterChange("all")}
          />
        ) : (
          <>
            {/* Date marker */}
            <div className="flex items-center gap-3 mb-8">
              <div className="h-px flex-1 bg-[var(--rule)]" />
              <span
                className="font-mono text-[11px] uppercase tracking-[0.16em]
                           text-[var(--fg-muted)]"
              >
                {today}
              </span>
              <div className="h-px flex-1 bg-[var(--rule)]" />
            </div>

            {hero ? <HeroPaperCard paper={hero} apiBase={apiBase} /> : null}

            {rest.length > 0 ? (
              <div className="mt-2">
                {rest.map((p) => (
                  <PaperCard key={p.arxiv_id} paper={p} apiBase={apiBase} />
                ))}
              </div>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}

interface BriefViewProps {
  primary: PaperListItem[];
  skim: PaperListItem[];
  apiBase: string;
  today: string;
  onViewAll: () => void;
}

/**
 * Email-style two-section brief: 主要论文 (status in [reading, queued],
 * full editorial cards) + 速读 (status=new, compact rows). archived/read_*
 * are omitted; user can switch to the corresponding chip to see them.
 */
function BriefView({
  primary,
  skim,
  apiBase,
  today,
  onViewAll,
}: BriefViewProps) {
  if (primary.length === 0 && skim.length === 0) {
    return (
      <div className="font-serif text-[var(--fg-muted)] py-16 text-center">
        <p className="text-lg italic">No papers in your brief.</p>
        <p className="mt-2 text-sm">
          <button
            type="button"
            onClick={onViewAll}
            className="underline decoration-[var(--rule)] underline-offset-4
                       hover:text-[var(--accent)] hover:decoration-[var(--accent)]
                       transition-colors"
          >
            View all papers &rarr;
          </button>
        </p>
      </div>
    );
  }
  return (
    <>
      {/* Date marker */}
      <div className="flex items-center gap-3 mb-8">
        <div className="h-px flex-1 bg-[var(--rule)]" />
        <span
          className="font-mono text-[11px] uppercase tracking-[0.16em]
                     text-[var(--fg-muted)]"
        >
          {today}
        </span>
        <div className="h-px flex-1 bg-[var(--rule)]" />
      </div>

      {/* 主要论文 — full editorial cards */}
      {primary.length > 0 ? (
        <section className="mb-12">
          <SectionHeader label="主要论文" count={primary.length} />
          {primary.map((p, i) => {
            // lead = abstract_zh（默认可见）；abstractEn 走 toggle。
            const lead = p.abstract_zh || p.tldr_zh || undefined;
            // chip 主源：作者 keywords 优先；空则 fallback 到 brief.keywords (LLM)
            const chipKeywords =
              p.keywords.length > 0 ? p.keywords : p.brief_keywords;
            return i === 0 ? (
              <HeroPaperCard
                key={p.arxiv_id}
                paper={p}
                apiBase={apiBase}
                lead={lead}
                keywords={chipKeywords}
                abstractEn={p.abstract_en}
              />
            ) : (
              <PaperCard
                key={p.arxiv_id}
                paper={p}
                apiBase={apiBase}
                lead={lead}
                keywords={chipKeywords}
                abstractEn={p.abstract_en}
              />
            );
          })}
        </section>
      ) : null}

      {/* 速读 — compact one-liner rows */}
      {skim.length > 0 ? (
        <section>
          <SectionHeader label="速读" count={skim.length} />
          <div>
            {skim.map((p) => {
              const skimLead = p.abstract_zh || p.tldr_zh || undefined;
              return (
                <SkimCard
                  key={p.arxiv_id}
                  paper={p}
                  lead={skimLead}
                  keywords={p.keywords}
                  abstractEn={p.abstract_en}
                />
              );
            })}
          </div>
        </section>
      ) : null}
    </>
  );
}

function SectionHeader({ label, count }: { label: string; count: number }) {
  return (
    <div className="flex items-baseline gap-3 mb-5">
      <h2 className="font-serif text-[1.6rem] font-semibold text-[var(--fg)]">
        {label}
      </h2>
      <span className="font-mono text-[12px] text-[var(--fg-muted)]">
        ({count})
      </span>
      <div className="flex-1 h-px bg-[var(--rule)] ml-2" />
    </div>
  );
}

interface EmptyStateProps {
  filter: StatusFilter;
  onViewAll: () => void;
}

function EmptyState({ filter, onViewAll }: EmptyStateProps) {
  if (filter === "new") {
    return (
      <div className="font-serif text-[var(--fg-muted)] py-16 text-center">
        <p className="text-lg italic">No new papers.</p>
        <p className="mt-2 text-sm">
          <button
            type="button"
            onClick={onViewAll}
            className="underline decoration-[var(--rule)] underline-offset-4
                       hover:text-[var(--accent)] hover:decoration-[var(--accent)]
                       transition-colors"
          >
            View all papers &rarr;
          </button>
        </p>
      </div>
    );
  }

  return (
    <div className="font-serif text-[var(--fg-muted)] py-16 text-center">
      <p className="text-lg italic">The desk is empty.</p>
      <p className="mt-2 text-sm">
        Trigger a run from the{" "}
        <Link
          to="/ingest"
          className="underline decoration-[var(--rule)] underline-offset-4
                     hover:text-[var(--accent)] hover:decoration-[var(--accent)]"
        >
          Ingest
        </Link>{" "}
        tab to surface today&rsquo;s reading.
      </p>
    </div>
  );
}
