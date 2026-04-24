"""ft-007: HTML email renderer (按分组)."""
from __future__ import annotations

import html
from dataclasses import dataclass

from interpret.tldr import TLDR
from sources.base import Item


@dataclass(slots=True)
class RenderedItem:
    item: Item
    tldr: TLDR | None
    dup_sources: list[str]  # e.g. ["arxiv", "hf_papers"]


def _esc(s: str) -> str:
    return html.escape(s or "", quote=True)


def render_html(
    subject: str,
    groups: dict[str, list[RenderedItem]],
    run_summary: str = "",
) -> tuple[str, str]:
    """返回 (html_body, plain_body)。"""
    parts_html: list[str] = [
        "<html><body style=\"font-family:-apple-system,Segoe UI,Roboto,sans-serif;"
        "max-width:720px;margin:20px auto;color:#1f2937;line-height:1.55\">",
        f"<h1 style=\"font-size:20px;border-bottom:2px solid #2563eb;padding-bottom:8px\">"
        f"{_esc(subject)}</h1>",
    ]
    if run_summary:
        parts_html.append(
            f"<p style=\"color:#6b7280;font-size:13px\">{_esc(run_summary)}</p>"
        )

    parts_text: list[str] = [subject, "=" * len(subject), ""]
    if run_summary:
        parts_text.extend([run_summary, ""])

    group_order = ["papers", "code", "models"]
    ordered = [g for g in group_order if g in groups] + [
        g for g in groups if g not in group_order
    ]

    for group in ordered:
        items = groups[group]
        if not items:
            continue
        parts_html.append(
            f"<h2 style=\"font-size:16px;margin-top:24px;color:#111827\">"
            f"[{_esc(group.upper())}] &nbsp;<span style=\"color:#6b7280;font-weight:400\">"
            f"{len(items)} items</span></h2>"
        )
        parts_text.append(f"## {group.upper()} ({len(items)} items)")
        parts_text.append("")

        for ri in items:
            it, tldr = ri.item, ri.tldr
            date_str = it.published_at.date().isoformat() if it.published_at else ""
            src_tag = "+".join(ri.dup_sources) if len(ri.dup_sources) > 1 else it.source_key
            authors = ", ".join(it.authors[:3])
            if len(it.authors) > 3:
                authors += f" +{len(it.authors) - 3}"

            summary = (tldr.summary if tldr else (it.abstract or "")[:200] + "…")
            kw = (
                " ".join(f"#{_esc(k)}" for k in (tldr.keywords if tldr else []))
                if tldr else ""
            )

            parts_html.append(
                f"<div style=\"margin:14px 0;padding:12px;border:1px solid #e5e7eb;"
                f"border-radius:6px\">"
                f"<div style=\"font-size:12px;color:#6b7280\">"
                f"{_esc(date_str)} · <span style=\"color:#2563eb\">{_esc(src_tag)}</span></div>"
                f"<div style=\"font-size:15px;font-weight:600;margin:4px 0\">"
                f"<a href=\"{_esc(it.url)}\" style=\"color:#111827;text-decoration:none\">"
                f"{_esc(it.title)}</a></div>"
                f"<div style=\"font-size:12px;color:#6b7280\">{_esc(authors)}</div>"
                f"<div style=\"font-size:13px;margin-top:6px\">{_esc(summary)}</div>"
                f"{'<div style=\"font-size:12px;color:#2563eb;margin-top:4px\">' + kw + '</div>' if kw else ''}"
                f"</div>"
            )
            parts_text.extend([
                f"- [{src_tag}] {date_str}  {it.title}",
                f"  {authors}",
                f"  {it.url}",
                f"  {summary}",
                "",
            ])

    parts_html.append(
        "<p style=\"color:#9ca3af;font-size:11px;margin-top:32px\">"
        "explore-os MVP · arXiv + HuggingFace Daily Papers</p></body></html>"
    )
    return "\n".join(parts_html), "\n".join(parts_text)
