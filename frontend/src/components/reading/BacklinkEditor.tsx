import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  addPaperBacklink,
  listPaperBacklinks,
  removePaperBacklink,
  searchPapersTypeahead,
} from "@/api/papers";
import type { BacklinkEdge } from "@/types/paper";

interface BacklinkEditorProps {
  paperKey: string;
}

/**
 * ft-029 NotesPane > Backlinks tab.
 *   - Outgoing: list with [×] remove
 *   - Incoming: read-only list (the other paper owns the edge)
 *   - Bottom search box: typeahead via `?q=` icontains, click result to add
 */
export function BacklinkEditor({ paperKey }: BacklinkEditorProps) {
  const queryClient = useQueryClient();
  const q = useQuery({
    queryKey: ["paper-backlinks", paperKey],
    queryFn: () => listPaperBacklinks(paperKey),
    enabled: !!paperKey,
  });
  const data = q.data ?? { outgoing: [], incoming: [] };

  const removeMut = useMutation({
    mutationFn: (bid: number) => removePaperBacklink(paperKey, bid),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["paper-backlinks", paperKey],
      });
    },
  });

  const addMut = useMutation({
    mutationFn: (dst: string) => addPaperBacklink(paperKey, dst),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["paper-backlinks", paperKey],
      });
    },
  });

  return (
    <div className="px-4 py-3 space-y-5 overflow-y-auto h-full">
      <BacklinkSection
        title="Outgoing"
        subtitle="papers I cite / reference"
        edges={data.outgoing}
        direction="out"
        onRemove={(id) => removeMut.mutate(id)}
        canRemove
      />
      <BacklinkSection
        title="Incoming"
        subtitle="papers that reference me (read-only)"
        edges={data.incoming}
        direction="in"
        onRemove={() => undefined}
        canRemove={false}
      />
      <div className="pt-3 border-t border-[var(--rule)]">
        <BacklinkAdd
          excludeKeys={
            new Set(
              data.outgoing
                .map((e) => e.dst_key)
                .filter((k): k is string => Boolean(k))
                .concat([paperKey]),
            )
          }
          onPick={(key) => addMut.mutate(key)}
          isPending={addMut.isPending}
        />
      </div>
    </div>
  );
}

function BacklinkSection({
  title,
  subtitle,
  edges,
  direction,
  onRemove,
  canRemove,
}: {
  title: string;
  subtitle: string;
  edges: BacklinkEdge[];
  direction: "in" | "out";
  onRemove: (id: number) => void;
  canRemove: boolean;
}) {
  return (
    <section className="space-y-2">
      <div className="font-sans text-[10px] uppercase tracking-[0.16em] text-[var(--fg-muted)]">
        {title} ({edges.length})
        <span className="ml-2 normal-case tracking-normal italic opacity-70">
          {subtitle}
        </span>
      </div>
      {edges.length === 0 ? (
        <div className="font-serif text-xs italic text-[var(--fg-muted)]">
          None.
        </div>
      ) : (
        <ul className="space-y-1.5">
          {edges.map((e) => {
            const otherKey =
              direction === "out" ? e.dst_key : e.src_key;
            const otherTitle =
              direction === "out" ? e.dst_title : e.src_title;
            return (
              <li
                key={e.id}
                className="flex items-start gap-2 px-2 py-1.5 rounded border border-[var(--rule)] bg-[var(--bg)]"
              >
                <div className="flex-1 min-w-0">
                  <div className="font-mono text-[10px] text-[var(--fg-muted)]">
                    {otherKey}
                  </div>
                  <div className="font-serif text-[0.88rem] leading-[1.4] text-[var(--fg)] truncate">
                    {otherTitle ?? otherKey ?? "(unknown)"}
                  </div>
                  {e.relation || e.note ? (
                    <div className="font-sans text-[10px] text-[var(--fg-muted)] mt-0.5">
                      {e.relation}
                      {e.relation && e.note ? " · " : null}
                      {e.note}
                    </div>
                  ) : null}
                </div>
                {canRemove ? (
                  <button
                    type="button"
                    onClick={() => onRemove(e.id)}
                    className="text-[var(--fg-muted)] hover:text-[var(--counter-fg)] px-1 self-center"
                    aria-label="Remove backlink"
                  >
                    ×
                  </button>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

function BacklinkAdd({
  excludeKeys,
  onPick,
  isPending,
}: {
  excludeKeys: Set<string>;
  onPick: (paperKey: string) => void;
  isPending: boolean;
}) {
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");

  useEffect(() => {
    const t = setTimeout(() => setDebounced(q.trim()), 200);
    return () => clearTimeout(t);
  }, [q]);

  const searchQ = useQuery({
    queryKey: ["backlink-search", debounced],
    queryFn: () => searchPapersTypeahead(debounced, 5),
    enabled: debounced.length >= 2,
  });

  const candidates = useMemo(
    () =>
      (searchQ.data ?? []).filter(
        (p) => p.paper_key && !excludeKeys.has(p.paper_key),
      ),
    [searchQ.data, excludeKeys],
  );

  return (
    <div className="space-y-2">
      <div className="font-sans text-[10px] uppercase tracking-[0.16em] text-[var(--fg-muted)]">
        Add backlink
      </div>
      <input
        type="search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="search paper title…"
        className="w-full px-2 py-1.5 rounded border border-[var(--rule)] bg-[var(--bg)] text-sm focus:outline-none focus:border-[var(--accent)]"
      />
      {debounced.length >= 2 ? (
        <ul className="space-y-1">
          {searchQ.isLoading ? (
            <li className="font-sans text-xs text-[var(--fg-muted)]">
              Searching…
            </li>
          ) : candidates.length === 0 ? (
            <li className="font-sans text-xs italic text-[var(--fg-muted)]">
              No matches.
            </li>
          ) : (
            candidates.map((p) => (
              <li key={p.paper_key || p.arxiv_id}>
                <button
                  type="button"
                  disabled={isPending || !p.paper_key}
                  onClick={() => p.paper_key && onPick(p.paper_key)}
                  className="w-full text-left px-2 py-1.5 rounded border border-[var(--rule)]
                             hover:border-[var(--accent)] hover:bg-[var(--bg-soft)]
                             disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <div className="font-mono text-[10px] text-[var(--fg-muted)]">
                    {p.paper_key || p.arxiv_id}
                  </div>
                  <div className="font-serif text-[0.85rem] truncate">
                    {p.title}
                  </div>
                </button>
              </li>
            ))
          )}
        </ul>
      ) : null}
    </div>
  );
}
