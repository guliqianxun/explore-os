// ft-027: replaces RunPage. Three entry points (PDF / arXiv / URL), then
// shows in-progress ingest jobs with 3-stage chain status.
import { useEffect, useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";

import IngestDropzone from "@/components/IngestDropzone";
import IngestProgressItem from "@/components/IngestProgressItem";
import {
  IngestResponse,
  ingestArxiv,
  ingestUpload,
  ingestUrl,
} from "@/api/ingest";
import { getJob } from "@/api/jobs";
import { useJobsStore } from "@/stores/jobsStore";

interface JobMeta {
  paperId: string;
}

export default function IngestPage() {
  const [arxivId, setArxivId] = useState("");
  const [url, setUrl] = useState("");

  // job_id → paper_id mapping (we only have it at submission time)
  const [meta, setMeta] = useState<Record<string, JobMeta>>({});

  const jobs = useJobsStore((s) => s.jobs);
  const upsert = useJobsStore((s) => s.upsert);

  const trackResp = (r: IngestResponse) => {
    setMeta((m) => ({ ...m, [r.job_id]: { paperId: r.paper_id } }));
    upsert({
      job_id: r.job_id,
      name: `ingest:${r.paper_id}`,
      status: r.status,
      created_at: new Date().toISOString(),
      started_at: "",
      finished_at: "",
      error: "",
    });
  };

  const uploadMut = useMutation({
    mutationFn: (f: File) => ingestUpload(f),
    onSuccess: trackResp,
    onError: (e: unknown) => alert(`Upload failed: ${(e as Error).message}`),
  });

  const arxivMut = useMutation({
    mutationFn: (id: string) => ingestArxiv(id),
    onSuccess: (r) => {
      trackResp(r);
      setArxivId("");
    },
    onError: (e: unknown) => alert(`arXiv fetch failed: ${(e as Error).message}`),
  });

  const urlMut = useMutation({
    mutationFn: (u: string) => ingestUrl(u),
    onSuccess: (r) => {
      trackResp(r);
      setUrl("");
    },
    onError: (e: unknown) => alert(`URL fetch failed: ${(e as Error).message}`),
  });

  // Poll non-terminal ingest jobs every 2s.
  useEffect(() => {
    const ingestJobs = Object.values(jobs).filter(
      (j) =>
        j.name.startsWith("ingest:") &&
        (j.status === "queued" || j.status === "running" || j.status === "pending"),
    );
    if (ingestJobs.length === 0) return;
    const id = window.setInterval(async () => {
      for (const j of ingestJobs) {
        try {
          const fresh = await getJob(j.job_id);
          upsert(fresh);
        } catch {
          /* transient */
        }
      }
    }, 2000);
    return () => window.clearInterval(id);
  }, [jobs, upsert]);

  const ingestList = useMemo(
    () =>
      Object.values(jobs)
        .filter((j) => j.name.startsWith("ingest:"))
        .sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [jobs],
  );

  const arxivValid = /^\d{4}\.\d{4,5}(v\d+)?$/.test(arxivId.trim());

  return (
    <div className="flex flex-col h-full" style={{ background: "var(--bg)" }}>
      <header
        className="px-6 py-4 border-b"
        style={{ borderColor: "var(--rule)", background: "var(--bg)" }}
      >
        <h1
          className="text-2xl"
          style={{
            fontFamily: "var(--font-serif)",
            color: "var(--fg)",
            letterSpacing: "-0.01em",
          }}
        >
          Ingest a paper
        </h1>
        <p className="text-xs mt-0.5" style={{ color: "var(--fg-muted)" }}>
          drop a PDF, paste an arXiv id, or fetch from a URL — we extract,
          interpret, and render
        </p>
      </header>

      <ScrollArea className="flex-1">
        <div className="px-6 py-5 max-w-3xl mx-auto space-y-5">
          {/* PDF dropzone */}
          <section>
            <IngestDropzone
              onFile={(f) => uploadMut.mutate(f)}
              disabled={uploadMut.isPending}
            />
          </section>

          {/* arXiv id */}
          <Divider label="or paste an arXiv id" />
          <section className="flex gap-2">
            <Input
              placeholder="e.g. 2401.12345"
              value={arxivId}
              onChange={(e) => setArxivId(e.target.value)}
              className="font-mono"
            />
            <Button
              onClick={() => arxivMut.mutate(arxivId.trim())}
              disabled={!arxivValid || arxivMut.isPending}
            >
              {arxivMut.isPending ? "Fetching…" : "Fetch"}
            </Button>
          </section>

          {/* URL */}
          <Divider label="or from a URL" />
          <section className="flex gap-2">
            <Input
              placeholder="https://arxiv.org/pdf/2401.12345.pdf"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
            />
            <Button
              onClick={() => urlMut.mutate(url.trim())}
              disabled={!url || urlMut.isPending}
            >
              {urlMut.isPending ? "Fetching…" : "Fetch"}
            </Button>
          </section>

          {/* In progress */}
          <section className="pt-4">
            <h2
              className="text-base mb-2"
              style={{
                fontFamily: "var(--font-serif)",
                color: "var(--fg)",
              }}
            >
              In progress ({ingestList.length})
            </h2>
            {ingestList.length === 0 ? (
              <p className="text-sm" style={{ color: "var(--fg-muted)" }}>
                No ingest jobs yet.
              </p>
            ) : (
              ingestList.map((j) => (
                <IngestProgressItem
                  key={j.job_id}
                  job={j}
                  paperId={meta[j.job_id]?.paperId || j.name.replace(/^ingest:/, "")}
                />
              ))
            )}
          </section>
        </div>
      </ScrollArea>
    </div>
  );
}

function Divider({ label }: { label: string }) {
  return (
    <div
      className="flex items-center gap-3 text-xs uppercase tracking-wider"
      style={{ color: "var(--fg-muted)" }}
    >
      <span
        className="flex-1 h-px"
        style={{ background: "var(--rule)" }}
      />
      <span>{label}</span>
      <span className="flex-1 h-px" style={{ background: "var(--rule)" }} />
    </div>
  );
}
