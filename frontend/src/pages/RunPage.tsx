import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  JobInfo,
  getJob,
  triggerExtract,
  triggerInterpret,
  triggerRender,
} from "@/api/jobs";
import { useJobsStore } from "@/stores/jobsStore";

const STATUS_TINT: Record<string, string> = {
  pending: "text-slate-600 bg-slate-100",
  running: "text-blue-700 bg-blue-100",
  succeeded: "text-emerald-700 bg-emerald-100",
  failed: "text-red-700 bg-red-100",
  cancelled: "text-amber-700 bg-amber-100",
};

export default function RunPage() {
  const [arxivId, setArxivId] = useState("");
  const jobs = useJobsStore((s) => s.jobs);
  const upsert = useJobsStore((s) => s.upsert);

  const extractMut = useMutation({
    mutationFn: (id: string) => triggerExtract(id),
    onSuccess: (r, id) =>
      upsert({
        job_id: r.job_id,
        name: `extract:${id}`,
        status: r.status,
        created_at: new Date().toISOString(),
        started_at: "",
        finished_at: "",
        error: "",
      }),
  });
  const interpretMut = useMutation({
    mutationFn: (id: string) => triggerInterpret(id),
    onSuccess: (r, id) =>
      upsert({
        job_id: r.job_id,
        name: `interpret:${id}`,
        status: r.status,
        created_at: new Date().toISOString(),
        started_at: "",
        finished_at: "",
        error: "",
      }),
  });
  const renderMut = useMutation({
    mutationFn: (id: string) => triggerRender(id),
    onSuccess: (r, id) =>
      upsert({
        job_id: r.job_id,
        name: `render:${id}`,
        status: r.status,
        created_at: new Date().toISOString(),
        started_at: "",
        finished_at: "",
        error: "",
      }),
  });

  // Poll any non-terminal job every 2s until it finishes.
  useEffect(() => {
    const pending = Object.values(jobs).filter(
      (j) => j.status === "pending" || j.status === "running",
    );
    if (pending.length === 0) return;
    const id = window.setInterval(async () => {
      for (const j of pending) {
        try {
          const fresh = await getJob(j.job_id);
          upsert(fresh);
        } catch {
          /* ignore transient */
        }
      }
    }, 2000);
    return () => window.clearInterval(id);
  }, [jobs, upsert]);

  const sorted: JobInfo[] = Object.values(jobs).sort((a, b) =>
    b.created_at.localeCompare(a.created_at),
  );

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between border-b bg-white px-4 py-2">
        <h1 className="text-base font-semibold">Run</h1>
      </div>
      <div className="p-4 space-y-3 max-w-3xl mx-auto w-full">
        <Card className="p-4 space-y-3">
          <div>
            <label className="text-xs font-medium">arxiv_id</label>
            <Input
              placeholder="e.g. 2502.00001"
              value={arxivId}
              onChange={(e) => setArxivId(e.target.value)}
            />
          </div>
          <div className="flex gap-2">
            <Button
              disabled={!arxivId || extractMut.isPending}
              onClick={() => extractMut.mutate(arxivId)}
            >
              Extract
            </Button>
            <Button
              variant="secondary"
              disabled={!arxivId || interpretMut.isPending}
              onClick={() => interpretMut.mutate(arxivId)}
            >
              Interpret
            </Button>
            <Button
              variant="outline"
              disabled={!arxivId || renderMut.isPending}
              onClick={() => renderMut.mutate(arxivId)}
            >
              Render
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            Triggers POST <code>/api/papers/&lt;id&gt;/extract|interpret|render/</code>.
            Status polled from <code>/api/jobs/&lt;job_id&gt;/</code> every 2s.
          </p>
        </Card>

        <div className="text-xs font-semibold text-slate-700 mt-4">
          Recent jobs ({sorted.length})
        </div>
        <ScrollArea className="flex-1">
          <div className="space-y-1.5">
            {sorted.length === 0 ? (
              <p className="text-sm text-muted-foreground">No jobs yet.</p>
            ) : (
              sorted.slice(0, 20).map((j) => (
                <Card
                  key={j.job_id}
                  className="p-2 flex items-center gap-3 text-xs"
                >
                  <span
                    className={
                      "px-2 py-0.5 rounded font-medium " +
                      (STATUS_TINT[j.status] ?? "text-slate-600 bg-slate-100")
                    }
                  >
                    {j.status}
                  </span>
                  <span className="font-mono">{j.name}</span>
                  <span className="text-muted-foreground truncate flex-1">
                    {j.job_id}
                  </span>
                  {j.error ? (
                    <span className="text-red-600 truncate max-w-[200px]" title={j.error}>
                      {j.error}
                    </span>
                  ) : null}
                </Card>
              ))
            )}
          </div>
        </ScrollArea>
      </div>
    </div>
  );
}
