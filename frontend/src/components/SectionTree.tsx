import { cn } from "@/lib/utils";
import type { SectionDTO } from "@/api/papers";

interface SectionTreeProps {
  sections: SectionDTO[];
  activeMaterialId?: string | null;
  onSelect: (section: SectionDTO) => void;
}

export function SectionTree({
  sections,
  activeMaterialId,
  onSelect,
}: SectionTreeProps) {
  if (sections.length === 0) {
    return (
      <div className="p-3 text-xs text-muted-foreground">No sections.</div>
    );
  }
  return (
    <nav className="p-2 text-sm space-y-0.5">
      {sections.map((s) => {
        const indent = Math.max(0, (s.level || 1) - 1) * 12;
        const isActive = s.material_id === activeMaterialId;
        return (
          <button
            key={s.material_id}
            type="button"
            onClick={() => onSelect(s)}
            style={{ paddingLeft: 8 + indent }}
            className={cn(
              "w-full text-left py-1 pr-2 rounded text-xs hover:bg-slate-200/70 transition truncate",
              isActive ? "bg-slate-900 text-white hover:bg-slate-900" : "text-slate-700",
            )}
            title={s.path}
          >
            {s.path || `§${s.seq}`}
          </button>
        );
      })}
    </nav>
  );
}
