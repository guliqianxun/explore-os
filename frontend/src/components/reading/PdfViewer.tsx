import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from "react";
import { Document, Page, pdfjs } from "react-pdf";
// `?url` import bundles the worker as a static asset whose URL Vite injects
// at build time — works in dev (5173) and in packaged Electron (file://).
// react-pdf 9.x ships an ESM-friendly `pdf.worker.min.mjs`; we prefer it over
// the legacy `.js` so Vite's worker plugin doesn't try to re-bundle it.
// eslint-disable-next-line import/no-unresolved
import pdfWorkerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";

// react-pdf v9 + Vite 5 known footgun: the textLayer/annotationLayer CSS is
// ESM and lives next to the package main; importing here picks up cleanly.
import "react-pdf/dist/Page/TextLayer.css";
import "react-pdf/dist/Page/AnnotationLayer.css";

pdfjs.GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

export interface PdfViewerHandle {
  /** Smooth-scroll a given 1-based page into view inside the viewport. */
  scrollToPage(page: number): void;
  /**
   * Highlight a docling bbox (PDF point coordinates, origin bottom-left) on
   * `page` for ~2s. The viewer owns the coordinate transform — callers pass
   * raw bbox numbers from `figure.bbox` / `table.bbox`.
   *
   * bbox layout follows docling: `[x0, y0, x1, y1]` in PDF points.
   */
  highlightBox(page: number, bbox: number[]): void;
  /** Use pdf.js findController to highlight every match of `query`. */
  searchText(query: string): void;
}

interface PdfViewerProps {
  pdfUrl: string;
  /** Forwarded to the rendered `<Document>` for graceful failure. */
  onLoadError?: (err: Error) => void;
}

/**
 * ft-029 PdfViewer.
 *
 * Strategy:
 *   - All pages are rendered up front (논문 ≤ 30 pages, ≤ ~1.5MB DOM is fine).
 *   - Each `<Page>` has `data-page-number` set so `scrollToPage` is a CSS
 *     selector lookup; we don't need a virtualized list yet.
 *   - bbox overlay is an absolutely-positioned div appended into the rendered
 *     page wrapper; its 2s fade-out is via inline transition.
 *   - searchText shells out to react-pdf's customTextRenderer hook, painting
 *     the matches as highlighted spans. (We don't reach into pdfjs internal
 *     findController; the hook approach survives upgrades better.)
 */
