import { useQuery } from "@tanstack/react-query";
import { listPapers } from "@/api/papers";
import { PaperCard } from "@/components/PaperCard";
import { ScrollArea } from "@/components/ui/scroll-area";

export default function PaperListPage() {
  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ["papers"],
    queryFn: listPapers,
  });

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between border-b bg-white px-4 py-2">
        <h1 className="text-base font-semibold">Papers</h1>
        <button
          type="button"
          onClick={() => refetch()}
          className="text-xs px-3 py-1 rounded border hover:bg-slate-100"
          disabled={isFetching}
        >
          {isFetching ? "Refreshing..." : "Refresh"}
        </button>
      </div>
      <ScrollArea className="flex-1">
        <div className="p-4 space-y-2 max-w-3xl mx-auto">
          {isLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : error ? (
            <p className="text-sm text-red-600">
              Failed to load papers: {(error as Error).message}
            </p>
          ) : !data || data.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No papers yet. Trigger a run from the Run tab.
            </p>
          ) : (
            data.map((p) => <PaperCard key={p.arxiv_id} paper={p} />)
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
