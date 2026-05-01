// ft-039 primary 卡 E: Top N claims 懒加载预览（默认折叠）。
// 数据来自 detail 接口；点开 toggle 才发请求。
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { getPaperDetail } from "@/api/papers";

interface Props {
  arxivId: string;
  /** 上限，default 3。 */
  topN?: number;
  /** 总论点数（来自 list DTO，0 时不渲染整个组件）。 */
  totalClaims: number;
}

export function ClaimsPreview({ arxivId, topN = 3, totalClaims }: Props) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);

  const detailQ = useQuery({
    queryKey: ["paperDetail", arxivId],
    queryFn: () => getPaperDetail(arxivId),
    enabled: open,
    staleTime: 60_000,
  });

  if (totalClaims <= 0) return null;

  return (
    <div className="mt-3">
      <button
        type="button"
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setOpen((v) => !v);
        }}
        className="font-mono text-[10px] uppercase tracking-[0.16em]
                   text-[var(--fg-soft)] hover:text-[var(--accent)]
                   transition-colors"
      >
        {open
          ? t("papers.brief.hide_claims")
          : t("papers.brief.show_claims")}
        <span className="ml-2 text-[var(--fg-muted)]">({totalClaims})</span>
      </button>

      {open ? (
        <div className="mt-2 rounded-card border border-[var(--rule)]
                        bg-[var(--bg-soft)]/40 p-3">
          {detailQ.isLoading ? (
            <p className="text-[12px] italic text-[var(--fg-muted)]">
              {t("papers.brief.claims_loading")}
            </p>
          ) : detailQ.error ? (
            <p className="text-[12px] text-[var(--counter-fg)]">
              {t("papers.tabs.load_failed", {
                err: (detailQ.error as Error).message,
              })}
            </p>
          ) : detailQ.data ? (
            <ClaimsList
              claims={detailQ.data.claims || []}
              topN={topN}
              emptyHint={t("papers.brief.no_claims")}
            />
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function ClaimsList({
  claims,
  topN,
  emptyHint,
}: {
  claims: Array<{
    claim_id?: string;
    text?: string;
    text_zh?: string;
    text_en?: string;
    claim_type?: string;
    page?: number | null;
  }>;
  topN: number;
  emptyHint: string;
}) {
  if (!claims.length) {
    return (
      <p className="text-[12px] italic text-[var(--fg-muted)]">{emptyHint}</p>
    );
  }
  const top = claims.slice(0, topN);
  return (
    <ol className="space-y-2 list-none">
      {top.map((c, i) => {
        const text = c.text_zh || c.text || c.text_en || "(empty claim)";
        return (
          <li key={c.claim_id || i} className="flex gap-2.5">
            <span className="font-mono text-[10px] text-[var(--fg-muted)] mt-0.5
                             shrink-0">
              {String(i + 1).padStart(2, "0")}
            </span>
            <div className="flex-1 min-w-0">
              {c.claim_type ? (
                <span className="font-mono text-[9px] uppercase tracking-[0.14em]
                                 text-[var(--accent)] mr-1.5">
                  [{c.claim_type}]
                </span>
              ) : null}
              <span className="font-serif text-[0.88rem] leading-[1.55]
                               text-[var(--fg)]">
                {text}
              </span>
              {c.page ? (
                <span className="ml-1.5 font-mono text-[10px] text-[var(--fg-muted)]">
                  · p.{c.page}
                </span>
              ) : null}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
