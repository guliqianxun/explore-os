import { useEffect } from "react";
import { X } from "lucide-react";

interface ClaimDrawerProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
}

/**
 * ft-026 right-side drawer for claims. Slides in/out (240ms ease).
 * Width: 540px (matches --drawer-w token). Sits on top of layout flow;
 * page is responsible for adding right padding when drawer is open if a
 * non-overlay layout is desired. Default: overlay style with subtle
 * left border + soft shadow for visual separation.
 */
export function ClaimDrawer({ open, onClose, title, children }: ClaimDrawerProps) {
  // ESC closes drawer.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <aside
      aria-hidden={!open}
      aria-label="Claims drawer"
      className={`drawer-panel fixed top-0 right-0 h-full
                  w-full sm:w-[540px] max-w-drawer
                  bg-[var(--bg)] border-l border-[var(--rule)]
                  shadow-lift z-40 flex flex-col
                  ${open ? "translate-x-0" : "translate-x-full"}`}
    >
      <header className="flex items-center justify-between px-5 py-4
                         border-b border-[var(--rule)] bg-[var(--bg)]">
        <h3 className="font-sans text-xs uppercase tracking-[0.14em]
                       text-[var(--fg-muted)] font-medium">
          {title ?? "Claims"}
        </h3>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close claims drawer"
          className="p-1 rounded hover:bg-[var(--bg-soft)] text-[var(--fg-soft)]"
        >
          <X className="h-4 w-4" />
        </button>
      </header>
      <div className="flex-1 overflow-y-auto px-5 py-6 space-y-6">{children}</div>
    </aside>
  );
}
