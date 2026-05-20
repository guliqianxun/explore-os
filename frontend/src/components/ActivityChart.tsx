import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import type { ActivityPointDTO } from "@/types/state";

interface Props {
  data: ActivityPointDTO[];
}

export default function ActivityChart({ data }: Props) {
  const { t } = useTranslation();

  const groups = useMemo(() => {
    const m = new Map<string, { date: string; value: number }[]>();
    for (const pt of data.slice(-30)) {
      const k = pt.topic_id || "_";
      if (!m.has(k)) m.set(k, []);
      m.get(k)!.push({ date: pt.date, value: pt.activity });
    }
    return Array.from(m.entries()).map(([topicId, points]) => ({
      topic: topicId === "_" ? t("profile.untagged") : topicId,
      points,
    }));
  }, [data, t]);

  if (data.length === 0) {
    return (
      <p
        className="font-serif text-sm italic py-3"
        style={{ color: "var(--fg-muted)" }}
      >
        {t("profile.no_activity")}
      </p>
    );
  }

  const colors = [
    "var(--accent)",
    "#b16100",
    "#5c4dab",
    "#a83422",
    "#6b5e2d",
    "#1f6e54",
  ];

  return (
    <div className="space-y-4">
      {groups.map(({ topic, points }, gi) => (
        <div key={topic}>
          <div
            className="font-mono text-[10px] uppercase tracking-[0.16em] mb-1.5"
            style={{ color: "var(--fg-muted)" }}
          >
            {topic}
          </div>
          <div className="flex items-end gap-[2px] h-20">
            {points.map((pt, i) => {
              const h = Math.max(2, Math.round(pt.value * 80));
              return (
                <div
                  key={i}
                  className="flex-1 rounded-[1px] transition-all hover:opacity-80"
                  title={`${pt.date}: ${(pt.value * 100).toFixed(0)}%`}
                  style={{
                    height: `${h}px`,
                    background: colors[gi % colors.length],
                    opacity: 0.82,
                  }}
                />
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
