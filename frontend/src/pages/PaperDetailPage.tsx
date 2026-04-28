import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { getPaperDetail, headPaperPdf } from "@/api/papers";
import type { PaperDetail } from "@/api/papers";

import SpeedReadView from "./SpeedReadView";
// ReadingStation pulls in react-resizable-panels + the PdfViewer chunk; keep
// it out of the main bundle so visiting only the PaperList doesn't pay for it.
const ReadingStation = lazy(() => import("./ReadingStation"));

type ReadingMode = "station" | "speed";
const MODE_STORAGE_KEY = "explore-os.reading-mode";

/**
 * ft-029: PaperDetailPage is now a thin shell.
 *
 *   1. Load detail (TanStack Query).
 *   2. Probe PDF availability — prefer `detail.has_pdf` from rpt-013, fall
 *      back to `HEAD /api/papers/<id>/pdf/` for legacy backends.
 *   3. Decide mode:
 *        - explicit user toggle (localStorage) wins
 *        - else: archived OR no-pdf → speed
 *        - else: station
 *   4. Dispatch to <ReadingStation> or <SpeedReadView>.
 */
export default function PaperDetailPage() {
  const { arxivId = "" } = useParams<{ arxivId: string }>();

  const detailQ = useQuery<PaperDetail>({
    queryKey: ["paper", arxivId, "detail"],
    queryFn: () => getPaperDetail(arxivId),
    enabled: !!arxivId,
  });

  const detail = detailQ.data;
  const paperKey = detail?.paper_key || arxivId;

  // PDF availability probe — only if `has_pdf` not already supplied.
  const hasPdfQ = useQuery({
    queryKey: ["paper-has-pdf", paperKey],
    queryFn: () => headPaperPdf(paperKey),
    enabled: !!detail && detail.has_pdf === undefined && !!paperKey,
    staleTime: 30_000,
  });
  const hasPdf =
    detail?.has_pdf !== undefined ? !!detail.has_pdf : hasPdfQ.data ?? false;

  // User toggle (persisted) — null means "auto".
  const [forcedMode, setForcedMode] = useState<ReadingMode | null>(() => {
    if (typeof window === "undefined") return null;
    const v = window.localStorage.getItem(MODE_STORAGE_KEY);
    return v === "speed" || v === "station" ? v : null;
  });
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (forcedMode === null) window.localStorage.removeItem(MODE_STORAGE_KEY);
    else window.localStorage.setItem(MODE_STORAGE_KEY, forcedMode);
  }, [forcedMode]);

  const mode: ReadingMode = useMemo(() => {
    if (forcedMode) return forcedMode;
    if (!detail) return "speed";
    if (detail.status === "archived") return "speed";
    if (!hasPdf) return "speed";
    return "station";
  }, [forcedMode, detail, hasPdf]);

  if (!arxivId) {
    return (
      <div className="p-6 font-serif text-sm text-[var(--counter-fg)]">
        Missing arxiv id.
      </div>
    );
  }
  if (detailQ.isLoading) {
    return (
      <div className="p-12 font-serif text-[var(--fg-muted)]">Loading…</div>
    );
  }
  if (detailQ.error) {
    return (
      <div className="p-12 font-serif text-[var(--counter-fg)]">
        Failed: {(detailQ.error as Error).message}
      </div>
    );
  }
  if (!detail) {
    return (
      <div className="p-12 font-serif text-[var(--fg-muted)]">No data.</div>
    );
  }

  if (mode === "speed") {
    return (
      <div className="relative h-full">
        <div className="absolute top-2 right-3 z-30 flex items-center gap-2">
          <Link
            to="/"
            className="font-sans text-[10px] uppercase tracking-[0.14em] text-[var(--fg-muted)] hover:text-[var(--accent)]"
          >
            ← brief
          </Link>
          {hasPdf ? (
            <button
              type="button"
              onClick={() => setForcedMode("station")}
              className="px-2 py-1 rounded-chip border border-[var(--rule)] bg-[var(--bg)] font-sans text-[10px] uppercase tracking-[0.14em] text-[var(--fg-soft)] hover:border-[var(--fg)]"
            >
              Station
            </button>
          ) : null}
        </div>
        <SpeedReadView detail={detail} />
      </div>
    );
  }

  return (
    <Suspense
      fallback={
        <div className="p-12 font-serif text-[var(--fg-muted)]">
          Loading reading station…
        </div>
      }
    >
      <ReadingStation
        detail={detail}
        hasPdf={hasPdf}
        onSwitchToSpeed={() => setForcedMode("speed")}
      />
    </Suspense>
  );
}
