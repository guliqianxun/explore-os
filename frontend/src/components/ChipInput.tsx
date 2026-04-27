// ft-027: editorial-style tag input. Press Enter / comma to commit a chip;
// click X to remove. Token-driven colors only (no hardcoded hex).
import { KeyboardEvent, useState } from "react";

interface Props {
  value: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
}

export default function ChipInput({ value, onChange, placeholder }: Props) {
  const [draft, setDraft] = useState("");

  const commit = () => {
    const t = draft.trim();
    if (!t) return;
    if (value.includes(t)) {
      setDraft("");
      return;
    }
    onChange([...value, t]);
    setDraft("");
  };

  const remove = (idx: number) => {
    const next = value.slice();
    next.splice(idx, 1);
    onChange(next);
  };

  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      commit();
    } else if (e.key === "Backspace" && draft === "" && value.length > 0) {
      e.preventDefault();
      remove(value.length - 1);
    }
  };

  return (
    <div
      className="flex flex-wrap gap-1.5 px-2 py-1.5 rounded border min-h-[2.25rem] focus-within:ring-1"
      style={{
        background: "var(--bg)",
        borderColor: "var(--rule)",
      }}
    >
      {value.map((chip, i) => (
        <span
          key={`${chip}-${i}`}
          className="inline-flex items-center gap-1 text-xs px-2 py-0.5"
          style={{
            background: "var(--accent-soft)",
            color: "var(--accent)",
            borderRadius: "var(--radius-chip)",
          }}
        >
          {chip}
          <button
            type="button"
            onClick={() => remove(i)}
            className="opacity-60 hover:opacity-100"
            aria-label={`remove ${chip}`}
          >
            ×
          </button>
        </span>
      ))}
      <input
        className="flex-1 min-w-[8rem] text-sm bg-transparent outline-none"
        style={{ color: "var(--fg)" }}
        placeholder={value.length === 0 ? placeholder : ""}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={onKey}
        onBlur={commit}
      />
    </div>
  );
}
