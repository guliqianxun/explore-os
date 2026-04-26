import { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";

interface MarkdownViewProps {
  markdown: string;
  arxivId: string;
  apiBase: string;
}

export function MarkdownView({ markdown, arxivId, apiBase }: MarkdownViewProps) {
  // Rewrite relative figure refs `figures/<seq>.png` → API URL.
  const rewritten = useMemo(() => {
    return markdown.replace(
      /(!\[[^\]]*\]\()([^)]*?(?:figures?|imgs?)\/(\d+)\.png)(\))/gi,
      (_m, p1, _p2, seq, p4) => `${p1}${apiBase}/papers/${arxivId}/figure/${seq}.png${p4}`,
    );
  }, [markdown, arxivId, apiBase]);

  return (
    <article className="prose-paper px-6 py-4 max-w-none">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          img: ({ ...props }) => (
            // eslint-disable-next-line jsx-a11y/alt-text
            <img loading="lazy" {...props} />
          ),
          a: ({ children, href, ...rest }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
              className="text-blue-600 hover:underline"
              {...rest}
            >
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
