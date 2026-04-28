import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { regeneratePaperBrief, type PaperBriefDTO } from "@/api/papers";

interface BriefSectionProps {
  paperKey: string;
  arxivId: string;
  brief: PaperBriefDTO | null | undefined;
}

/**
 * ft-033: editorial brief block — abstract_zh + keywords + for_you +
 * key_innovation. Shown at top of SpeedReadView (above raw abstract).
 *
 * No-brief state: a single [Generate brief] button that POSTs regenerate
 * (synchronous, ~5–15s LLM call).
 */
export function BriefSection({ paperKey, arxivId, brief }: BriefSectionProps) {
  const queryClient = useQueryClient();
  const id = paperKey || arxivId;
  const [error, setError] = useState<string | null>(null);

  const mut = useMutation({
    mutationFn: () => regeneratePaperBrief(id),
    onSuccess: () => {
      setError(null);
      void queryClient.invalidateQueries({ queryKey: ["paper", arxivId] });
      void queryClient.invalidateQueries({ queryKey: ["paper-detail", arxivId] });
      void queryClient.invalidateQueries({ queryKey: ["papers"] });
    },
    onError: (e) => setError(String(e)),
  });

  if (!brief || !brief.abstract_zh) {
    return (
      <section>
        <div
          className="font-mono text-[10px] uppercase tracking-[0.16em]
                     text-[var(--fg-muted)] mb-3"
        >
          Brief
        </div>
        <div
          className="rounded border border-dashed border-[var(--rule)] p-6
                     text-center"
        >
          <p className="font-serif text-sm italic text-[var(--fg-muted)]">
            No brief yet. Generate the editorial summary
            (中文摘要 + 关键词 + 视角点评)?
          </p>
          <button
            type="button"
            onClick={() => mut.mutate()}
            disabled={mut.isPending}
            className="mt-3 px-4 py-1.5 rounded-chip border border-[var(--fg)]
                       bg-[var(--fg)] text-[var(--bg)]
                       text-[11px] font-sans uppercase tracking-[0.16em]
                       disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {mut.isPending ? "Generating…" : "Generate brief"}
          </button>
          {error ? (
            <p className="mt-2 text-xs text-[var(--counter-fg)] font-sans">
              {error}
            </p>
          ) : null}
        </div>
      </section>
    );
  }

  return (
    <section>
      <div className="flex items-baseline justify-between mb-3">
        <div
          className="font-mono text-[10px] uppercase tracking-[0.16em]
                     text-[var(--fg-muted)]"
        >
          Brief · {brief.perspective_used || "—"}
        </div>
        <button
          type="button"
          onClick={() => mut.mutate()}
          disabled={mut.isPending}
          className="text-[10px] font-sans uppercase tracking-[0.14em]
                     text-[var(--fg-soft)] hover:text-[var(--accent)] transition-colors
                     disabled:opacity-50"
        >
          {mut.isPending ? "Regenerating…" : "Regenerate"}
        </button>
      </div>

      <p
        className="font-serif text-[1.05rem] leading-[1.8] text-[var(--fg)]
                   whitespace-pre-line"
      >
        {brief.abstract_zh}
      </p>

      {brief.keywords.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {brief.keywords.map((k) => (
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

      {brief.for_you ? (
        <blockquote
          className="mt-5 pl-4 border-l-2 border-[var(--accent)]
                     font-serif italic text-[0.98rem] leading-[1.7]
                     text-[var(--fg-soft)]"
        >
          {brief.for_you}
        </blockquote>
      ) : null}

      {brief.key_innovation.length > 0 ? (
        <div className="mt-5">
          <div
            className="font-mono text-[10px] uppercase tracking-[0.16em]
                       text-[var(--fg-muted)] mb-2"
          >
            Key innovation
          </div>
          <ul className="list-disc list-inside font-serif text-sm leading-[1.7] text-[var(--fg)]">
            {brief.key_innovation.map((k, i) => (
              <li key={i}>{k}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {brief.limitations.length > 0 ? (
        <div className="mt-4">
          <div
            className="font-mono text-[10px] uppercase tracking-[0.16em]
                       text-[var(--fg-muted)] mb-2"
          >
            Limitations
          </div>
          <ul className="list-disc list-inside font-serif text-sm leading-[1.7] text-[var(--fg-soft)]">
            {brief.limitations.map((k, i) => (
              <li key={i}>{k}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {error ? (
        <p className="mt-3 text-xs text-[var(--counter-fg)] font-sans">
          {error}
        </p>
      ) : null}
    </section>
  );
}
