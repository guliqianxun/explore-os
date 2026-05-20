import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type { ThreadDTO } from "@/types/state";

interface Props {
  thread: ThreadDTO;
}

export default function ThreadCard({ thread }: Props) {
  const { t } = useTranslation();
  const updated = new Date(thread.updated_at).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  return (
    <Link
      to={`/threads/${encodeURIComponent(thread.id)}`}
      className="block px-4 py-3 mb-1.5 transition hover:translate-x-0.5"
      style={{
        background: "var(--bg)",
        border: "1px solid var(--rule)",
        borderRadius: "var(--radius-card)",
        boxShadow: "var(--shadow-soft)",
      }}
    >
      <div className="flex items-center justify-between gap-3">
        <h4
          className="font-serif text-sm font-medium truncate min-w-0"
          style={{ color: "var(--fg)" }}
        >
          {thread.title}
        </h4>
        <div className="flex items-center gap-3 shrink-0">
          <span
            className="font-mono text-[11px]"
            style={{ color: "var(--fg-soft)" }}
          >
            {t("profile.notes_count", { count: thread.notes.length })}
          </span>
          <span
            className="font-mono text-[10px]"
            style={{ color: "var(--fg-muted)" }}
          >
            {updated}
          </span>
        </div>
      </div>
    </Link>
  );
}
