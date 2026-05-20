import type { TopicStateDTO } from "@/types/state";

interface Props {
  topic: TopicStateDTO;
}

function arrowForActivity(a: number): string {
  if (a > 0.5) return "\u2B06";
  if (a >= 0.2) return "\u2192";
  return "\u2B07";
}

export default function TopicBar({ topic }: Props) {
  const pct = Math.round(topic.activity * 100);
  const filled = Math.round(pct / 10);
  const empty = 10 - filled;
  const bar = "\u2588".repeat(filled) + "\u2591".repeat(empty);
  const arrow = arrowForActivity(topic.activity);

  return (
    <div
      className="flex items-center gap-3 px-4 py-2.5 mb-1.5"
      style={{
        background: "var(--bg)",
        border: "1px solid var(--rule)",
        borderRadius: "var(--radius-card)",
      }}
    >
      <span
        className="flex-1 min-w-0 truncate font-serif text-sm font-medium"
        style={{ color: "var(--fg)" }}
      >
        {topic.name}
      </span>

      <span
        className="font-mono text-xs shrink-0"
        style={{ color: "var(--fg-soft)" }}
      >
        {bar}
      </span>

      <span
        className="font-mono text-[11px] shrink-0 w-10 text-right"
        style={{ color: "var(--fg-soft)" }}
      >
        {topic.consolidation.toFixed(2)}
      </span>

      <span
        className="font-mono text-xs shrink-0 w-5 text-center"
        style={{
          color:
            topic.activity > 0.5
              ? "var(--accent)"
              : topic.activity >= 0.2
                ? "var(--fg-soft)"
                : "var(--counter-fg)",
        }}
      >
        {arrow}
      </span>
    </div>
  );
}
