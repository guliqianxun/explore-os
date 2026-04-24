"""ft-009 + ft-010: 分档渲染 (deep / skim) + Daily Narrative."""
from __future__ import annotations

import html
from dataclasses import dataclass, field

from interpret.interpretation import DeepOut, SkimOut
from interpret.narrative import Narrative
from sources.base import Item


@dataclass(slots=True)
class RenderedDeep:
    item: Item
    deep: DeepOut
    dup_sources: list[str] = field(default_factory=list)
    index: int = 0   # 邮件中的编号（供 narrative 引用）


@dataclass(slots=True)
class RenderedSkim:
    item: Item
    skim: SkimOut | None
    dup_sources: list[str] = field(default_factory=list)
    index: int = 0


def _esc(s: str) -> str:
    return html.escape(s or "", quote=True)


def _score_badge(item: Item) -> str:
    sc = (item.raw or {}).get("score") or {}
    total = sc.get("total")
    if total is None:
        return ""
    return f"score={total:.2f}"


def _authors(item: Item) -> str:
    out = ", ".join(item.authors[:3])
    if len(item.authors) > 3:
        out += f" +{len(item.authors) - 3}"
    return out


def _date(item: Item) -> str:
    return item.published_at.date().isoformat() if item.published_at else ""


def _src_tag(ri: RenderedDeep | RenderedSkim) -> str:
    return (
        "+".join(ri.dup_sources)
        if len(ri.dup_sources) > 1
        else ri.item.source_key
    )


# ---------------- render ----------------

def render_html(
    subject: str,
    narrative: Narrative | None,
    deeps: list[RenderedDeep],
    skims: list[RenderedSkim],
    run_summary: str = "",
) -> tuple[str, str]:
    """返回 (html_body, plain_body)."""
    parts_html: list[str] = [
        "<html><body style=\"font-family:-apple-system,Segoe UI,Roboto,sans-serif;"
        "max-width:760px;margin:20px auto;color:#1f2937;line-height:1.6\">",
        f"<h1 style=\"font-size:20px;border-bottom:2px solid #2563eb;padding-bottom:8px;"
        f"margin:0 0 10px 0\">{_esc(subject)}</h1>",
    ]
    parts_text: list[str] = [subject, "=" * min(len(subject), 60), ""]

    if run_summary:
        parts_html.append(
            f"<p style=\"color:#6b7280;font-size:12px;margin:0 0 16px 0\">"
            f"{_esc(run_summary)}</p>"
        )
        parts_text.extend([run_summary, ""])

    # ---- Narrative ----
    if narrative and (narrative.hero_sentence or narrative.bullets):
        parts_html.append(
            "<div style=\"background:#eff6ff;border-left:4px solid #2563eb;"
            "padding:12px 16px;margin:16px 0;border-radius:4px\">"
        )
        parts_html.append(
            f"<div style=\"font-size:14px;color:#1e40af;font-weight:600;"
            f"margin-bottom:6px\">今日主题速览</div>"
        )
        if narrative.hero_sentence:
            parts_html.append(
                f"<div style=\"font-size:15px;margin-bottom:8px\">"
                f"{_esc(narrative.hero_sentence)}</div>"
            )
        if narrative.bullets:
            parts_html.append("<ul style=\"margin:6px 0;padding-left:20px\">")
            for b in narrative.bullets:
                parts_html.append(
                    f"<li style=\"font-size:13px;margin:3px 0\">{_esc(b)}</li>"
                )
            parts_html.append("</ul>")
        if narrative.note_for_you:
            parts_html.append(
                f"<div style=\"font-size:12px;color:#6b7280;margin-top:8px;"
                f"font-style:italic\">{_esc(narrative.note_for_you)}</div>"
            )
        parts_html.append("</div>")

        parts_text.append("[今日主题速览]")
        if narrative.hero_sentence:
            parts_text.append(narrative.hero_sentence)
        for b in narrative.bullets:
            parts_text.append(f"  - {b}")
        if narrative.note_for_you:
            parts_text.append(f"  ({narrative.note_for_you})")
        parts_text.append("")

    # ---- Deep ----
    if deeps:
        parts_html.append(
            f"<h2 style=\"font-size:17px;color:#b45309;margin:24px 0 10px 0\">"
            f"★ 精读 ({len(deeps)})</h2>"
        )
        parts_text.append(f"## 精读 ({len(deeps)})")
        parts_text.append("")
        for rd in deeps:
            parts_html.append(_render_deep_html(rd))
            parts_text.extend(_render_deep_text(rd))
            parts_text.append("")

    # ---- Skim ----
    if skims:
        parts_html.append(
            f"<h2 style=\"font-size:16px;color:#374151;margin:24px 0 10px 0\">"
            f"略读 ({len(skims)})</h2>"
        )
        parts_text.append(f"## 略读 ({len(skims)})")
        parts_text.append("")
        for rs in skims:
            parts_html.append(_render_skim_html(rs))
            parts_text.extend(_render_skim_text(rs))
            parts_text.append("")

    parts_html.append(
        "<p style=\"color:#9ca3af;font-size:11px;margin-top:36px;text-align:center\">"
        "explore-os · arXiv + HuggingFace Daily Papers</p></body></html>"
    )
    return "\n".join(parts_html), "\n".join(parts_text)


