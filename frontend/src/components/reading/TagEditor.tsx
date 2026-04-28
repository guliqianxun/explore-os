import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { addPaperTag, listPaperTags, removePaperTag } from "@/api/papers";
import ChipInput from "@/components/ChipInput";

interface TagEditorProps {
  paperKey: string;
}

/**
 * ft-029 NotesPane > Tags tab. Wraps the existing ft-027 ChipInput; deltas
 * are translated into POST/DELETE calls. ChipInput is pure UI so we own the
 * server reconciliation here.
 */
export function TagEditor({ paperKey }: TagEditorProps) {
  const queryClient = useQueryClient();
  const q = useQuery({
    queryKey: ["paper-tags", paperKey],
    queryFn: () => listPaperTags(paperKey),
    enabled: !!paperKey,
  });

  const tags = q.data ?? [];

  const addMut = useMutation({
    mutationFn: (tag: string) => addPaperTag(paperKey, tag),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["paper-tags", paperKey],
      });
      void queryClient.invalidateQueries({ queryKey: ["papers"] });
    },
  });
  const removeMut = useMutation({
    mutationFn: (tag: string) => removePaperTag(paperKey, tag),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["paper-tags", paperKey],
      });
      void queryClient.invalidateQueries({ queryKey: ["papers"] });
    },
  });

  const handleChange = (next: string[]) => {
    // Diff against current cache.
    const prev = new Set(tags);
    const nextSet = new Set(next);
    for (const t of next) {
      if (!prev.has(t)) addMut.mutate(t);
    }
    for (const t of tags) {
      if (!nextSet.has(t)) removeMut.mutate(t);
    }
  };

  return (
    <div className="px-4 py-3 space-y-3">
      <div className="font-sans text-[10px] uppercase tracking-[0.16em] text-[var(--fg-muted)]">
        Tags
      </div>
      <ChipInput
        value={tags}
        onChange={handleChange}
        placeholder="add tag, press Enter"
      />
    </div>
  );
}
