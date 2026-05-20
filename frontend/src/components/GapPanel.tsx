import { useTranslation } from "react-i18next";
import type { GapsDTO } from "@/types/state";
import { Button } from "@/components/ui/button";

interface Props {
  gaps: GapsDTO;
}

export default function GapPanel({ gaps }: Props) {
  const { t } = useTranslation();
  const hasPrereqs = gaps.prereq.length > 0;
  const hasDecays = gaps.decay.length > 0;

  if (!hasPrereqs && !hasDecays) {
    return (
      <p
        className="font-serif text-sm italic py-3"
        style={{ color: "var(--fg-muted)" }}
      >
        {t("profile.no_gaps")}
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {hasPrereqs ? (
        <div>
          <h3
            className="font-mono text-[10px] uppercase tracking-[0.16em] mb-2"
            style={{ color: "var(--fg-muted)" }}
          >
            {t("profile.prereq_gaps")}
          </h3>
          <div className="space-y-2">
            {gaps.prereq.map((g, i) => (
              <div
                key={i}
                className="flex items-center justify-between gap-3 px-3 py-2 rounded-card"
                style={{
                  background: "var(--bg-soft)",
                  border: "1px solid var(--rule)",
                }}
              >
                <p
                  className="font-serif text-sm leading-relaxed min-w-0"
                  style={{ color: "var(--fg)" }}
                >
                  {t("profile.prereq_gap_text", {
                    topic: g.topic_id,
                    prerequisite: g.prerequisite_name,
                  })}
                </p>
                <Button
                  size="sm"
                  variant="outline"
                  className="shrink-0"
                  asChild
                >
                  <a
                    href={`https://arxiv.org/search/?query=${encodeURIComponent(g.prerequisite_name)}&searchtype=all`}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {t("profile.find_papers")}
                  </a>
                </Button>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {hasDecays ? (
        <div>
          <h3
            className="font-mono text-[10px] uppercase tracking-[0.16em] mb-2"
            style={{ color: "var(--fg-muted)" }}
          >
            {t("profile.decay_gaps")}
          </h3>
          <div className="space-y-2">
            {gaps.decay.map((g, i) => (
              <div
                key={i}
                className="flex items-center justify-between gap-3 px-3 py-2 rounded-card"
                style={{
                  background: "var(--bg-soft)",
                  border: "1px solid var(--rule)",
                }}
              >
                <p
                  className="font-serif text-sm leading-relaxed min-w-0"
                  style={{ color: "var(--fg)" }}
                >
                  {t("profile.decay_gap_text", {
                    topic: g.topic_id,
                    days: g.days_since_last,
                  })}
                </p>
                <Button size="sm" variant="outline" className="shrink-0">
                  {t("profile.review")}
                </Button>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
