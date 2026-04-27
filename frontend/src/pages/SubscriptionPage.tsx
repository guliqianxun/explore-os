// ft-027: card list + form-driven editor modal. YAML editor lives in
// the Advanced details inside SubscriptionEditor.
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import SubscriptionCard from "@/components/SubscriptionCard";
import SubscriptionEditor from "@/components/SubscriptionEditor";
import {
  SubscriptionDTO,
  createSubscription,
  deleteSubscription,
  listSubscriptions,
  runSubscription,
  updateSubscription,
} from "@/api/subscriptions";
import { useJobsStore } from "@/stores/jobsStore";
import { useJobPolling, isTerminal } from "@/hooks/useJobPolling";
import ActiveRunsBanner from "@/components/ActiveRunsBanner";

function formatLastRun(j: { status: string; finished_at?: string; error?: string }): string {
  const ts = j.finished_at ? new Date(j.finished_at).toLocaleTimeString() : "just now";
  if (j.status === "succeeded") return `✓ ${ts}`;
  if (j.status === "failed" || j.status === "cancelled") {
    return `✗ ${ts}${j.error ? ` · ${j.error.slice(0, 40)}` : ""}`;
  }
  return ts;
}

export default function SubscriptionPage() {
  const qc = useQueryClient();
  const subsQ = useQuery({
    queryKey: ["subscriptions"],
    queryFn: listSubscriptions,
  });

  const [editorOpen, setEditorOpen] = useState(false);
  const [editing, setEditing] = useState<SubscriptionDTO | null>(null);
  const [originalName, setOriginalName] = useState<string | null>(null);

  const upsertJob = useJobsStore((s) => s.upsert);
  const jobs = useJobsStore((s) => s.jobs);
  useJobPolling(2000);

  // 每个 subscription 的活跃 job（最新一个非 terminal，或最新一个 terminal 用于 last-run 显示）
  const subJobs: Record<string, { running: boolean; lastRun?: string }> = {};
  Object.values(jobs)
    .filter((j) => j.name.startsWith("run-sub:"))
    .forEach((j) => {
      const name = j.name.replace(/^run-sub:/, "");
      const term = isTerminal(j.status);
      const prev = subJobs[name];
      // 没记录 → 写；已记录但是 terminal 且新的是 active → 覆盖；都 terminal → 取较新的
      if (!prev) {
        subJobs[name] = {
          running: !term,
          lastRun: term ? formatLastRun(j) : undefined,
        };
      } else if (!term && !prev.running) {
        subJobs[name] = { running: true, lastRun: prev.lastRun };
      }
    });

  const saveMut = useMutation({
    mutationFn: async (sub: SubscriptionDTO) => {
      if (originalName) {
        return updateSubscription(originalName, sub);
      }
      return createSubscription(sub);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["subscriptions"] });
      setEditorOpen(false);
      setEditing(null);
      setOriginalName(null);
    },
  });

  const deleteMut = useMutation({
    mutationFn: deleteSubscription,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["subscriptions"] }),
  });

  const runMut = useMutation({
    mutationFn: runSubscription,
    onSuccess: (r, name) =>
      upsertJob({
        job_id: r.job_id,
        name: `run-sub:${name}`,
        status: r.status,
        created_at: new Date().toISOString(),
        started_at: "",
        finished_at: "",
        error: "",
      }),
  });

  const openNew = () => {
    setEditing(null);
    setOriginalName(null);
    setEditorOpen(true);
  };
  const openEdit = (sub: SubscriptionDTO) => {
    setEditing(sub);
    setOriginalName(sub.name);
    setEditorOpen(true);
  };

  return (
    <div className="flex flex-col h-full" style={{ background: "var(--bg)" }}>
      <header
        className="flex items-baseline justify-between px-6 py-4 border-b"
        style={{ borderColor: "var(--rule)", background: "var(--bg)" }}
      >
        <div>
          <h1
            className="text-2xl"
            style={{
              fontFamily: "var(--font-serif)",
              color: "var(--fg)",
              letterSpacing: "-0.01em",
            }}
          >
            Subscriptions
          </h1>
          <p className="text-xs mt-0.5" style={{ color: "var(--fg-muted)" }}>
            interest digests delivered on a schedule
          </p>
        </div>
        <Button onClick={openNew}>+ New subscription</Button>
      </header>

      <ActiveRunsBanner />

      <ScrollArea className="flex-1">
        <div className="px-6 py-4 max-w-3xl mx-auto">
          {subsQ.isLoading ? (
            <p className="text-sm" style={{ color: "var(--fg-muted)" }}>
              Loading…
            </p>
          ) : subsQ.data && subsQ.data.length > 0 ? (
            subsQ.data.map((sub) => (
              <SubscriptionCard
                key={sub.name}
                sub={sub}
                onEdit={() => openEdit(sub)}
                onRun={() => runMut.mutate(sub.name)}
                onDelete={() => {
                  if (window.confirm(`Delete "${sub.name}"?`)) {
                    deleteMut.mutate(sub.name);
                  }
                }}
                running={
                  (runMut.isPending && runMut.variables === sub.name) ||
                  subJobs[sub.name]?.running ||
                  false
                }
                lastRun={subJobs[sub.name]?.lastRun}
              />
            ))
          ) : (
            <div
              className="px-4 py-10 text-center"
              style={{
                background: "var(--bg-soft)",
                border: "1px dashed var(--rule)",
                borderRadius: "var(--radius-card)",
                color: "var(--fg-muted)",
              }}
            >
              <p
                className="text-base mb-1"
                style={{ fontFamily: "var(--font-serif)", color: "var(--fg)" }}
              >
                No subscriptions yet
              </p>
              <p className="text-xs">
                Click <em>+ New subscription</em> above to add one.
              </p>
            </div>
          )}
        </div>
      </ScrollArea>

      <SubscriptionEditor
        open={editorOpen}
        onOpenChange={(o) => {
          setEditorOpen(o);
          if (!o) {
            setEditing(null);
            setOriginalName(null);
          }
        }}
        initial={editing}
        onSave={(sub) => saveMut.mutate(sub)}
        saving={saveMut.isPending}
      />
    </div>
  );
}
