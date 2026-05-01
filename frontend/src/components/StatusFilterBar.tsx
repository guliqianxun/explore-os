import { useTranslation } from "react-i18next";
import type { StatusFilter } from "@/types/paper";
import { cn } from "@/lib/utils";

interface StatusFilterBarProps {
  current: StatusFilter;
  /**
   * Per-status counts. `read` is the merged read_kept + read_dropped bucket;
   * `all` is the total. Missing entries render without a count.
   */
  counts: Partial<Record<StatusFilter, number>>;
  onChange: (s: StatusFilter) => void;
}

// i18n key suffix for each chip; resolved at render in ``papers.filter.*``.
const CHIPS: { value: StatusFilter; key: string }[] = [
  { value: "brief", key: "brief" },
  { value: "new", key: "new" },
  { value: "queued", key: "queued" },
  { value: "reading", key: "reading" },
  { value: "read", key: "read" },
  { value: "all", key: "all" },
];

/**
 * ft-028 status filter bar — sticky chips above the paper feed.
 *
 * `read` chip aggregates `read_kept + read_dropped` (the spec calls this out
 * explicitly: backend may not yet support `?status=read` so the page is in
 * charge of fanning out two requests when needed).
 */
export function StatusFilterBar({
  current,
  counts,
  onChange,
}: StatusFilterBarProps) {
  const { t } = useTranslation();
  return (
    <nav
      aria-label="Inbox status filter"
      className="flex items-center gap-2 flex-wrap"
    >
      {CHIPS.map(({ value, key }) => {
        const active = current === value;
        const count = counts[value];
        return (
          <button
            key={value}
            type="button"
            onClick={() => onChange(value)}
            aria-pressed={active}
            className={cn(
              "px-3 py-1 rounded-chip border font-sans",
              "text-[11px] tracking-[0.16em] uppercase transition-colors",
              active
                ? "border-[var(--fg)] bg-[var(--fg)] text-[var(--bg)]"
                : "border-[var(--rule)] text-[var(--fg-soft)] hover:border-[var(--fg)] hover:text-[var(--fg)]",
            )}
          >
            <span>{t(`papers.filter.${key}`)}</span>
            {typeof count === "number" ? (
              <span
                className={cn(
                  "ml-1.5 font-mono tracking-normal text-[10px]",
                  active ? "text-[var(--bg-soft)]" : "text-[var(--fg-muted)]",
                )}
              >
                {count}
              </span>
            ) : null}
          </button>
        );
      })}
    </nav>
  );
}
