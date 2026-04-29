import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { setPaperKeywords } from "@/api/papers";

interface KeywordsEditorProps {
  paperKey: string;
  arxivId: string;
  /** 当前 paper.keywords —— 区别于 brief.keywords / LLM 抽出的. */
  initial: string[];
}

const MAX_LEN = 64;
const MAX_ITEMS = 20;

/**
 * 单用户桌面场景下的最简编辑器：默认 read-only chip 列表 + Edit 按钮；
 * 点击进入编辑态后可加 / 删 / 直接 Enter 提交。Save 调用 POST keywords/，
 * 清缓存让 list / detail 重读。
 */
export function KeywordsEditor({ paperKey, arxivId, initial }: KeywordsEditorProps) {
  const queryClient = useQueryClient();
  const id = paperKey || arxivId;
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<string[]>(initial);
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);

  // initial 变化（detail refetch）→ 重置 draft，除非正在编辑（避免吃掉用户改动）
  useEffect(() => {
    if (!editing) setDraft(initial);
  }, [initial, editing]);

  const mut = useMutation({
    mutationFn: (kws: string[]) => setPaperKeywords(id, kws),
    onSuccess: (saved) => {
      setDraft(saved);
      setEditing(false);
      setError(null);
      void queryClient.invalidateQueries({ queryKey: ["paper", arxivId] });
      void queryClient.invalidateQueries({ queryKey: ["paperDetail", arxivId] });
      void queryClient.invalidateQueries({ queryKey: ["papers"] });
    },
    onError: (e) => setError(String(e)),
  });

  const addInput = () => {
    const kw = input.trim().slice(0, MAX_LEN);
    if (!kw) return;
    if (draft.length >= MAX_ITEMS) {
      setError(`max ${MAX_ITEMS} keywords`);
      return;
    }
    if (draft.some((k) => k.toLowerCase() === kw.toLowerCase())) {
      setInput("");
      return;
    }
    setDraft((d) => [...d, kw]);
    setInput("");
  };

  const removeAt = (i: number) => {
    setDraft((d) => d.filter((_, idx) => idx !== i));
  };

  if (!editing) {
    return (
      <section>
        <div className="flex items-baseline justify-between mb-2">
          <div className="font-mono text-[10px] uppercase tracking-[0.16em]
                          text-[var(--fg-muted)]">
            Keywords
          </div>
          <button
            type="button"
            onClick={() => setEditing(true)}
            className="text-[10px] font-sans uppercase tracking-[0.14em]
                       text-[var(--fg-soft)] hover:text-[var(--accent)]
                       transition-colors"
          >
            {initial.length === 0 ? "+ Add" : "Edit"}
          </button>
        </div>
        {initial.length === 0 ? (
          <p className="font-serif text-sm italic text-[var(--fg-muted)]">
            No keywords. Click <strong>+ Add</strong> to tag this paper.
          </p>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {initial.map((k) => (
              <span
                key={k}
                className="px-2 py-0.5 rounded-chip border border-[var(--rule)]
                           text-[11px] font-sans text-[var(--fg-soft)] lowercase"
              >
                {k}
              </span>
            ))}
          </div>
        )}
      </section>
    );
  }

  return (
    <section>
      <div className="flex items-baseline justify-between mb-2">
        <div className="font-mono text-[10px] uppercase tracking-[0.16em]
                        text-[var(--fg-muted)]">
          Keywords (editing)
        </div>
        <div className="flex gap-3">
          <button
            type="button"
            onClick={() => {
              setDraft(initial);
              setInput("");
              setError(null);
              setEditing(false);
            }}
            className="text-[10px] font-sans uppercase tracking-[0.14em]
                       text-[var(--fg-soft)] hover:text-[var(--counter-fg)]"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => mut.mutate(draft)}
            disabled={mut.isPending}
            className="text-[10px] font-sans uppercase tracking-[0.14em]
                       text-[var(--accent)] hover:opacity-70 disabled:opacity-40"
          >
            {mut.isPending ? "Saving…" : "Save"}
          </button>
        </div>
      </div>

      <div className="flex flex-wrap gap-1.5 mb-2">
        {draft.map((k, i) => (
          <span
            key={`${i}-${k}`}
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-chip
                       border border-[var(--rule)] text-[11px] font-sans
                       text-[var(--fg-soft)] lowercase"
          >
            {k}
            <button
              type="button"
              onClick={() => removeAt(i)}
              className="text-[var(--fg-muted)] hover:text-[var(--counter-fg)]
                         leading-none"
              aria-label={`remove ${k}`}
            >
              ×
            </button>
          </span>
        ))}
      </div>

      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          maxLength={MAX_LEN}
          placeholder="add keyword + Enter"
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              addInput();
            }
          }}
          className="flex-1 px-2 py-1 rounded-chip border border-[var(--rule)]
                     bg-transparent text-[12px] font-sans
                     text-[var(--fg)] placeholder:text-[var(--fg-muted)]
                     focus:outline-none focus:border-[var(--accent)]"
        />
        <button
          type="button"
          onClick={addInput}
          disabled={!input.trim()}
          className="px-3 py-1 rounded-chip border border-[var(--rule)]
                     text-[10px] font-sans uppercase tracking-[0.14em]
                     text-[var(--fg-soft)] hover:border-[var(--accent)]
                     disabled:opacity-40"
        >
          + add
        </button>
      </div>

      {error ? (
        <p className="mt-2 text-xs text-[var(--counter-fg)] font-sans">
          {error}
        </p>
      ) : null}
    </section>
  );
}
