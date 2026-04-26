import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { listPapers } from "@/api/papers";
import { getApi } from "@/api/client";
import { HeroPaperCard } from "@/components/HeroPaperCard";
import { PaperCard } from "@/components/PaperCard";

/**
 * ft-026 PaperListPage. Editorial feed:
 *   - "Today's brief" headline + date
 *   - Hero card (latest / first paper)
 *   - Remaining cards stacked feed-style
 *
 * No real publish-date signal is exposed by the API yet; we treat the
 * server's listing order as the chronological order (newest first).
 */
export default function PaperListPage() {
  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ["papers"],
    queryFn: listPapers,
  });

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

  const [hero, ...rest] = data ?? [];

  return (
    <div className="h-full overflow-y-auto bg-[var(--bg)]">
      <div className="max-w-[920px] mx-auto px-8 md:px-12 py-12">
        {/* Masthead */}
        <header className="flex items-end justify-between border-b-2 border-[var(--fg)]
                           pb-4 mb-10">
          <div>
            <div className="font-mono text-[10px] tracking-[0.2em] uppercase
                            text-[var(--fg-muted)] mb-2">
              explore-os
            </div>
            <h1 className="font-serif text-4xl md:text-5xl font-semibold
                           text-[var(--fg)] leading-none">
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

        {/* Body */}
        {isLoading ? (
          <p className="font-serif text-[var(--fg-muted)]">Loading…</p>
        ) : error ? (
          <p className="font-serif text-[var(--counter-fg)]">
            Failed to load papers: {(error as Error).message}
          </p>
        ) : !data || data.length === 0 ? (
          <div className="font-serif text-[var(--fg-muted)] py-16 text-center">
            <p className="text-lg italic">The desk is empty.</p>
            <p className="mt-2 text-sm">
              Trigger a run from the Run tab to surface today&rsquo;s reading.
            </p>
          </div>
        ) : (
          <>
            {/* Date marker */}
            <div className="flex items-center gap-3 mb-8">
              <div className="h-px flex-1 bg-[var(--rule)]" />
              <span className="font-mono text-[11px] uppercase tracking-[0.16em]
                               text-[var(--fg-muted)]">
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
