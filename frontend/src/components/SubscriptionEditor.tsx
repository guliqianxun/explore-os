// ft-027: editor modal for SubscriptionDTO. Form-driven primary path,
// collapsible Advanced YAML for power users (read-only preview;
// editing the YAML disables the form to avoid drift).
import { useEffect, useMemo, useState } from "react";

import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import ChipInput from "@/components/ChipInput";
import type { SubscriptionDTO } from "@/api/subscriptions";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initial: SubscriptionDTO | null;
  onSave: (sub: SubscriptionDTO) => void;
  saving?: boolean;
}

const KNOWN_SOURCES = [
  { key: "arxiv", label: "arXiv" },
  { key: "hf_papers", label: "HF Papers" },
  { key: "github", label: "GitHub (planned)" },
];

const SCHEDULE_PRESETS = [
  { id: "daily8", label: "Daily 08:00", cron: "0 8 * * *" },
  { id: "weeklyMon9", label: "Mon 09:00", cron: "0 9 * * 1" },
  { id: "custom", label: "Custom", cron: "" },
];

// minimal indented YAML-ish preview (read-only). Not a parser; only for display.
function toYaml(sub: SubscriptionDTO): string {
  const lines: string[] = ["subscriptions:"];
  const push = (depth: number, s: string) =>
    lines.push("  ".repeat(depth) + s);
  push(1, `- name: ${sub.name || ""}`);
  push(2, `enabled: ${sub.enabled !== false}`);
  if (sub.interests?.length) {
    push(2, "interests:");
    sub.interests.forEach((k) => push(3, `- ${JSON.stringify(k)}`));
  }
  if (sub.exclude?.length) {
    push(2, "exclude:");
    sub.exclude.forEach((k) => push(3, `- ${JSON.stringify(k)}`));
  }
  if (sub.sources?.length) {
    push(2, "sources:");
    sub.sources.forEach((s) => {
      push(3, `- key: ${s.key}`);
      const params = s.params || {};
      const ks = Object.keys(params);
      if (ks.length) {
        push(4, "params:");
        ks.forEach((k) => {
          const v = params[k];
          if (Array.isArray(v)) {
            push(5, `${k}: [${v.map((x) => JSON.stringify(x)).join(", ")}]`);
          } else {
            push(5, `${k}: ${JSON.stringify(v)}`);
          }
        });
      }
    });
  }
  if (sub.deliveries?.length) {
    push(2, "deliveries:");
    sub.deliveries.forEach((d) => {
      push(3, `- channel: ${d.channel}`);
      if (d.to) push(4, `to: ${JSON.stringify(d.to)}`);
      if (d.depth) push(4, `depth: ${d.depth}`);
      if (d.schedule) push(4, `schedule: ${JSON.stringify(d.schedule)}`);
      if (typeof d.max_items === "number") push(4, `max_items: ${d.max_items}`);
    });
  }
  if (sub.perspective && (sub.perspective.preset || sub.perspective.custom)) {
    push(2, "perspective:");
    if (sub.perspective.preset) push(3, `preset: ${sub.perspective.preset}`);
    if (sub.perspective.custom)
      push(3, `custom: ${JSON.stringify(sub.perspective.custom)}`);
  }
  return lines.join("\n");
}

function emptyDraft(): SubscriptionDTO {
  return {
    name: "",
    enabled: true,
    interests: [],
    exclude: [],
    sources: [{ key: "arxiv", params: { since_days: 1, limit: 30 } }],
    deliveries: [
      {
        channel: "email",
        to: "",
        depth: "tldr",
        schedule: "0 8 * * *",
        max_items: 15,
      },
    ],
    perspective: { preset: "researcher", custom: "" },
  };
}

