// ft-027: editorial-style subscription card.
import { Button } from "@/components/ui/button";
import type { SubscriptionDTO } from "@/api/subscriptions";

interface Props {
  sub: SubscriptionDTO;
  onEdit: () => void;
  onRun: () => void;
  onDelete: () => void;
  running?: boolean;
  lastRun?: string;
}

export default function SubscriptionCard({
  sub,
  onEdit,
  onRun,
  onDelete,
  running,
  lastRun,
}: Props) {
  const sourceLabels = (sub.sources || []).map((s) => s.key).join(" · ") || "—";
  const deliveryLabels =
    (sub.deliveries || [])
      .map((d) => `${d.channel}${d.to ? `→${d.to}` : ""}`)
      .join(" · ") || "—";
  const schedule = sub.deliveries?.[0]?.schedule || "—";

  return (
    <article
      className="p-4 mb-3"
      style={{
        background: "var(--bg)",
        border: "1px solid var(--rule)",
        borderRadius: "var(--radius-card)",
        boxShadow: "var(--shadow-soft)",
      }}
    >
      <header className="flex items-start justify-between gap-3 mb-2">
        <div className="min-w-0 flex-1">
          <h3
            className="text-lg font-semibold truncate"
            style={{
              fontFamily: "var(--font-serif)",
              color: "var(--fg)",
              letterSpacing: "-0.005em",
            }}
          >
            {sub.name}
          </h3>
          {!sub.enabled && (
            <span
              className="text-[11px] uppercase tracking-wide"
              style={{ color: "var(--fg-muted)" }}
            >
              disabled
            </span>
          )}
        </div>
        <div className="flex gap-1.5 shrink-0">
          <Button size="sm" variant="outline" onClick={onEdit}>
            Edit
          </Button>
          <Button size="sm" onClick={onRun} disabled={running}>
            {running ? "Running…" : "Run now"}
          </Button>
          <Button size="sm" variant="ghost" onClick={onDelete}>
            ×
          </Button>
        </div>
      </header>

      {sub.interests && sub.interests.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-2">
          {sub.interests.map((kw) => (
            <span
              key={kw}
              className="text-xs px-2 py-0.5"
              style={{
                background: "var(--accent-soft)",
                color: "var(--accent)",
                borderRadius: "var(--radius-chip)",
              }}
            >
              {kw}
            </span>
          ))}
        </div>
      )}

      <dl
        className="grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1 text-xs"
        style={{ color: "var(--fg-soft)" }}
      >
        <dt style={{ color: "var(--fg-muted)" }}>sources</dt>
        <dd>{sourceLabels}</dd>
        <dt style={{ color: "var(--fg-muted)" }}>delivery</dt>
        <dd className="truncate">{deliveryLabels}</dd>
        <dt style={{ color: "var(--fg-muted)" }}>schedule</dt>
        <dd>
          <code style={{ fontFamily: "var(--font-mono)" }}>{schedule}</code>
        </dd>
        {lastRun && (
          <>
            <dt style={{ color: "var(--fg-muted)" }}>last run</dt>
            <dd>{lastRun}</dd>
          </>
        )}
      </dl>
    </article>
  );
}
