import { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";

interface MarkdownViewProps {
  markdown: string;
  arxivId: string;
  apiBase: string;
  /** Optional className appended to the article wrapper. */
  className?: string;
}

/**
 * ft-026 MarkdownView. Same data path as before (rewrites figure URLs);
 * styling moves to .prose-paper which now goes serif + line-height 1.75.
 * Width is controlled by the parent (PaperDetailPage uses max-w-reading).
 */
export function MarkdownView({
  markdown,
  arxivId,
  apiBase,
  className = "",
}: MarkdownViewProps) {
  // Rewrite relative figure refs `figures/<seq>.png` → API URL.
  const rewritten = useMemo(() => {
    return markdown.replace(
      /(!\[[^\]]*\]\()([^)]*?(?:figures?|imgs?)\/(\d+)\.png)(\))/gi,
      (_m, p1, _p2, seq, p4) =>
        `${p1}${apiBase}/papers/${arxivId}/figure/${seq}.png${p4}`,
    );
  }, [markdown, arxivId, apiBase]);

  return (
    <article className={`prose-paper ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          img: ({ ...props }) => (
            // eslint-disable-next-line jsx-a11y/alt-text
            <img loading="lazy" {...props} />
          ),
          a: ({ children, href, ...rest }) => (
            <a href={href} target="_blank" rel="noreferrer" {...rest}>
              {children}
            </a>
          ),
        }}
      >
        {rewritten}
      </ReactMarkdown>
    </article>
  );
}
