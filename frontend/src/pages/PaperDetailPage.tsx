import { useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Layers } from "lucide-react";

import { ClaimCard } from "@/components/ClaimCard";
import { ClaimDrawer } from "@/components/ClaimDrawer";
import { FloatingTOC } from "@/components/FloatingTOC";
import { MarkdownView } from "@/components/MarkdownView";
import { ReadingModeToggle } from "@/components/ReadingModeToggle";
import {
  EquationDTO,
  PaperDetail,
  SectionDTO,
  getPaperDetail,
  getPaperMarkdown,
} from "@/api/papers";
import { getApi } from "@/api/client";

/**
 * ft-026 PaperDetailPage. Single-column immersive reading by default.
 * - Right-bottom button toggles ClaimDrawer (slides in from right, 540px).
 * - Left-bottom FloatingTOC button surfaces a popover ToC.
 * - Top-right ReadingModeToggle hides chrome and widens reading.
 *
 * Markdown is centered in max-w-reading (720px). The drawer overlays
 * (does not push) the content; on wider screens both fit comfortably.
 */
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
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [readingMode, setReadingMode] = useState(false);
  const articleRef = useRef<HTMLDivElement | null>(null);

  const equationsById = useMemo(() => {
    const m: Record<string, EquationDTO> = {};
    (detailQ.data?.equations ?? []).forEach((e) => (m[e.material_id] = e));
    return m;
  }, [detailQ.data]);

  function scrollToEvidence(materialId: string) {
    setActiveSectionId(materialId);
    const root = articleRef.current;
    if (!root) return;
    const short = materialId.split(":").slice(-2).join(":");
    const candidates = Array.from(root.querySelectorAll<HTMLElement>("*"))
      .filter(
        (el) =>
          el.textContent &&
          el.textContent.toLowerCase().includes(short.toLowerCase()),
      )
      .slice(0, 1);
    if (candidates.length > 0) {
      candidates[0].scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }

  function scrollToSection(s: SectionDTO) {
    setActiveSectionId(s.material_id);
    const root = articleRef.current;
    if (!root) return;
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
    return (
      <div className="p-6 font-serif text-sm text-[var(--counter-fg)]">
        Missing arxiv id.
      </div>
    );
  }

  const detail = detailQ.data;
  const claimCount = detail?.claims.length ?? 0;

  return (
    <div
      className={`relative h-full overflow-y-auto bg-[var(--bg)]
                  ${readingMode ? "reading-mode" : ""}`}
    >
      {/* Top bar */}
      <div className="sticky top-0 z-20 bg-[var(--bg)]/90 backdrop-blur
                      border-b border-[var(--rule)] reading-mode-hide">
        <div className="max-w-[920px] mx-auto px-8 md:px-12 py-3
                        flex items-center justify-between">
          <Link
            to="/"
            className="font-sans text-xs uppercase tracking-[0.14em]
                       text-[var(--fg-muted)] hover:text-[var(--accent)]
                       transition-colors"
          >
            ← Today&rsquo;s brief
          </Link>
          <div className="flex items-center gap-3">
            <span className="font-mono text-[11px] text-[var(--fg-muted)] truncate
                             max-w-[280px]">
              {arxivId}
            </span>
            <ReadingModeToggle
              active={readingMode}
              onToggle={() => setReadingMode((v) => !v)}
            />
          </div>
        </div>
      </div>

      {/* Article column */}
      <main className="max-w-reading mx-auto px-6 md:px-8 py-12">
        <div ref={articleRef}>
          {markdownQ.isLoading ? (
            <p className="font-serif text-[var(--fg-muted)]">Loading markdown…</p>
          ) : markdownQ.error ? (
            <p className="font-serif text-[var(--counter-fg)]">
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
      </main>

      {/* Floating ToC (bottom-left) */}
      <FloatingTOC
        sections={detail?.sections ?? []}
        activeMaterialId={activeSectionId}
        onSelect={scrollToSection}
      />

      {/* Claim drawer toggle (bottom-right) */}
      <button
        type="button"
        onClick={() => setDrawerOpen((v) => !v)}
        aria-label={drawerOpen ? "Hide claims" : "Show claims"}
        className="reading-mode-hide fixed bottom-6 right-6 z-30
                   inline-flex items-center gap-2 px-4 py-2.5 rounded-full
                   bg-[var(--accent)] text-[var(--accent-fg)]
                   shadow-lift hover:shadow-soft transition
                   font-sans text-sm font-medium"
      >
        <Layers className="h-4 w-4" />
        {claimCount} claims
      </button>

      {/* Right-side drawer */}
      <ClaimDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={`Claims (${claimCount})`}
      >
        {!detail ? (
          <p className="font-serif text-sm text-[var(--fg-muted)]">Loading…</p>
        ) : detail.claims.length === 0 ? (
          <p className="font-serif text-sm text-[var(--fg-muted)]">
            No claims yet. Run interpret from the Run tab.
          </p>
        ) : (
          detail.claims.map((c) => (
            <ClaimCard
              key={c.claim_id}
              claim={c}
              equationsById={equationsById}
              onCiteClick={scrollToEvidence}
            />
          ))
        )}
      </ClaimDrawer>
    </div>
  );
}