# ---------------- per-card renderers ----------------

def _render_deep_html(rd: RenderedDeep) -> str:
    it = rd.item
    src = _src_tag(rd)
    badge = _score_badge(it)
    authors = _authors(it)
    date = _date(it)
    fig_html = ""
    if rd.deep.figure_path:
        fig_html = (
            f"<div style=\"margin:10px 0;text-align:center\">"
            f"<img src=\"cid:{_esc(rd.deep.figure_path)}\" "
            f"style=\"max-width:100%;border:1px solid #e5e7eb;border-radius:4px\"/>"
            f"<div style=\"font-size:11px;color:#6b7280;margin-top:4px\">"
            f"{_esc(rd.deep.figure_caption)}</div></div>"
        )
    deep_html = ""
    if rd.deep.method_summary:
        deep_html += (
            f"<div style=\"margin-top:12px\">"
            f"<div style=\"font-size:13px;font-weight:600;color:#111827\">方法摘要</div>"
            f"<div style=\"font-size:13px\">{_esc(rd.deep.method_summary)}</div></div>"
        )
    if rd.deep.key_innovation:
        deep_html += (
            "<div style=\"margin-top:10px\">"
            "<div style=\"font-size:13px;font-weight:600;color:#111827\">关键创新</div>"
            "<ul style=\"margin:4px 0;padding-left:20px;font-size:13px\">"
            + "".join(f"<li>{_esc(k)}</li>" for k in rd.deep.key_innovation)
            + "</ul></div>"
        )
    if rd.deep.limitations:
        deep_html += (
            "<div style=\"margin-top:10px\">"
            "<div style=\"font-size:13px;font-weight:600;color:#111827\">局限</div>"
            "<ul style=\"margin:4px 0;padding-left:20px;font-size:13px\">"
            + "".join(f"<li>{_esc(k)}</li>" for k in rd.deep.limitations)
            + "</ul></div>"
        )
    if rd.deep.for_you:
        deep_html += (
            f"<div style=\"margin-top:10px;padding:8px 10px;background:#fffbeb;"
            f"border-left:3px solid #f59e0b;font-size:13px\">"
            f"<b>视角解读：</b>{_esc(rd.deep.for_you)}</div>"
        )
    if not deep_html:
        deep_html = (
            f"<div style=\"margin-top:10px;padding:8px 10px;background:#f3f4f6;"
            f"font-size:12px;color:#6b7280;border-radius:3px\">"
            f"{_esc(rd.deep.placeholder)}</div>"
        )

    return (
        f"<div style=\"margin:18px 0;padding:16px;border:2px solid #fbbf24;"
        f"border-radius:8px;background:#fffbf3\">"
        f"<div style=\"font-size:12px;color:#92400e;margin-bottom:4px\">"
        f"#{rd.index} · {_esc(date)} · "
        f"<span style=\"color:#b45309;font-weight:600\">{_esc(src)}</span>"
        f"{' · ' + _esc(badge) if badge else ''}</div>"
        f"<div style=\"font-size:17px;font-weight:700;margin:6px 0\">"
        f"<a href=\"{_esc(it.url)}\" style=\"color:#111827;text-decoration:none\">"
        f"{_esc(it.title)}</a></div>"
        f"<div style=\"font-size:12px;color:#6b7280\">{_esc(authors)}</div>"
        f"{fig_html}"
        f"<div style=\"margin-top:12px\">"
        f"<div style=\"font-size:13px;font-weight:600;color:#111827\">原文摘要</div>"
        f"<div style=\"font-size:13px;color:#374151\">{_esc(rd.deep.abstract)}</div>"
        f"</div>"
        f"{deep_html}"
        f"</div>"
    )


