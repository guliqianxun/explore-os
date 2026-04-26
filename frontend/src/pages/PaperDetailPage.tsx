import { useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { ScrollArea } from "@/components/ui/scroll-area";
import { ClaimCard } from "@/components/ClaimCard";
import { MarkdownView } from "@/components/MarkdownView";
import { SectionTree } from "@/components/SectionTree";
import {
  EquationDTO,
  PaperDetail,
  SectionDTO,
  getPaperDetail,
  getPaperMarkdown,
} from "@/api/papers";
import { getApi } from "@/api/client";

export default function PaperDetailPage() {
  const { arxivId = "" } = useParams<{ arxivId: string }>();

  const detailQ = useQuery<PaperDetail>({
    queryKey: ["paper", arxivId, "detail"],
    queryFn: () => getPaperDetail(arxivId),
    enabled: !!arxivId,
  });
  const markdownQ = useQuery({
    queryKey: ["paper", arxivId, "markdown"],
    queryFn: () => getPaperMarkdown(arxivId),
    enabled: !!arxivId,
  });
  const apiBaseQ = useQuery({
    queryKey: ["api-base"],
    queryFn: async () => {
      const api = await getApi();
      return api.defaults.baseURL ?? "";
    },
    staleTime: Infinity,
  });

  const [activeSectionId, setActiveSectionId] = useState<string | null>(null);
  const middleRef = useRef<HTMLDivElement | null>(null);

  const equationsById = useMemo(() => {
    const m: Record<string, EquationDTO> = {};
    (detailQ.data?.equations ?? []).forEach((e) => (m[e.material_id] = e));
    return m;
  }, [detailQ.data]);

  // When ClaimCard cite badge clicked, scroll center column to a target the
  // markdown rendered. The Docling markdown does not currently embed our
  // material_ids as anchors, so we fall back to text search by short ref.
  function scrollToEvidence(materialId: string) {
    setActiveSectionId(materialId);
    const root = middleRef.current;
    if (!root) return;
    const short = materialId.split(":").slice(-2).join(":"); // e.g. "fig:3"
    const candidates = Array.from(root.querySelectorAll<HTMLElement>("*"))
      .filter((el) => el.textContent && el.textContent.toLowerCase().includes(short.toLowerCase()))
      .slice(0, 1);
    if (candidates.length > 0) {
      candidates[0].scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }

  function scrollToSection(s: SectionDTO) {
    setActiveSectionId(s.material_id);
    const root = middleRef.current;
    if (!root) return;
    // Find a heading whose text matches s.path.
    const headings = Array.from(
      root.querySelectorAll<HTMLElement>("h1, h2, h3, h4, h5, h6"),
    );
    const target =
      headings.find(
        (h) =>
          h.textContent &&
          s.path &&
          h.textContent.trim().toLowerCase() === s.path.trim().toLowerCase(),
      ) ?? headings[s.seq];
    if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  if (!arxivId) {
    return <div className="p-4 text-sm">Missing arxiv id.</div>;
  }

  return (
    <div className="grid grid-cols-[250px_1fr_400px] h-full">
      <aside className="border-r bg-white overflow-hidden flex flex-col">
        <div className="px-3 py-2 border-b text-xs">
          <Link to="/" className="text-blue-600 hover:underline">
            ← Papers
          </Link>
          <div className="font-mono text-[11px] text-muted-foreground mt-1 truncate">
            {arxivId}
          </div>
        </div>
        <ScrollArea className="flex-1">
          <SectionTree
            sections={detailQ.data?.sections ?? []}
            activeMaterialId={activeSectionId}
            onSelect={scrollToSection}
          />
        </ScrollArea>
      </aside>

      <section className="overflow-hidden bg-white flex flex-col min-w-0">
        <ScrollArea className="flex-1">
          <div ref={middleRef}>
            {markdownQ.isLoading ? (
              <p className="p-4 text-sm text-muted-foreground">Loading markdown…</p>
            ) : markdownQ.error ? (
              <p className="p-4 text-sm text-red-600">
                Failed: {(markdownQ.error as Error).message}
              </p>
            ) : (
              <MarkdownView
                markdown={markdownQ.data ?? ""}
                arxivId={arxivId}
                apiBase={apiBaseQ.data ?? ""}
              />
            )}
          </div>
        </ScrollArea>
      </section>

      <aside className="border-l bg-slate-50 overflow-hidden flex flex-col">
        <div className="px-3 py-2 border-b bg-white text-xs font-semibold">
          Claims ({detailQ.data?.claims.length ?? 0})
        </div>
        <ScrollArea className="flex-1">
          <ClaimList
            detail={detailQ.data}
            equationsById={equationsById}
            onCiteClick={scrollToEvidence}
          />
        </ScrollArea>
      </aside>
    </div>
  );
}

function ClaimList({
  detail,
  equationsById,
  onCiteClick,
}: {
  detail: PaperDetail | undefined;
  equationsById: Record<string, EquationDTO>;
  onCiteClick: (materialId: string) => void;
}) {
  if (!detail) {
    return <p className="p-4 text-sm text-muted-foreground">Loading…</p>;
  }
  if (detail.claims.length === 0) {
    return (
      <p className="p-4 text-sm text-muted-foreground">
        No claims yet. Run interpret from the Run tab.
      </p>
    );
  }
  return (
    <div className="p-3 space-y-3">
      {detail.claims.map((c) => (
        <ClaimCard
          key={c.claim_id}
          claim={c}
          equationsById={equationsById}
          onCiteClick={onCiteClick}
        />
      ))}
    </div>
  );
}

