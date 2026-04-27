// ft-027: per-paper ingest row showing 3-stage chain progress.
// Stages are inferred from the root job (extract → interpret → render):
//   - chain succeeded → all 3 done
//   - chain failed    → which stage failed deduced from error string
//   - chain running   → we don't know which sub-stage (root job is one worker)
//                       so show stages as "in progress" collectively.
import { Link } from "react-router-dom";

import type { JobInfo } from "@/api/jobs";

interface Props {
  job: JobInfo;
  paperId: string;
}

type StageState = "pending" | "running" | "done" | "failed";

interface Stage {
  key: string;
  label: string;
  state: StageState;
}

function deriveStages(job: JobInfo): Stage[] {
  const labels: Array<[string, string]> = [
    ["extract", "Extracted"],
    ["interpret", "Interpreted"],
    ["render", "Rendered"],
  ];

  if (job.status === "succeeded") {
    return labels.map(([k, l]) => ({ key: k, label: l, state: "done" }));
  }
  if (job.status === "failed") {
    const err = (job.error || "").toLowerCase();
    let failedAt = "extract";
    if (err.includes("render failed")) failedAt = "render";
    else if (err.includes("interpret failed")) failedAt = "interpret";
    return labels.map(([k, l]) => {
      if (k === failedAt) return { key: k, label: l, state: "failed" };
      const failedIdx = labels.findIndex(([x]) => x === failedAt);
      const myIdx = labels.findIndex(([x]) => x === k);
      return {
        key: k,
        label: l,
        state: myIdx < failedIdx ? "done" : "pending",
      };
    });
  }
  if (job.status === "running") {
    return labels.map(([k, l], i) => ({
      key: k,
      label: l,
      state: i === 0 ? "running" : "pending",
    }));
  }
  // queued / pending
  return labels.map(([k, l]) => ({ key: k, label: l, state: "pending" }));
}

const TINT: Record<StageState, { bg: string; fg: string; mark: string }> = {
  pending: { bg: "var(--bg-muted)", fg: "var(--fg-muted)", mark: "·" },
  running: { bg: "var(--accent-soft)", fg: "var(--accent)", mark: "…" },
  done: { bg: "var(--proposal-soft)", fg: "var(--proposal)", mark: "✓" },
  failed: { bg: "var(--counter-bg)", fg: "var(--counter-fg)", mark: "✗" },
};

export default function IngestProgressItem({ job, paperId }: Props) {
  const stages = deriveStages(job);
  const allDone = stages.every((s) => s.state === "done");

  return (
    <article
      className="p-3 mb-2 flex items-center gap-3"
      style={{
        background: "var(--bg)",
        border: "1px solid var(--rule)",
        borderRadius: "var(--radius-card)",
      }}
    >
      <div className="min-w-0 flex-1">
        <div
          className="text-sm font-medium truncate"
          style={{ fontFamily: "var(--font-serif)", color: "var(--fg)" }}
        >
          {paperId}
        </div>
        <div className="flex gap-1.5 mt-1 flex-wrap">
          {stages.map((s) => {
            const t = TINT[s.state];
            return (
              <span
                key={s.key}
                className="text-[11px] px-2 py-0.5"
                style={{
                  background: t.bg,
                  color: t.fg,
                  borderRadius: "var(--radius-chip)",
                }}
              >
                {t.mark} {s.label}
              </span>
            );
          })}
        </div>
        {job.status === "failed" && job.error && (
          <p
            className="text-xs mt-1 truncate"
            style={{ color: "var(--counter-fg)" }}
            title={job.error}
          >
            {job.error.split("\n")[0]}
          </p>
        )}
      </div>
      {allDone && (
        <Link
          to={`/papers/${encodeURIComponent(paperId)}`}
          className="text-sm px-3 py-1 shrink-0"
          style={{
            background: "var(--accent)",
            color: "var(--accent-fg)",
            borderRadius: "var(--radius-card)",
          }}
        >
          Read →
        </Link>
      )}
    </article>
  );
}
