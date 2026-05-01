// ft-027: drag-or-click PDF dropzone (editorial styling, no third-party dep).
import { ChangeEvent, DragEvent, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

interface Props {
  onFile: (file: File) => void;
  disabled?: boolean;
}

export default function IngestDropzone({ onFile, disabled }: Props) {
  const { t } = useTranslation();
  const inputRef = useRef<HTMLInputElement>(null);
  const [hover, setHover] = useState(false);

  const pick = (f: File | null | undefined) => {
    if (!f) return;
    if (!f.name.toLowerCase().endsWith(".pdf")) {
      alert(t("ingest.drop_invalid"));
      return;
    }
    onFile(f);
  };

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setHover(false);
    if (disabled) return;
    pick(e.dataTransfer.files?.[0]);
  };

  const onChange = (e: ChangeEvent<HTMLInputElement>) => {
    pick(e.target.files?.[0]);
    e.target.value = "";
  };

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setHover(true);
      }}
      onDragLeave={() => setHover(false)}
      onDrop={onDrop}
      onClick={() => !disabled && inputRef.current?.click()}
      className="cursor-pointer flex flex-col items-center justify-center text-center px-6 py-10 transition"
      style={{
        background: hover ? "var(--accent-soft)" : "var(--bg-soft)",
        border: `1.5px dashed ${hover ? "var(--accent)" : "var(--rule)"}`,
        borderRadius: "var(--radius-card)",
        color: "var(--fg-soft)",
        opacity: disabled ? 0.5 : 1,
      }}
    >
      <p
        className="text-base"
        style={{ fontFamily: "var(--font-serif)", color: "var(--fg)" }}
      >
        {t("ingest.drop_pdf")}
      </p>
      <p className="text-xs mt-1" style={{ color: "var(--fg-muted)" }}>
        {t("ingest.drop_hint")}
      </p>
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,application/pdf"
        hidden
        onChange={onChange}
      />
    </div>
  );
}
