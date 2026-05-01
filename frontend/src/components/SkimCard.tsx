import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import type { PaperListItem } from "@/api/papers";
import { PaperLinks } from "@/components/PaperLinks";
import { VerdictActions } from "@/components/VerdictActions";

interface SkimCardProps {
  paper: PaperListItem;
  /** abstract_zh —— 中文翻译，走 toggle. */
  lead?: string;
  /** chip 关键词（page 已 fallback：paper.keywords ?? brief_keywords）. */
  keywords?: string[];
  /** 原文 abstract，默认显示. */
  abstractEn?: string;
}

/**
 * 速度卡片 (Brief-view 速读 region, status=new).
 *   title + keywords + 原文 abstract (line-clamp 3) + ▸ 中文翻译 toggle
 *   不挂 figure thumbnail / 3 meta cards —— 那是精读卡的形态.
 */
export function SkimCard({ paper, lead, keywords, abstractEn }: SkimCardProps) {
  const { t, i18n } = useTranslation();
  // ft-038 follow-up: 英文 UI 下隐藏「显示中文翻译」toggle —— 用户既然选了
  // 英文界面，论文原文 abstract 已经是英文，再露一个中文翻译入口属于冗余。
  const showZhToggle = i18n.language?.startsWith("zh") && !!lead;
  const [showZh, setShowZh] = useState(false);
  const displayTitle = paper.title || paper.arxiv_id;
  const detailHref = `/papers/${encodeURIComponent(paper.arxiv_id)}`;

  return (
    <article className="py-4 border-b border-[var(--rule)] last:border-b-0">
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2 mb-1">
            <div className="font-mono text-[10px] text-[var(--fg-muted)] truncate">
              {paper.arxiv_id}
            </div>
            <PaperLinks arxivId={paper.arxiv_id} compact />
          </div>
          <Link to={detailHref} className="group block">
            <h3 className="font-serif text-[1.05rem] leading-[1.3] font-medium
                           text-[var(--fg)] group-hover:text-[var(--accent)]
                           transition-colors">
              {displayTitle}
            </h3>
            {keywords && keywords.length > 0 ? (
              <div className="mt-1.5 flex flex-wrap gap-1">
                {keywords.slice(0, 6).map((k) => (
                  <span
                    key={k}
                    className="px-1.5 py-px rounded-chip
                               bg-[var(--bg-soft)] text-[10px] font-sans
                               text-[var(--fg-soft)] lowercase"
                  >
                    {k}
                  </span>
                ))}
              </div>
            ) : null}
            {abstractEn ? (
              <p className="mt-1.5 font-serif text-[0.88rem] leading-[1.55]
                            text-[var(--fg-soft)] whitespace-pre-line">
                {abstractEn.trim()}
              </p>
            ) : (
              <p className="mt-1.5 font-serif text-[0.82rem] italic text-[var(--fg-muted)]">
                {t("papers.tabs.no_abstract")}
              </p>
            )}
          </Link>
          {showZhToggle ? (
            <div className="mt-1.5">
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setShowZh((v) => !v);
                }}
                className="text-[10px] font-sans uppercase tracking-[0.14em]
                           text-[var(--fg-soft)] hover:text-[var(--accent)]
                           transition-colors"
              >
                {showZh ? t("papers.tabs.hide_zh") : t("papers.tabs.show_zh")}
              </button>
              {showZh ? (
                <p className="mt-1.5 font-serif text-[0.9rem] leading-[1.6]
                              text-[var(--fg)] whitespace-pre-line
                              border-l-2 border-[var(--rule)] pl-3">
                  {lead}
                </p>
              ) : null}
            </div>
          ) : null}
        </div>
        <div className="shrink-0">
          <VerdictActions paper={paper} />
        </div>
      </div>
    </article>
  );
}
