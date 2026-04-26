import { AlertTriangle } from "lucide-react";
import type { CounterSignalDTO } from "@/api/papers";

/**
 * ft-026 editorial restyle: warm red palette via tokens, italic serif body,
 * slim left rail. Composes inside ClaimCard.
 */
export function CounterSignalBadge({ signal }: { signal: CounterSignalDTO }) {
  return (
    <div
      className="border-l-4 pl-3 py-2 text-[0.88rem] flex gap-2 items-start"
      style={{
        borderColor: "var(--counter-fg)",
        backgroundColor: "var(--counter-bg)",
        color: "var(--counter-fg)",
      }}
    >
      <AlertTriangle
        className="h-3.5 w-3.5 shrink-0 mt-0.5"
        style={{ color: "var(--counter-fg)" }}
      />
      <div className="space-y-0.5">
        <div className="font-sans text-[10px] uppercase tracking-[0.12em] font-semibold">
          {signal.signal_type}
        </div>
        <p className="font-serif italic leading-[1.6]">{signal.text}</p>
      </div>
    </div>
  );
}
