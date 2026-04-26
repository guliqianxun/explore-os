import { BookOpen, BookOpenCheck } from "lucide-react";

interface ReadingModeToggleProps {
  active: boolean;
  onToggle: () => void;
}

/**
 * ft-026 reading-mode toggle (top-right). When active, the page should add
 * `reading-mode` to a parent container — utility classes in globals.css
 * (`.reading-mode-hide`, `.reading-mode .prose-paper`) reshape the page.
 */
export function ReadingModeToggle({ active, onToggle }: ReadingModeToggleProps) {
  const Icon = active ? BookOpenCheck : BookOpen;
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={active}
      aria-label={active ? "Exit reading mode" : "Enter reading mode"}
      className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full
                  border text-xs font-sans transition
                  ${active
                    ? "bg-[var(--accent)] text-[var(--accent-fg)] border-[var(--accent)]"
                    : "bg-[var(--bg)] text-[var(--fg-soft)] border-[var(--rule)] hover:border-[var(--accent)] hover:text-[var(--accent)]"}`}
    >
      <Icon className="h-3.5 w-3.5" />
      {active ? "Reading" : "Read mode"}
    </button>
  );
}
