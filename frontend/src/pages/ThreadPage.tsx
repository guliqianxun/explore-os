import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  addThreadNote,
  createThread,
  deleteThread,
  listThreads,
} from "@/api/state";
function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const noteRule = {
  background: "var(--rule)",
};

export default function ThreadPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const isNew = id === "new";
  const threadId = id && !isNew ? Number(id) : null;

  const threadsQ = useQuery({
    queryKey: ["threads"],
    queryFn: () => listThreads(),
    enabled: !isNew,
  });

  const thread = useMemo(() => {
    if (isNew || !threadsQ.data || !threadId) return null;
    return threadsQ.data.find((t) => t.id === threadId) ?? null;
  }, [isNew, threadsQ.data, threadId]);

  // ── new thread creation ──
  const [newTitle, setNewTitle] = useState("");

  const createMut = useMutation({
    mutationFn: () => createThread(newTitle),
    onSuccess: (data) => {
      void qc.invalidateQueries({ queryKey: ["threads"] });
      navigate(`/threads/${data.id}`, { replace: true });
    },
  });

  // ── add note ──
  const [noteBody, setNoteBody] = useState("");
  const [refClaimInput, setRefClaimInput] = useState("");
  const [refClaims, setRefClaims] = useState<string[]>([]);

  const addNoteMut = useMutation({
    mutationFn: () =>
      addThreadNote(threadId!, noteBody, refClaims.length > 0 ? refClaims : undefined),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["threads"] });
      setNoteBody("");
      setRefClaims([]);
    },
  });

  const addRefClaim = () => {
    const v = refClaimInput.trim();
    if (v && !refClaims.includes(v)) {
      setRefClaims((prev) => [...prev, v]);
    }
    setRefClaimInput("");
  };

  const removeRefClaim = (cid: string) => {
    setRefClaims((prev) => prev.filter((c) => c !== cid));
  };

  // ── export .md ──
  const handleExport = () => {
    if (!thread) return;
    const lines: string[] = [];
    lines.push(`# ${thread.title}`);
    lines.push("");
    if (thread.paper_keys.length > 0) {
      lines.push("## Papers");
      thread.paper_keys.forEach((k) => lines.push(`- ${k}`));
      lines.push("");
    }
    if (thread.viewpoint_ids.length > 0) {
      lines.push("## Viewpoints");
      thread.viewpoint_ids.forEach((v) => lines.push(`- \`${v}\``));
      lines.push("");
    }
    lines.push("## Notes");
    lines.push("");
    thread.notes.forEach((n) => {
      lines.push(`> ${fmtDate(n.created_at)}`);
      lines.push("");
      lines.push(n.body);
      lines.push("");
      lines.push("---");
      lines.push("");
    });

    const blob = new Blob([lines.join("\n")], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${thread.title.replace(/[/\\?%*:|"<>]/g, "_")}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // ── delete thread ──
  const deleteMut = useMutation({
    mutationFn: () => deleteThread(threadId!),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["threads"] });
      navigate("/", { replace: true });
    },
    onError: () => {
      alert("Failed to delete thread (backend may not support DELETE yet).");
    },
  });

  // ── new thread form ──
  if (isNew) {
    return (
      <div
        className="flex flex-col h-full"
        style={{ background: "var(--bg)" }}
      >
        <header
          className="px-6 py-4 border-b shrink-0"
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
            New Thread
          </h1>
        </header>
        <div className="flex-1 flex items-start justify-center pt-20">
          <div className="w-full max-w-lg space-y-4 px-4">
            <div>
              <label
                className="text-sm mb-1 block"
                style={{ color: "var(--fg-soft)" }}
              >
                Title
              </label>
              <Input
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                placeholder="e.g. Diffusion for video: what matters"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && newTitle.trim()) {
                    createMut.mutate();
                  }
                }}
              />
            </div>
            <div className="flex gap-2">
              <Button
                onClick={() => navigate("/")}
                variant="outline"
              >
                Back
              </Button>
              <Button
                onClick={() => createMut.mutate()}
                disabled={!newTitle.trim() || createMut.isPending}
              >
                {createMut.isPending ? "Creating..." : "Create Thread"}
              </Button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ── loading / missing ──
  if (threadsQ.isLoading) {
    return (
      <div
        className="flex items-center justify-center h-full"
        style={{ background: "var(--bg)" }}
      >
        <p className="font-serif text-sm" style={{ color: "var(--fg-muted)" }}>
          Loading…
        </p>
      </div>
    );
  }
  if (!thread) {
    return (
      <div
        className="flex items-center justify-center h-full"
        style={{ background: "var(--bg)" }}
      >
        <p className="font-serif text-sm" style={{ color: "var(--fg-muted)" }}>
          Thread not found.
        </p>
      </div>
    );
  }

  // ── existing thread view ──
  return (
    <div
      className="flex flex-col h-full"
      style={{ background: "var(--bg)" }}
    >
      <header
        className="px-6 py-4 border-b shrink-0 space-y-3"
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
          {thread.title}
        </h1>

        {thread.paper_keys.length > 0 && (
          <div className="flex items-center gap-1.5 flex-wrap">
            <span
              className="text-[10px] uppercase tracking-wider"
              style={{ color: "var(--fg-muted)" }}
            >
              Papers
            </span>
            {thread.paper_keys.map((k) => (
              <Badge key={k} variant="secondary" className="font-mono text-[10px]">
                {k}
              </Badge>
            ))}
          </div>
        )}

        {thread.viewpoint_ids.length > 0 && (
          <div className="flex items-center gap-1.5 flex-wrap">
            <span
              className="text-[10px] uppercase tracking-wider"
              style={{ color: "var(--fg-muted)" }}
            >
              Viewpoints
            </span>
            {thread.viewpoint_ids.map((v) => (
              <Badge key={v} variant="outline" className="font-mono text-[10px]">
                {v}
              </Badge>
            ))}
          </div>
        )}
      </header>

      <ScrollArea className="flex-1">
        <div className="px-6 py-4 max-w-3xl mx-auto space-y-6">
          {/* ── notes ── */}
          <section>
            <h2
              className="text-sm font-semibold mb-3 uppercase tracking-wider"
              style={{ color: "var(--fg-muted)" }}
            >
              Notes
            </h2>
            {thread.notes.length === 0 ? (
              <p
                className="text-sm italic py-6 text-center"
                style={{ color: "var(--fg-muted)" }}
              >
                No notes yet.
              </p>
            ) : (
              <div className="space-y-4">
                {thread.notes.map((n) => (
                  <div key={n.id}>
                    <div
                      className="flex items-center gap-2 mb-1"
                    >
                      <span
                        className="text-[11px] font-mono"
                        style={{ color: "var(--fg-muted)" }}
                      >
                        {fmtDate(n.created_at)}
                      </span>
                    </div>
                    <p
                      className="text-sm whitespace-pre-wrap leading-relaxed"
                      style={{ color: "var(--fg)" }}
                    >
                      {n.body}
                    </p>
                    <div className="mt-2 h-px" style={noteRule} />
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* ── add note ── */}
          <section
            className="p-4 rounded-lg border"
            style={{
              borderColor: "var(--rule)",
              background: "var(--bg-soft)",
            }}
          >
            <h3
              className="text-sm font-semibold mb-3"
              style={{ color: "var(--fg)" }}
            >
              Add note
            </h3>
            <Textarea
              value={noteBody}
              onChange={(e) => setNoteBody(e.target.value)}
              placeholder="Write your note..."
              rows={4}
              className="mb-3"
            />

            {refClaims.length > 0 && (
              <div className="flex items-center gap-1.5 flex-wrap mb-3">
                <span
                  className="text-[10px] uppercase tracking-wider"
                  style={{ color: "var(--fg-muted)" }}
                >
                  Refs
                </span>
                {refClaims.map((c) => (
                  <Badge key={c} variant="secondary" className="font-mono text-[10px] gap-1">
                    {c}
                    <button
                      type="button"
                      onClick={() => removeRefClaim(c)}
                      className="ml-0.5 hover:text-[var(--counter-fg)]"
                    >
                      ×
                    </button>
                  </Badge>
                ))}
              </div>
            )}

            <div className="flex gap-2 items-center mb-3">
              <Input
                value={refClaimInput}
                onChange={(e) => setRefClaimInput(e.target.value)}
                placeholder="Add claim ref..."
                className="h-8 text-xs"
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addRefClaim();
                  }
                }}
              />
              <Button
                variant="outline"
                size="sm"
                onClick={addRefClaim}
                disabled={!refClaimInput.trim()}
                className="shrink-0 h-8 text-xs"
              >
                + Add
              </Button>
            </div>

            <Button
              onClick={() => addNoteMut.mutate()}
              disabled={!noteBody.trim() || addNoteMut.isPending}
              size="sm"
            >
              {addNoteMut.isPending ? "Submitting..." : "Submit note"}
            </Button>
          </section>
        </div>
      </ScrollArea>

      {/* ── bottom bar ── */}
      <footer
        className="flex items-center gap-3 px-6 py-3 border-t shrink-0"
        style={{ borderColor: "var(--rule)", background: "var(--bg)" }}
      >
        <Button
          variant="destructive"
          size="sm"
          onClick={() => {
            if (window.confirm("Delete this thread?")) {
              deleteMut.mutate();
            }
          }}
          disabled={deleteMut.isPending}
        >
          {deleteMut.isPending ? "Deleting..." : "Delete thread"}
        </Button>
        <Button variant="outline" size="sm" onClick={handleExport}>
          Export as .md
        </Button>
      </footer>
    </div>
  );
}
