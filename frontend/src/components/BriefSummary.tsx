// ft-039 primary 卡 A+B: 方法概要（markdown）+ 创新点 / 局限（双列）。
// 数据全在 PaperListItem（list DTO 已包含），无需懒加载。
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useTranslation } from "react-i18next";

interface Props {
  /** brief.method_summary_zh — 已是 markdown 格式（生成器输出）。 */
  methodSummary?: string;
  /** brief.key_innovation — list 视图前 2 条；这里展示传入的全部。 */
  keyInnovation?: string[];
  /** brief.limitations — 同上。 */
  limitations?: string[];
  /** ft-040: brief 内容语言（'zh' | 'en' | ''）。
   *  与 UI 语言不一致时显示小 badge 提示用户内容是另一语言。 */
  briefLang?: string;
}

export function BriefSummary({
  methodSummary,
  keyInnovation,
  limitations,
  briefLang,
}: Props) {
  const { t, i18n } = useTranslation();
  const uiLang = (i18n.language || "").startsWith("zh") ? "zh" : "en";
  const showLangBadge = !!briefLang && briefLang !== uiLang;
  const hasMethod = !!(methodSummary || "").trim();
  const hasInnov = (keyInnovation || []).length > 0;
  const hasLimit = (limitations || []).length > 0;
  if (!hasMethod && !hasInnov && !hasLimit) return null;

  return (
    <div className="mt-4 pt-4 border-t border-[var(--rule)] space-y-3">
      {hasMethod ? (
        <section>
          <h4 className="font-mono text-[10px] uppercase tracking-[0.18em]
                         text-[var(--fg-muted)] mb-1.5 flex items-center gap-2">
            <span>{t("papers.brief.method_summary")}</span>
            {showLangBadge ? (
              <span className="px-1.5 py-px rounded-chip border border-[var(--rule)]
                               text-[9px] tracking-[0.14em] font-mono
                               text-[var(--fg-soft)] normal-case">
                {briefLang === "en"
                  ? t("papers.brief.lang_en_badge")
                  : t("papers.brief.lang_zh_badge")}
              </span>
            ) : null}
          </h4>
          <div className="font-serif text-[0.92rem] leading-[1.65] text-[var(--fg)]
                          [&>p]:mb-2 [&>ul]:list-disc [&>ul]:pl-5 [&>ol]:list-decimal
                          [&>ol]:pl-5 [&>strong]:font-semibold">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {methodSummary!}
            </ReactMarkdown>
          </div>
        </section>
      ) : null}

      {(hasInnov || hasLimit) ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-5 gap-y-3">
          {hasInnov ? (
            <section>
              <h4 className="font-mono text-[10px] uppercase tracking-[0.18em]
                             text-[var(--accent)] mb-1.5">
                ▸ {t("papers.brief.key_innovation")}
              </h4>
              <ul className="font-serif text-[0.88rem] leading-[1.6]
                             text-[var(--fg)] space-y-1 list-none">
                {keyInnovation!.map((k, i) => (
                  <li key={i} className="pl-3 border-l-2 border-[var(--accent)]/40">
                    {k}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
          {hasLimit ? (
            <section>
              <h4 className="font-mono text-[10px] uppercase tracking-[0.18em]
                             text-[var(--counter-fg,#a05050)] mb-1.5">
                ▸ {t("papers.brief.limitations")}
              </h4>
              <ul className="font-serif text-[0.88rem] leading-[1.6]
                             text-[var(--fg)] space-y-1 list-none">
                {limitations!.map((k, i) => (
                  <li key={i} className="pl-3 border-l-2 border-[var(--counter-fg,#a05050)]/40">
                    {k}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
