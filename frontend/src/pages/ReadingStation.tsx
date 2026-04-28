import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";

import type { PaperDetail } from "@/api/papers";
import { pdfFileUrl, setPaperStatus } from "@/api/papers";
import type { PaperStatus } from "@/types/paper";

import SpeedCardPane from "@/components/reading/SpeedCardPane";
import { NotesPane } from "@/components/reading/NotesPane";
import { ActionBar } from "@/components/reading/ActionBar";
import { StatusPill } from "@/components/reading/StatusPill";
import type { PdfViewerHandle } from "@/components/reading/PdfViewer";

// pdf.js bundle is ~600KB gzip — split it into its own chunk so the app's
// main bundle doesn't carry it for users who never open a PDF.
const PdfViewer = lazy(() =>
  import("@/components/reading/PdfViewer").then((m) => ({ default: m.PdfViewer })),
);

interface ReadingStationProps {
  detail: PaperDetail;
  /** When false (no PDF), we collapse to a 2-pane layout. */
  hasPdf: boolean;
  /** Toggle handler back to speed mode (top-right). */
  onSwitchToSpeed: () => void;
}

const NARROW_BREAKPOINT = 1100;

/**
 * ft-029 ReadingStation — three-pane layout (or two when no PDF).
 *
 *   speed-card (28%)  |  pdf (47%)  |  notes (25%)
 *
 * Window narrower than NARROW_BREAKPOINT collapses notes into a slide-over
 * sheet that the user toggles via a top-right button. We use a media-query
 * watcher rather than CSS-only because the PdfViewer's resize observer needs
 * to react to the actual mounted layout.
 */