def _render_deep_text(rd: RenderedDeep) -> list[str]:
    it = rd.item
    out = [
        f"[★ 精读 #{rd.index}] {_date(it)}  {it.title}",
        f"  来源: {_src_tag(rd)}   {_score_badge(it)}",
        f"  {_authors(it)}",
        f"  {it.url}",
        "",
        "  [原文摘要]",
        f"  {rd.deep.abstract}",
    ]
    if rd.deep.method_summary:
        out.extend(["", "  [方法摘要]", f"  {rd.deep.method_summary}"])
    if rd.deep.key_innovation:
        out.extend(["", "  [关键创新]"] + [f"    - {k}" for k in rd.deep.key_innovation])
    if rd.deep.limitations:
        out.extend(["", "  [局限]"] + [f"    - {k}" for k in rd.deep.limitations])
    if rd.deep.for_you:
        out.extend(["", f"  [视角解读] {rd.deep.for_you}"])
    if not (
        rd.deep.method_summary or rd.deep.key_innovation
        or rd.deep.limitations or rd.deep.for_you
    ):
        out.extend(["", f"  {rd.deep.placeholder}"])
    return out


def _render_skim_html(rs: RenderedSkim) -> str:
    it = rs.item
    src = _src_tag(rs)
    badge = _score_badge(it)
    authors = _authors(it)
    date = _date(it)
    one_liner = rs.skim.one_liner if rs.skim else (it.abstract or "")[:160] + "…"
    kw_html = ""
    if rs.skim and rs.skim.keywords:
        kw_html = " ".join(
            f"<span style=\"color:#2563eb;font-size:11px;margin-right:4px\">"
            f"#{_esc(k)}</span>"
            for k in rs.skim.keywords
        )
    return (
        f"<div style=\"margin:10px 0;padding:10px 12px;border:1px solid #e5e7eb;"
        f"border-radius:5px\">"
        f"<div style=\"font-size:11px;color:#6b7280\">"
        f"#{rs.index} · {_esc(date)} · "
        f"<span style=\"color:#2563eb\">{_esc(src)}</span>"
        f"{' · ' + _esc(badge) if badge else ''}</div>"
        f"<div style=\"font-size:14px;font-weight:600;margin:3px 0\">"
        f"<a href=\"{_esc(it.url)}\" style=\"color:#111827;text-decoration:none\">"
        f"{_esc(it.title)}</a></div>"
        f"<div style=\"font-size:11px;color:#6b7280\">{_esc(authors)}</div>"
        f"<div style=\"font-size:13px;margin-top:4px\">{_esc(one_liner)}</div>"
        f"{('<div style=\"margin-top:4px\">' + kw_html + '</div>') if kw_html else ''}"
        f"</div>"
    )


def _render_skim_text(rs: RenderedSkim) -> list[str]:
    it = rs.item
    one_liner = rs.skim.one_liner if rs.skim else (it.abstract or "")[:160] + "…"
    kw = " ".join(f"#{k}" for k in rs.skim.keywords) if rs.skim else ""
    return [
        f"- #{rs.index} [{_src_tag(rs)}] {_date(it)}  {it.title}",
        f"    {_authors(it)}   {_score_badge(it)}",
        f"    {it.url}",
        f"    >> {one_liner}",
        f"    {kw}" if kw else "",
    ]
