import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { listPaperComments } from "@/api/papers";
import { getApi } from "@/api/client";
import type { CommentDTO } from "@/types/paper";

import { CommentForm } from "./CommentForm";

interface CommentListProps {
  paperKey: string;
}

/**
 * ft-029 NotesPane > Comments tab. Schema is append-only — we never
 * delete or re-order, only flip `hidden=true` on the PATCH endpoint.
 *
 * Rendered chronologically (oldest first); hidden items collapse to a small
 * grey pill the user can click to re-show inline.
 */
export function CommentList({ paperKey }: CommentListProps) {
  const queryClient = useQueryClient();
  const q = useQuery({
    queryKey: ["paper-comments", paperKey],
    queryFn: () => listPaperComments(paperKey),
    enabled: !!paperKey,
  });

  const hideMut = useMutation({
    mutationFn: async ({ id, hidden }: { id: number; hidden: boolean }) => {
      const api = await getApi();
      await api.patch(`/comments/${id}/`, { hidden });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["paper-comments", paperKey],
      });
    },
  });

  const comments = q.data ?? [];
  // Backend orders ASC (oldest first) per ft-028 spec; defensive sort here.
  const ordered = [...comments].sort((a, b) =>
    a.created_at.localeCompare(b.created_at),
  );

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {q.isLoading ? (
          <div className="font-serif text-sm text-[var(--fg-muted)]">
            Loading comments…
          </div>
        ) : ordered.length === 0 ? (
          <div className="font-serif text-sm italic text-[var(--fg-muted)]">
            No comments yet.
          </div>
        ) : (
          ordered.map((c) => (
            <CommentItem
              key={c.id}
              comment={c}
              onToggleHidden={(hidden) =>
                hideMut.mutate({ id: c.id, hidden })
              }
            />
          ))
        )}
      </div>
      <div className="border-t border-[var(--rule)] p-3 bg-[var(--bg-soft)]">
        <CommentForm paperKey={paperKey} />
      </div>
    </div>
  );
}

function CommentItem({
  comment,
  onToggleHidden,
}: {
  comment: CommentDTO;
  onToggleHidden: (hidden: boolean) => void;
}) {
  const ts = formatTs(comment.created_at);
  if (comment.hidden) {
    return (
      <button
        type="button"
        onClick={() => onToggleHidden(false)}
        className="font-sans text-[10px] uppercase tracking-[0.14em]
                   text-[var(--fg-muted)] italic hover:text-[var(--fg-soft)]"
      >
        {ts} · hidden — click to expand
      </button>
    );
  }
  return (
    <article className="space-y-1">
      <div className="font-sans text-[10px] uppercase tracking-[0.14em] text-[var(--fg-muted)] flex justify-between items-center">
        <span>{ts}</span>
        <button
          type="button"
          onClick={() => onToggleHidden(true)}
          className="opacity-50 hover:opacity-100 hover:text-[var(--fg)]"
          title="Hide comment"
        >
          hide
        </button>
      </div>
      <div className="font-serif text-[0.92rem] leading-[1.6] text-[var(--fg)] whitespace-pre-line">
        {comment.text}
      </div>
    </article>
  );
}

function formatTs(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString();
  } catch {
    return iso;
  }
}