export default function SubscriptionEditor({
  open,
  onOpenChange,
  initial,
  onSave,
  saving,
}: Props) {
  const [draft, setDraft] = useState<SubscriptionDTO>(emptyDraft());
  const [advancedOpen, setAdvancedOpen] = useState(false);

  useEffect(() => {
    if (open) {
      setDraft(initial ? (JSON.parse(JSON.stringify(initial)) as SubscriptionDTO) : emptyDraft());
      setAdvancedOpen(false);
    }
  }, [open, initial]);

  const isEdit = Boolean(initial?.name);

  const sourceKeys = new Set((draft.sources || []).map((s) => s.key));
  const toggleSource = (key: string) => {
    const next = sourceKeys.has(key)
      ? (draft.sources || []).filter((s) => s.key !== key)
      : [
          ...(draft.sources || []),
          { key, params: key === "arxiv" ? { since_days: 1, limit: 30 } : {} },
        ];
    setDraft({ ...draft, sources: next });
  };

  const arxivIdx = (draft.sources || []).findIndex((s) => s.key === "arxiv");
  const arxivCats = useMemo<string[]>(() => {
    if (arxivIdx < 0) return [];
    const p = draft.sources[arxivIdx].params || {};
    return Array.isArray(p.categories) ? (p.categories as string[]) : [];
  }, [arxivIdx, draft.sources]);
  const setArxivCats = (next: string[]) => {
    if (arxivIdx < 0) return;
    const sources = draft.sources.slice();
    sources[arxivIdx] = {
      ...sources[arxivIdx],
      params: { ...(sources[arxivIdx].params || {}), categories: next },
    };
    setDraft({ ...draft, sources });
  };

  const delivery = draft.deliveries?.[0] || {
    channel: "email",
    to: "",
    depth: "tldr",
    schedule: "",
    max_items: 15,
  };
  const setDelivery = (patch: Partial<typeof delivery>) => {
    const next = [{ ...delivery, ...patch }, ...(draft.deliveries || []).slice(1)];
    setDraft({ ...draft, deliveries: next });
  };

  const currentPreset =
    SCHEDULE_PRESETS.find((p) => p.cron === delivery.schedule)?.id || "custom";

  const yamlPreview = useMemo(() => toYaml(draft), [draft]);

  const canSave = draft.name.trim().length > 0 && !saving;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle style={{ fontFamily: "var(--font-serif)" }}>
            {isEdit ? "Edit subscription" : "New subscription"}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 text-sm">
          {/* name */}
          <div>
            <label className="text-xs font-medium" style={{ color: "var(--fg-soft)" }}>
              Name
            </label>
            <Input
              value={draft.name}
              onChange={(e) => setDraft({ ...draft, name: e.target.value })}
              placeholder="e.g. video-generation-daily"
            />
          </div>

          {/* interests */}
          <div>
            <label className="text-xs font-medium" style={{ color: "var(--fg-soft)" }}>
              Interests
            </label>
            <ChipInput
              value={draft.interests || []}
              onChange={(v) => setDraft({ ...draft, interests: v })}
              placeholder="press Enter to add a keyword"
            />
          </div>

          {/* exclude */}
          <div>
            <label className="text-xs font-medium" style={{ color: "var(--fg-soft)" }}>
              Exclude
            </label>
            <ChipInput
              value={draft.exclude || []}
              onChange={(v) => setDraft({ ...draft, exclude: v })}
              placeholder="negative keywords (optional)"
            />
          </div>

          {/* sources */}
          <div>
            <label className="text-xs font-medium" style={{ color: "var(--fg-soft)" }}>
              Sources
            </label>
            <div className="flex flex-wrap gap-3 mt-1">
              {KNOWN_SOURCES.map((s) => (
                <label key={s.key} className="inline-flex items-center gap-1.5 text-sm">
                  <input
                    type="checkbox"
                    checked={sourceKeys.has(s.key)}
                    onChange={() => toggleSource(s.key)}
                  />
                  {s.label}
                </label>
              ))}
            </div>
            {sourceKeys.has("arxiv") && (
              <div className="mt-2">
                <label className="text-xs" style={{ color: "var(--fg-muted)" }}>
                  arXiv categories
                </label>
                <ChipInput
                  value={arxivCats}
                  onChange={setArxivCats}
                  placeholder="cs.CV, cs.LG, …"
                />
              </div>
            )}
          </div>

          {/* schedule */}
          <div>
            <label className="text-xs font-medium" style={{ color: "var(--fg-soft)" }}>
              Schedule
            </label>
            <div className="flex gap-3 items-center mt-1">
              {SCHEDULE_PRESETS.map((p) => (
                <label key={p.id} className="inline-flex items-center gap-1.5 text-sm">
                  <input
                    type="radio"
                    name="schedule-preset"
                    checked={currentPreset === p.id}
                    onChange={() => setDelivery({ schedule: p.cron })}
                  />
                  {p.label}
                </label>
              ))}
            </div>
            {currentPreset === "custom" && (
              <Input
                className="mt-1 font-mono text-xs"
                value={delivery.schedule || ""}
                onChange={(e) => setDelivery({ schedule: e.target.value })}
                placeholder="cron e.g. 0 8 * * *"
              />
            )}
          </div>

          {/* delivery */}
          <div>
            <label className="text-xs font-medium" style={{ color: "var(--fg-soft)" }}>
              Delivery
            </label>
            <div className="flex gap-3 items-center mt-1">
              <label className="inline-flex items-center gap-1.5 text-sm">
                <input
                  type="radio"
                  checked={delivery.channel === "email"}
                  onChange={() => setDelivery({ channel: "email" })}
                />
                Email
              </label>
              <label className="inline-flex items-center gap-1.5 text-sm">
                <input
                  type="radio"
                  checked={delivery.channel === "outbox"}
                  onChange={() => setDelivery({ channel: "outbox" })}
                />
                Outbox-only (.eml on disk)
              </label>
            </div>
            {delivery.channel === "email" && (
              <Input
                className="mt-1"
                value={delivery.to || ""}
                onChange={(e) => setDelivery({ to: e.target.value })}
                placeholder="to@example.com"
              />
            )}
          </div>

          {/* enabled */}
          <div>
            <label className="inline-flex items-center gap-1.5 text-sm">
              <input
                type="checkbox"
                checked={draft.enabled !== false}
                onChange={(e) => setDraft({ ...draft, enabled: e.target.checked })}
              />
              Enabled
            </label>
          </div>

          {/* advanced */}
          <details
            open={advancedOpen}
            onToggle={(e) => setAdvancedOpen((e.target as HTMLDetailsElement).open)}
            className="border-t pt-3"
            style={{ borderColor: "var(--rule)" }}
          >
            <summary
              className="cursor-pointer text-xs uppercase tracking-wide"
              style={{ color: "var(--fg-muted)" }}
            >
              Advanced — YAML preview
            </summary>
            <Textarea
              className="mt-2 font-mono text-xs"
              rows={10}
              value={yamlPreview}
              readOnly
            />
            <p className="text-xs mt-1" style={{ color: "var(--fg-muted)" }}>
              read-only preview; edits land via the form above
            </p>
          </details>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={() => onSave(draft)} disabled={!canSave}>
            {saving ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
