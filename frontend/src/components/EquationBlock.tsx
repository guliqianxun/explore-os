import { Component, ReactNode } from "react";
import { BlockMath } from "react-katex";

/** Mild LaTeX sanitiser — KaTeX rejects a handful of tokens our extractor
 *  emits ad-hoc; map the common ones to KaTeX-friendly equivalents and let
 *  the error boundary handle anything still broken. */
function sanitizeLatex(s: string): string {
  return (
    s
      .replace(/\\colon/g, ":")
      .replace(/\\text\{([^}]*)\}/g, "\\mathrm{$1}")
      // Drop label macros that show up in arxiv source but break KaTeX.
      .replace(/\\label\{[^}]*\}/g, "")
      .trim()
  );
}

interface EquationErrorBoundaryProps {
  fallback: ReactNode;
  children: ReactNode;
}

interface EquationErrorBoundaryState {
  hasError: boolean;
}

class EquationErrorBoundary extends Component<
  EquationErrorBoundaryProps,
  EquationErrorBoundaryState
> {
  state: EquationErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): EquationErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(): void {
    // Swallow — fallback already renders the LaTeX source.
  }

  render() {
    if (this.state.hasError) return this.props.fallback;
    return this.props.children;
  }
}

export function EquationBlock({ latex }: { latex: string }) {
  const cleaned = sanitizeLatex(latex);
  if (!cleaned) {
    return <code className="text-xs text-muted-foreground">(empty)</code>;
  }
  const fallback = (
    <code className="text-xs whitespace-pre-wrap break-all">{latex}</code>
  );
  return (
    <EquationErrorBoundary fallback={fallback}>
      <BlockMath math={cleaned} errorColor="#cc0000" />
    </EquationErrorBoundary>
  );
}
