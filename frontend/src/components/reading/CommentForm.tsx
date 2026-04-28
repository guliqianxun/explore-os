import { KeyboardEvent, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { appendPaperComment } from "@/api/papers";

interface CommentFormProps {
  paperKey: string;
}

/**
 * Append-only comment form. Submit = `Cmd+Enter` / `Ctrl+Enter`. No edit /
 * delete affordances — schema is intentionally append-only (ft-028).
 */
export function CommentForm({ paperKey }: CommentFormProps) {
  const [text, setText] = useState("");
  const queryClient = useQueryClient();

  const mut = useMutation({
    mutationFn: (body: string) => appendPaperComment(paperKey, body),
    onSuccess: () => {
      setText("");
      void queryClient.invalidateQueries({
        queryKey: ["paper-comments", paperKey],
      });
      // n_comments is rolled into the paper detail / list response.
      void queryClient.invalidateQueries({ queryKey: ["paper", paperKey] });
      void queryClient.invalidateQueries({ queryKey: ["papers"] });
    },
  });

  const submit = () => {
    const trimmed = text.trim();
    if (!trimmed || mut.isPending) return;
    mut.mutate(trimmed);
  };

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKey}
        placeholder="Add a note… (Cmd/Ctrl + Enter to submit)"
        rows={3}
        className="w-full resize-y rounded border border-[var(--rule)]
                   bg-[var(--bg)] px-2 py-1.5 font-serif text-sm
                   focus:outline-none focus:border-[var(--accent)]"
      />
      <div className="flex justify-end items-center gap-2">
        {mut.isError ? (
          <span className="font-sans text-[10px] text-[var(--counter-fg)]">
            {(mut.error as Error).message}
          </span>
        ) : null}
        <button
          type="button"
          disabled={!text.trim() || mut.isPending}
          onClick={submit}
          className="px-3 py-1 rounded font-sans text-xs uppercase tracking-[0.12em]
                     bg-[var(--accent)] text-[var(--accent-fg)]
                     disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {mut.isPending ? "…" : "Append"}
        </button>
      </div>
    </div>
  );
}
