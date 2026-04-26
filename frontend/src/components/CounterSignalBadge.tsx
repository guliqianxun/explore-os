import { AlertTriangle } from "lucide-react";
import type { CounterSignalDTO } from "@/api/papers";

export function CounterSignalBadge({ signal }: { signal: CounterSignalDTO }) {
  return (
    <div className="border-l-4 border-red-400 bg-red-50 p-2 text-xs flex gap-2 items-start">
      <AlertTriangle className="h-3.5 w-3.5 text-red-600 shrink-0 mt-0.5" />
      <div className="space-y-0.5">
        <span className="font-semibold text-red-700">{signal.signal_type}</span>
        <p className="text-red-900 leading-relaxed">{signal.text}</p>
      </div>
    </div>
  );
}