export default function ReadingStation({
  detail,
  hasPdf,
  onSwitchToSpeed,
}: ReadingStationProps) {
  const paperKey = detail.paper_key || detail.arxiv_id;
  const status: PaperStatus = detail.status ?? "new";
  const queryClient = useQueryClient();

  // Auto-bump new/queued → reading on first mount.
  const bumpedRef = useRef(false);
  const bumpMut = useMutation({
    mutationFn: () => setPaperStatus(paperKey, "reading"),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["paper", paperKey] });
      void queryClient.invalidateQueries({ queryKey: ["papers"] });
    },
  });
  useEffect(() => {
    if (bumpedRef.current) return;
    if (status === "new" || status === "queued") {
      bumpedRef.current = true;
      bumpMut.mutate();
    }
  }, [status, bumpMut]);

  // Resolve PDF URL once.
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!hasPdf) {
      setPdfUrl(null);
      return;
    }
    let cancelled = false;
    pdfFileUrl(paperKey).then((u) => {
      if (!cancelled) setPdfUrl(u);
    });
    return () => {
      cancelled = true;
    };
  }, [hasPdf, paperKey]);

  // Cross-link orchestration: SpeedCardPane / ClaimCard / Evidence call into
  // pdfRef.current. handleCite resolves materialId → action.
  const pdfRef = useRef<PdfViewerHandle | null>(null);

  const handleCite = useMemo(
    () => (materialId: string) => {
      const fig = detail.figures.find((f) => f.material_id === materialId);
      if (fig) {
        pdfRef.current?.scrollToPage(fig.page);
        if (fig.bbox && fig.bbox.length >= 4) {
          // Defer slightly so the scroll animation has a chance to settle.
          window.setTimeout(() => {
            pdfRef.current?.highlightBox(fig.page, fig.bbox as number[]);
          }, 120);
        }
        return;
      }
      const tbl = detail.tables.find((t) => t.material_id === materialId);
      if (tbl) {
        pdfRef.current?.scrollToPage(tbl.page);
        if (tbl.bbox && tbl.bbox.length >= 4) {
          window.setTimeout(() => {
            pdfRef.current?.highlightBox(tbl.page, tbl.bbox as number[]);
          }, 120);
        }
        return;
      }
      const sec = detail.sections.find((s) => s.material_id === materialId);
      if (sec) {
        // No page/bbox for sections — fall back to text search.
        pdfRef.current?.searchText(sec.path.slice(0, 60));
        return;
      }
      const eq = detail.equations.find((e) => e.material_id === materialId);
      if (eq && eq.page) {
        pdfRef.current?.scrollToPage(eq.page);
        return;
      }
      // citation / unknown — no-op.
    },
    [detail],
  );

  const handleSectionJump = useMemo(
    () => (sectionPath: string) => {
      // Sections don't carry a bbox; pdf.js text search by the path's tail
      // (e.g. "Methods / 3.2 Training" → "3.2 Training").
      const tail = sectionPath.split("/").pop()?.trim() ?? sectionPath;
      pdfRef.current?.searchText(tail.slice(0, 60));
    },
    [],
  );

  // Narrow-screen detection.
  const [narrow, setNarrow] = useState<boolean>(
    typeof window !== "undefined"
      ? window.innerWidth < NARROW_BREAKPOINT
      : false,
  );
  const [notesOpen, setNotesOpen] = useState(false);
  useEffect(() => {
    const onResize = () =>
      setNarrow(window.innerWidth < NARROW_BREAKPOINT);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  return (
    <div className="flex flex-col h-full bg-[var(--bg)]">
      {/* Top bar */}
      <div className="flex items-center justify-between px-4 h-10 border-b border-[var(--rule)] shrink-0 bg-[var(--bg)]">
        <Link
          to="/"
          className="font-sans text-[11px] uppercase tracking-[0.14em] text-[var(--fg-muted)] hover:text-[var(--accent)]"
        >
          ← Today&rsquo;s brief
        </Link>
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] text-[var(--fg-muted)] truncate max-w-[200px]">
            {detail.arxiv_id}
          </span>
          {narrow && hasPdf ? (
            <button
              type="button"
              onClick={() => setNotesOpen((v) => !v)}
              className="px-2 py-1 rounded-chip border border-[var(--rule)] font-sans text-[10px] uppercase tracking-[0.14em] text-[var(--fg-soft)] hover:border-[var(--fg)]"
            >
              {notesOpen ? "× Notes" : "Notes"}
            </button>
          ) : null}
          <button
            type="button"
            onClick={onSwitchToSpeed}
            className="px-2 py-1 rounded-chip border border-[var(--rule)] font-sans text-[10px] uppercase tracking-[0.14em] text-[var(--fg-soft)] hover:border-[var(--fg)]"
            title="Switch to speed-read mode"
          >
            Speed
          </button>
          <StatusPill paperKey={paperKey} status={status} />
        </div>
      </div>

      {/* Main split panes */}
      <div className="flex-1 min-h-0 relative">
        {hasPdf ? (
          narrow ? (
            // 2-pane (speed | pdf), notes lives in slide-over.
            <PanelGroup
              direction="horizontal"
              autoSaveId="reading-station-narrow"
            >
              <Panel defaultSize={40} minSize={25} maxSize={60}>
                <SpeedCardPane
                  detail={detail}
                  onCiteClick={handleCite}
                  onSectionJump={handleSectionJump}
                />
              </Panel>
              <PanelResizeHandle className="w-px bg-[var(--rule)] hover:bg-[var(--accent)] transition-colors" />
              <Panel defaultSize={60} minSize={30}>
                <PdfPaneSuspense pdfUrl={pdfUrl} pdfRef={pdfRef} />
              </Panel>
            </PanelGroup>
          ) : (
            <PanelGroup
              direction="horizontal"
              autoSaveId="reading-station-3pane"
            >
              <Panel defaultSize={28} minSize={20} maxSize={40}>
                <SpeedCardPane
                  detail={detail}
                  onCiteClick={handleCite}
                  onSectionJump={handleSectionJump}
                />
              </Panel>
              <PanelResizeHandle className="w-px bg-[var(--rule)] hover:bg-[var(--accent)] transition-colors" />
              <Panel defaultSize={47} minSize={30}>
                <PdfPaneSuspense pdfUrl={pdfUrl} pdfRef={pdfRef} />
              </Panel>
              <PanelResizeHandle className="w-px bg-[var(--rule)] hover:bg-[var(--accent)] transition-colors" />
              <Panel defaultSize={25} minSize={18} maxSize={35}>
                <NotesPane paperKey={paperKey} />
              </Panel>
            </PanelGroup>
          )
        ) : (
          // No PDF → 2-pane: speed-card 60% + notes 40%
          <PanelGroup
            direction="horizontal"
            autoSaveId="reading-station-no-pdf"
          >
            <Panel defaultSize={60} minSize={40}>
              <SpeedCardPane
                detail={detail}
                onCiteClick={handleCite}
                onSectionJump={handleSectionJump}
              />
            </Panel>
            <PanelResizeHandle className="w-px bg-[var(--rule)] hover:bg-[var(--accent)] transition-colors" />
            <Panel defaultSize={40} minSize={20} maxSize={55}>
              <NotesPane paperKey={paperKey} />
            </Panel>
          </PanelGroup>
        )}

        {/* Narrow-screen notes slide-over */}
        {narrow && hasPdf && notesOpen ? (
          <div className="absolute inset-y-0 right-0 w-[min(420px,90vw)] border-l border-[var(--rule)] bg-[var(--bg)] shadow-lift z-20">
            <NotesPane paperKey={paperKey} />
          </div>
        ) : null}
      </div>

      {/* Bottom action bar */}
      <ActionBar paperKey={paperKey} status={status} />
    </div>
  );
}

function PdfPaneSuspense({
  pdfUrl,
  pdfRef,
}: {
  pdfUrl: string | null;
  pdfRef: React.MutableRefObject<PdfViewerHandle | null>;
}) {
  if (!pdfUrl) {
    return (
      <div className="h-full flex items-center justify-center font-serif text-[var(--fg-muted)]">
        Resolving PDF…
      </div>
    );
  }
  return (
    <Suspense
      fallback={
        <div className="h-full flex items-center justify-center font-serif text-[var(--fg-muted)]">
          Loading viewer…
        </div>
      }
    >
      <PdfViewer ref={pdfRef} pdfUrl={pdfUrl} />
    </Suspense>
  );
}