export const PdfViewer = forwardRef<PdfViewerHandle, PdfViewerProps>(
  function PdfViewer({ pdfUrl, onLoadError }, ref) {
    const containerRef = useRef<HTMLDivElement | null>(null);
    const [numPages, setNumPages] = useState(0);
    const [pageWidth, setPageWidth] = useState(700);
    const [searchQuery, setSearchQuery] = useState<string>("");
    const [loadErr, setLoadErr] = useState<Error | null>(null);

    // Track rendered native widths per page so highlightBox can compute
    // a px-from-points scale at click time.
    const pageNativeSizesRef = useRef<Map<number, { w: number; h: number }>>(
      new Map(),
    );

    // Resize observer: fit pages into the panel width (- a small gutter).
    useEffect(() => {
      const el = containerRef.current;
      if (!el) return;
      const ro = new ResizeObserver((entries) => {
        for (const e of entries) {
          const w = Math.max(320, Math.floor(e.contentRect.width - 24));
          setPageWidth(w);
        }
      });
      ro.observe(el);
      return () => ro.disconnect();
    }, []);

    const onDocLoad = useCallback(
      ({ numPages: n }: { numPages: number }) => {
        setNumPages(n);
        setLoadErr(null);
      },
      [],
    );

    const handleLoadError = useCallback(
      (err: Error) => {
        setLoadErr(err);
        onLoadError?.(err);
      },
      [onLoadError],
    );

    const handlePageLoad = useCallback(
      (page: { pageNumber: number; originalWidth: number; originalHeight: number }) => {
        pageNativeSizesRef.current.set(page.pageNumber, {
          w: page.originalWidth,
          h: page.originalHeight,
        });
      },
      [],
    );

    // Imperative API exposed through the ref.
    useImperativeHandle(
      ref,
      (): PdfViewerHandle => ({
        scrollToPage(page: number) {
          const root = containerRef.current;
          if (!root) return;
          const target = root.querySelector<HTMLElement>(
            `[data-page-number="${page}"]`,
          );
          if (target) {
            target.scrollIntoView({ behavior: "smooth", block: "start" });
          }
        },
        highlightBox(page: number, bbox: number[]) {
          const root = containerRef.current;
          if (!root || bbox.length < 4) return;
          const wrap = root.querySelector<HTMLElement>(
            `[data-page-number="${page}"]`,
          );
          if (!wrap) return;
          // First scroll, then paint overlay (after the smooth scroll lands
          // the wrap is positioned correctly relative to viewport).
          wrap.scrollIntoView({ behavior: "smooth", block: "start" });

          const native = pageNativeSizesRef.current.get(page);
          // Find the canvas to get its rendered px size; gives us scale.
          const canvas = wrap.querySelector<HTMLCanvasElement>("canvas");
          if (!native || !canvas) return;
          const renderedW = canvas.clientWidth;
          const renderedH = canvas.clientHeight;
          const sx = renderedW / native.w;
          const sy = renderedH / native.h;

          // docling bbox: [x0, y0, x1, y1] in PDF points, origin bottom-left.
          // PDF.js canvas: origin top-left, y grows downward.
          const [x0, y0, x1, y1] = bbox;
          const left = x0 * sx;
          const top = (native.h - y1) * sy;
          const width = Math.max(2, (x1 - x0) * sx);
          const height = Math.max(2, (y1 - y0) * sy);

          const overlay = document.createElement("div");
          overlay.style.position = "absolute";
          overlay.style.left = `${left}px`;
          overlay.style.top = `${top}px`;
          overlay.style.width = `${width}px`;
          overlay.style.height = `${height}px`;
          overlay.style.background = "rgba(255, 200, 60, 0.35)";
          overlay.style.border = "2px solid var(--accent, #c9863a)";
          overlay.style.borderRadius = "3px";
          overlay.style.pointerEvents = "none";
          overlay.style.zIndex = "20";
          overlay.style.transition = "opacity 600ms ease-out";

          // The page wrap is `relative` (react-pdf default); just append.
          const prev = wrap.style.position;
          if (!prev) wrap.style.position = "relative";
          wrap.appendChild(overlay);
          window.setTimeout(() => {
            overlay.style.opacity = "0";
          }, 1400);
          window.setTimeout(() => {
            overlay.remove();
          }, 2100);
        },
        searchText(query: string) {
          // Setting state re-renders pages; the customTextRenderer below
          // wraps every occurrence of `query` in a <mark>.
          const trimmed = query.trim();
          setSearchQuery(trimmed);
          if (!trimmed) return;

          // After repaint, scroll to the first <mark>.
          window.requestAnimationFrame(() => {
            window.requestAnimationFrame(() => {
              const root = containerRef.current;
              if (!root) return;
              const m = root.querySelector<HTMLElement>("mark.pdf-search-hit");
              if (m) m.scrollIntoView({ behavior: "smooth", block: "center" });
            });
          });

          // Auto-clear after 4s so the highlight is transient.
          window.setTimeout(() => setSearchQuery(""), 4000);
        },
      }),
      [],
    );

    // customTextRenderer: invoked per text-layer chunk, returns HTML string.
    const customTextRenderer = useMemo(() => {
      if (!searchQuery) return undefined;
      const needle = searchQuery.toLowerCase();
      return ({ str }: { str: string }) => {
        if (!str) return str;
        const lower = str.toLowerCase();
        const idx = lower.indexOf(needle);
        if (idx < 0) return str;
        const before = escapeHtml(str.slice(0, idx));
        const hit = escapeHtml(str.slice(idx, idx + needle.length));
        const after = escapeHtml(str.slice(idx + needle.length));
        return `${before}<mark class="pdf-search-hit" style="background:rgba(255,220,80,0.65);color:inherit;">${hit}</mark>${after}`;
      };
    }, [searchQuery]);

    // `file` must be referentially stable to avoid react-pdf re-fetching the
    // PDF every render. Memoize on the URL string.
    const fileMemo = useMemo(
      () => ({ url: pdfUrl, withCredentials: false }),
      [pdfUrl],
    );

    return (
      <div
        ref={containerRef}
        className="relative h-full w-full overflow-y-auto bg-[var(--bg-soft)] px-3 py-3"
      >
        {loadErr ? (
          <div className="p-8 font-serif text-sm text-[var(--counter-fg)]">
            Failed to load PDF: {loadErr.message}
          </div>
        ) : null}

        <Document
          file={fileMemo}
          onLoadSuccess={onDocLoad}
          onLoadError={handleLoadError}
          loading={
            <div className="p-12 font-serif text-[var(--fg-muted)]">
              Loading PDF…
            </div>
          }
          error={
            <div className="p-8 font-serif text-sm text-[var(--counter-fg)]">
              PDF could not be displayed.
            </div>
          }
        >
          {Array.from({ length: numPages }, (_, i) => i + 1).map((p) => (
            <div
              key={p}
              data-page-number={p}
              className="mb-4 mx-auto bg-white shadow-soft"
              style={{ width: pageWidth, position: "relative" }}
            >
              <Page
                pageNumber={p}
                width={pageWidth}
                renderTextLayer={true}
                renderAnnotationLayer={false}
                onLoadSuccess={handlePageLoad}
                customTextRenderer={customTextRenderer}
              />
            </div>
          ))}
        </Document>
      </div>
    );
  },
);

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
