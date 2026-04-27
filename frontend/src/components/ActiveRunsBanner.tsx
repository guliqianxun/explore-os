// ft-027 follow-up: pinned banner listing currently-running subscription jobs.
import { useJobsStore } from "@/stores/jobsStore";
import { isTerminal } from "@/hooks/useJobPolling";

export default function ActiveRunsBanner() {
  const jobs = Object.values(useJobsStore((s) => s.jobs))
    .filter((j) => j.name.startsWith("run-sub:"))
    .sort((a, b) => (a.created_at < b.created_at ? 1 : -1));

  if (jobs.length === 0) return null;

  return (
    <div
      className="px-6 py-2 border-b text-xs flex flex-wrap gap-3 items-center"
      style={{
        background: "var(--bg-soft)",
        borderColor: "var(--rule)",
        color: "var(--fg-soft)",
      }}
    >
      <span style={{ color: "var(--fg-muted)" }}>active runs:</span>
      {jobs.map((j) => {
        const subName = j.name.replace(/^run-sub:/, "");
        const terminal = isTerminal(j.status);
        const ok = j.status === "succeeded";
        const failed = j.status === "failed" || j.status === "cancelled";
        const color = failed
          ? "var(--counter-fg)"
          : ok
          ? "var(--accent)"
          : "var(--fg)";
        return (
          <span
            key={j.job_id}
            className="inline-flex items-center gap-1.5 px-2 py-0.5"
            style={{
              background: "var(--bg)",
              border: "1px solid var(--rule)",
              borderRadius: "var(--radius-chip)",
              color,
            }}
          >
            <span
              className="inline-block w-1.5 h-1.5 rounded-full"
              style={{
                background: failed
                  ? "var(--counter-fg)"
                  : ok
                  ? "var(--accent)"
                  : "var(--fg-soft)",
                animation: terminal ? "none" : "pulse 1.4s ease-in-out infinite",
              }}
            />
            <span style={{ fontWeight: 500 }}>{subName}</span>
            <span style={{ color: "var(--fg-muted)" }}>
              {ok
                ? "✓ done"
                : failed
                ? "✗ failed"
                : j.status === "running"
                ? "running…"
                : "queued"}
            </span>
            {failed && j.error && (
              <span
                className="truncate max-w-[20ch]"
                title={j.error}
                style={{ color: "var(--counter-fg)" }}
              >
                · {j.error}
              </span>
            )}
          </span>
        );
      })}
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.35; }
        }
      `}</style>
    </div>
  );
}
