import { arxivAbsUrl, arxivPdfUrl, openExternal } from "@/lib/externalLinks";

interface PaperLinksProps {
  arxivId: string;
  /** 紧凑模式（速读卡）字号更小 */
  compact?: boolean;
}

/**
 * arXiv abs / PDF download 链接对。点击走 shell.openExternal（Electron）或
 * window.open（dev 浏览器）。非 arxiv id（PDF 上传 / DOI-only）不渲染。
 */
export function PaperLinks({ arxivId, compact = false }: PaperLinksProps) {
  const abs = arxivAbsUrl(arxivId);
  const pdf = arxivPdfUrl(arxivId);
  if (!abs && !pdf) return null;

  const cls = compact
    ? "text-[10px] tracking-[0.12em]"
    : "text-[11px] tracking-[0.14em]";

  const handle = (url: string) => (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    void openExternal(url);
  };

  return (
    <div className={`flex gap-3 ${cls} font-sans uppercase`}>
      {abs ? (
        <button
          type="button"
          onClick={handle(abs)}
          className="text-[var(--fg-soft)] hover:text-[var(--accent)]
                     transition-colors"
          title={abs}
        >
          arXiv ↗
        </button>
      ) : null}
      {pdf ? (
        <button
          type="button"
          onClick={handle(pdf)}
          className="text-[var(--fg-soft)] hover:text-[var(--accent)]
                     transition-colors"
          title={pdf}
        >
          PDF ↓
        </button>
      ) : null}
    </div>
  );
}
