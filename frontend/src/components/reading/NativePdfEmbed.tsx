import {
  forwardRef,
  useCallback,
  useImperativeHandle,
  useState,
} from "react";

export interface NativePdfEmbedHandle {
  scrollToPage(page: number): void;
  highlightText(text: string): void;
}

interface NativePdfEmbedProps {
  pdfUrl: string;
  className?: string;
  onPageChange?: (page: number) => void;
}

/**
 * Phase F6 — browser-native PDF viewer via `<embed>`.
 *
 * Replaces the heavy pdf.js bundle (~600KB gzip) with the browser's built-in
 * PDF renderer. Limitations:
 *   - No programmatic text highlight (highlightText is a no-op)
 *   - No programmatic text search (user Ctrl+F in the embed directly)
 *   - scrollToPage reloads the embed at the target page via URL fragment
 */
export const NativePdfEmbed = forwardRef<
  NativePdfEmbedHandle,
  NativePdfEmbedProps
>(function NativePdfEmbed({ pdfUrl, className, onPageChange }, ref) {
  const [src, setSrc] = useState(pdfUrl);

  const baseUrl = pdfUrl.includes("?")
    ? (() => {
        const u = new URL(pdfUrl, window.location.origin);
        u.hash = "";
        return u.toString();
      })()
    : (() => {
        const hashIdx = pdfUrl.indexOf("#");
        return hashIdx >= 0 ? pdfUrl.slice(0, hashIdx) : pdfUrl;
      })();

  const scrollToPage = useCallback(
    (page: number) => {
      setSrc(`${baseUrl}#page=${page}`);
      onPageChange?.(page);
    },
    [baseUrl, onPageChange],
  );

  const highlightText = useCallback((text: string) => {
    void text; // unused
    // Browser-native PDF viewer doesn't support programmatic highlights.
  }, []);

  useImperativeHandle(
    ref,
    (): NativePdfEmbedHandle => ({
      scrollToPage,
      highlightText,
    }),
    [scrollToPage, highlightText],
  );

  return (
    <embed
      src={src}
      type="application/pdf"
      width="100%"
      height="100%"
      className={className}
    />
  );
});
