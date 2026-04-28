import { useQuery } from "@tanstack/react-query";
import * as TabsPrimitive from "@radix-ui/react-tabs";

import {
  listPaperBacklinks,
  listPaperComments,
  listPaperTags,
} from "@/api/papers";

import { CommentList } from "./CommentList";
import { TagEditor } from "./TagEditor";
import { BacklinkEditor } from "./BacklinkEditor";

interface NotesPaneProps {
  paperKey: string;
}

/**
 * ft-029 right pane in ReadingStation. Three editorial tabs:
 *   - Comments (append-only, Cmd+Enter)
 *   - Tags (chip input)
 *   - Backlinks (outgoing/incoming + typeahead add)
 *
 * Counts in the tab labels are pre-fetched so the user doesn't have to
 * click each tab to know whether anything's there.
 */
export function NotesPane({ paperKey }: NotesPaneProps) {
  const commentsQ = useQuery({
    queryKey: ["paper-comments", paperKey],
    queryFn: () => listPaperComments(paperKey),
    enabled: !!paperKey,
  });
  const tagsQ = useQuery({
    queryKey: ["paper-tags", paperKey],
    queryFn: () => listPaperTags(paperKey),
    enabled: !!paperKey,
  });
  const backlinksQ = useQuery({
    queryKey: ["paper-backlinks", paperKey],
    queryFn: () => listPaperBacklinks(paperKey),
    enabled: !!paperKey,
  });

  const nComments = commentsQ.data?.length ?? 0;
  const nTags = tagsQ.data?.length ?? 0;
  const nBacklinks =
    (backlinksQ.data?.outgoing.length ?? 0) +
    (backlinksQ.data?.incoming.length ?? 0);

  return (
    <TabsPrimitive.Root
      defaultValue="comments"
      className="flex flex-col h-full bg-[var(--bg)]"
    >
      <TabsPrimitive.List className="flex border-b border-[var(--rule)] px-2 shrink-0">
        <TabTrig value="comments">Comments {nComments > 0 ? `(${nComments})` : ""}</TabTrig>
        <TabTrig value="tags">Tags {nTags > 0 ? `(${nTags})` : ""}</TabTrig>
        <TabTrig value="backlinks">Backlinks {nBacklinks > 0 ? `(${nBacklinks})` : ""}</TabTrig>
      </TabsPrimitive.List>
      <TabsPrimitive.Content
        value="comments"
        className="flex-1 overflow-hidden focus:outline-none"
      >
        <CommentList paperKey={paperKey} />
      </TabsPrimitive.Content>
      <TabsPrimitive.Content
        value="tags"
        className="flex-1 overflow-y-auto focus:outline-none"
      >
        <TagEditor paperKey={paperKey} />
      </TabsPrimitive.Content>
      <TabsPrimitive.Content
        value="backlinks"
        className="flex-1 overflow-hidden focus:outline-none"
      >
        <BacklinkEditor paperKey={paperKey} />
      </TabsPrimitive.Content>
    </TabsPrimitive.Root>
  );
}

function TabTrig({
  value,
  children,
}: {
  value: string;
  children: React.ReactNode;
}) {
  return (
    <TabsPrimitive.Trigger
      value={value}
      className="px-3 py-2 font-sans text-[11px] uppercase tracking-[0.14em]
                 text-[var(--fg-muted)] border-b-2 border-transparent
                 hover:text-[var(--fg)]
                 data-[state=active]:text-[var(--fg)]
                 data-[state=active]:border-[var(--accent)]
                 transition-colors focus:outline-none"
    >
      {children}
    </TabsPrimitive.Trigger>
  );
}
