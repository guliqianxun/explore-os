"""ft-016: Email DeliveryAdapter（SMTP 投递 + HTML 渲染）.

接收 Digest，渲染 HTML + plain，通过 SMTP 投递；支持内嵌图（CID）。
"""
from __future__ import annotations

import html
import logging
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from email.mime.image import MIMEImage
from pathlib import Path

from django.conf import settings
from django.core.mail import get_connection
from django.core.mail.message import EmailMultiAlternatives

from apps.core.paths import outbox_dir

from delivery.base import (
    Digest,
    DeliveryAdapter,
    DeliveryResult,
    DeliveryTarget,
    RenderedDeep,
    RenderedSkim,
    register,
)
from interpret.interpretation import DeepOut, SkimOut
from interpret.narrative import Narrative
from sources.base import Item

log = logging.getLogger(__name__)


# ---------------- HTML/plain rendering helpers ----------------

def _esc(s: str) -> str:
    return html.escape(s or "", quote=True)


def _score_badge(item: Item) -> str:
    sc = (item.raw or {}).get("score") or {}
    total = sc.get("total")
    return f"score={total:.2f}" if total is not None else ""


def _authors(item: Item) -> str:
    out = ", ".join(item.authors[:3])
    if len(item.authors) > 3:
        out += f" +{len(item.authors) - 3}"
    return out


def _date(item: Item) -> str:
    return item.published_at.date().isoformat() if item.published_at else ""


def _src_tag(ri) -> str:
    return ("+".join(ri.dup_sources) if len(ri.dup_sources) > 1
            else ri.item.source_key)


def _img_html(path: str, caption: str) -> str:
    if not path:
        return ""
    return (
        f"<div style=\"margin:10px 0;text-align:center\">"
        f"<img src=\"cid:{_esc(path)}\" "
        f"style=\"max-width:100%;border:1px solid #e5e7eb;border-radius:4px\"/>"
        f"<div style=\"font-size:11px;color:#6b7280;margin-top:4px\">"
        f"{_esc(caption)}</div></div>"
    )


def _abstract_zh_block_html(skim: SkimOut | None) -> str:
    if not skim or not skim.abstract_zh:
        return ""
    return (
        f"<div style=\"font-size:13px;font-weight:600;color:#111827;margin-top:10px\">"
        f"摘要（中文）</div>"
        f"<div style=\"font-size:13px;color:#374151\">{_esc(skim.abstract_zh)}</div>"
    )


def _abstract_en_collapsed_html(item: Item) -> str:
    if not item.abstract:
        return ""
    return (
        f"<details style=\"margin-top:8px\">"
        f"<summary style=\"font-size:12px;color:#6b7280;cursor:pointer\">"
        f"原文摘要（English）</summary>"
        f"<div style=\"font-size:12px;color:#4b5563;margin-top:4px;"
        f"font-family:Georgia,serif;line-height:1.55\">{_esc(item.abstract)}</div>"
        f"</details>"
    )


def _keywords_html(skim: SkimOut | None) -> str:
    if not skim or not skim.keywords:
        return ""
    spans = "".join(
        f"<span style=\"color:#2563eb;font-size:11px;margin-right:6px\">"
        f"#{_esc(k)}</span>"
        for k in skim.keywords
    )
    return f"<div style=\"margin-top:8px\">{spans}</div>"


def _figure_blocks_skim_html(deep: DeepOut | None) -> str:
    if not deep:
        return ""
    return _img_html(deep.figure_path, deep.figure_caption) + \
           _img_html(deep.qualitative_path, deep.qualitative_caption)


def _render_skim_html(rs: RenderedSkim) -> str:
    it = rs.item
    src = _src_tag(rs)
    badge = _score_badge(it)
    return (
        f"<div style=\"margin:14px 0;padding:14px 16px;border:1px solid #e5e7eb;"
        f"border-radius:6px\">"
        f"<div style=\"font-size:11px;color:#6b7280\">"
        f"#{rs.index} · {_esc(_date(it))} · "
        f"<span style=\"color:#2563eb\">{_esc(src)}</span>"
        f"{' · ' + _esc(badge) if badge else ''}</div>"
        f"<div style=\"font-size:15px;font-weight:600;margin:4px 0\">"
        f"<a href=\"{_esc(it.url)}\" style=\"color:#111827;text-decoration:none\">"
        f"{_esc(it.title)}</a></div>"
        f"<div style=\"font-size:12px;color:#6b7280\">{_esc(_authors(it))}</div>"
        f"{_abstract_zh_block_html(rs.skim)}"
        f"{_figure_blocks_skim_html(rs.deep)}"
        f"{_abstract_en_collapsed_html(it)}"
        f"{_keywords_html(rs.skim)}"
        f"</div>"
    )


def _render_skim_text(rs: RenderedSkim) -> list[str]:
    it = rs.item
    out = [
        f"- #{rs.index} [{_src_tag(rs)}] {_date(it)}  {it.title}",
        f"    {_authors(it)}   {_score_badge(it)}",
        f"    {it.url}",
    ]
    if rs.skim and rs.skim.abstract_zh:
        out.append(f"    [摘要] {rs.skim.abstract_zh}")
    if rs.deep and rs.deep.figure_caption:
        out.append(f"    [框图] {rs.deep.figure_caption}")
    if rs.deep and rs.deep.qualitative_caption:
        out.append(f"    [效果图] {rs.deep.qualitative_caption}")
    if rs.skim and rs.skim.keywords:
        out.append("    " + " ".join(f"#{k}" for k in rs.skim.keywords))
    return out


def _deep_extras_html(deep: DeepOut) -> str:
    parts: list[str] = []
    if deep.method_summary:
        parts.append(
            f"<div style=\"margin-top:14px\">"
            f"<div style=\"font-size:13px;font-weight:600;color:#111827\">方法摘要</div>"
            f"<div style=\"font-size:13px;color:#374151\">"
            f"{_esc(deep.method_summary)}</div></div>"
        )
    if deep.key_innovation:
        items = "".join(f"<li>{_esc(k)}</li>" for k in deep.key_innovation)
        parts.append(
            f"<div style=\"margin-top:10px\">"
            f"<div style=\"font-size:13px;font-weight:600;color:#111827\">关键创新</div>"
            f"<ul style=\"margin:4px 0;padding-left:20px;font-size:13px\">{items}</ul></div>"
        )
    if deep.limitations:
        items = "".join(f"<li>{_esc(k)}</li>" for k in deep.limitations)
        parts.append(
            f"<div style=\"margin-top:10px\">"
            f"<div style=\"font-size:13px;font-weight:600;color:#111827\">局限</div>"
            f"<ul style=\"margin:4px 0;padding-left:20px;font-size:13px\">{items}</ul></div>"
        )
    if deep.for_you:
        parts.append(
            f"<div style=\"margin-top:12px;padding:8px 10px;background:#fffbeb;"
            f"border-left:3px solid #f59e0b;font-size:13px\">"
            f"<b>视角解读：</b>{_esc(deep.for_you)}</div>"
        )
    if deep.table_path:
        parts.append(_img_html(deep.table_path, deep.table_caption))
    if not parts:
        parts.append(
            f"<div style=\"margin-top:10px;padding:8px 10px;background:#f3f4f6;"
            f"font-size:12px;color:#6b7280;border-radius:3px\">"
            f"{_esc(deep.placeholder)}</div>"
        )
    return "".join(parts)


def _render_deep_html(rd: RenderedDeep) -> str:
    it = rd.item
    src = _src_tag(rd)
    badge = _score_badge(it)
    return (
        f"<div style=\"margin:18px 0;padding:16px;border:2px solid #fbbf24;"
        f"border-radius:8px;background:#fffbf3\">"
        f"<div style=\"font-size:12px;color:#92400e;margin-bottom:4px\">"
        f"#{rd.index} · {_esc(_date(it))} · "
        f"<span style=\"color:#b45309;font-weight:600\">{_esc(src)}</span>"
        f"{' · ' + _esc(badge) if badge else ''}</div>"
        f"<div style=\"font-size:17px;font-weight:700;margin:6px 0\">"
        f"<a href=\"{_esc(it.url)}\" style=\"color:#111827;text-decoration:none\">"
        f"{_esc(it.title)}</a></div>"
        f"<div style=\"font-size:12px;color:#6b7280\">{_esc(_authors(it))}</div>"
        f"{_abstract_zh_block_html(rd.skim)}"
        f"{_figure_blocks_skim_html(rd.deep)}"
        f"{_deep_extras_html(rd.deep)}"
        f"{_abstract_en_collapsed_html(it)}"
        f"{_keywords_html(rd.skim)}"
        f"</div>"
    )


def _render_deep_text(rd: RenderedDeep) -> list[str]:
    it = rd.item
    out = [
        f"[★ 精读 #{rd.index}] {_date(it)}  {it.title}",
        f"  来源: {_src_tag(rd)}   {_score_badge(it)}",
        f"  {_authors(it)}",
        f"  {it.url}",
    ]
    if rd.skim and rd.skim.abstract_zh:
        out.extend(["", "  [摘要]", f"  {rd.skim.abstract_zh}"])
    if rd.deep.figure_caption:
        out.extend(["", f"  [框图] {rd.deep.figure_caption}"])
    if rd.deep.qualitative_caption:
        out.extend(["", f"  [效果图] {rd.deep.qualitative_caption}"])
    if rd.deep.method_summary:
        out.extend(["", "  [方法摘要]", f"  {rd.deep.method_summary}"])
    if rd.deep.key_innovation:
        out.extend(["", "  [关键创新]"]
                   + [f"    - {k}" for k in rd.deep.key_innovation])
    if rd.deep.limitations:
        out.extend(["", "  [局限]"] + [f"    - {k}" for k in rd.deep.limitations])
    if rd.deep.for_you:
        out.extend(["", f"  [视角解读] {rd.deep.for_you}"])
    if rd.deep.table_caption:
        out.extend(["", f"  [表] {rd.deep.table_caption}"])
    if not (rd.deep.method_summary or rd.deep.key_innovation
            or rd.deep.limitations or rd.deep.for_you):
        out.extend(["", f"  {rd.deep.placeholder}"])
    if rd.skim and rd.skim.keywords:
        out.append("  " + " ".join(f"#{k}" for k in rd.skim.keywords))
    return out


def render_html(digest: Digest) -> tuple[str, str]:
    """Digest → (html_body, plain_body)."""
    parts_html: list[str] = [
        "<html><body style=\"font-family:-apple-system,Segoe UI,Roboto,sans-serif;"
        "max-width:760px;margin:20px auto;color:#1f2937;line-height:1.6\">",
        f"<h1 style=\"font-size:20px;border-bottom:2px solid #2563eb;padding-bottom:8px;"
        f"margin:0 0 10px 0\">{_esc(digest.subject)}</h1>",
    ]
    parts_text: list[str] = [
        digest.subject, "=" * min(len(digest.subject), 60), "",
    ]
    if digest.run_summary:
        parts_html.append(
            f"<p style=\"color:#6b7280;font-size:12px;margin:0 0 16px 0\">"
            f"{_esc(digest.run_summary)}</p>"
        )
        parts_text.extend([digest.run_summary, ""])

    nar = digest.narrative
    if nar and (nar.hero_sentence or nar.bullets):
        parts_html.append(
            "<div style=\"background:#eff6ff;border-left:4px solid #2563eb;"
            "padding:12px 16px;margin:16px 0;border-radius:4px\">"
            "<div style=\"font-size:14px;color:#1e40af;font-weight:600;"
            "margin-bottom:6px\">今日主题速览</div>"
        )
        if nar.hero_sentence:
            parts_html.append(
                f"<div style=\"font-size:15px;margin-bottom:8px\">"
                f"{_esc(nar.hero_sentence)}</div>"
            )
        if nar.bullets:
            parts_html.append("<ul style=\"margin:6px 0;padding-left:20px\">")
            for b in nar.bullets:
                parts_html.append(
                    f"<li style=\"font-size:13px;margin:3px 0\">{_esc(b)}</li>"
                )
            parts_html.append("</ul>")
        if nar.note_for_you:
            parts_html.append(
                f"<div style=\"font-size:12px;color:#6b7280;margin-top:8px;"
                f"font-style:italic\">{_esc(nar.note_for_you)}</div>"
            )
        parts_html.append("</div>")
        parts_text.append("[今日主题速览]")
        if nar.hero_sentence:
            parts_text.append(nar.hero_sentence)
        for b in nar.bullets:
            parts_text.append(f"  - {b}")
        if nar.note_for_you:
            parts_text.append(f"  ({nar.note_for_you})")
        parts_text.append("")

    if digest.deeps:
        parts_html.append(
            f"<h2 style=\"font-size:17px;color:#b45309;margin:24px 0 10px 0\">"
            f"★ 精读 ({len(digest.deeps)})</h2>"
        )
        parts_text.extend([f"## 精读 ({len(digest.deeps)})", ""])
        for rd in digest.deeps:
            parts_html.append(_render_deep_html(rd))
            parts_text.extend(_render_deep_text(rd))
            parts_text.append("")

    if digest.skims:
        parts_html.append(
            f"<h2 style=\"font-size:16px;color:#374151;margin:24px 0 10px 0\">"
            f"略读 ({len(digest.skims)})</h2>"
        )
        parts_text.extend([f"## 略读 ({len(digest.skims)})", ""])
        for rs in digest.skims:
            parts_html.append(_render_skim_html(rs))
            parts_text.extend(_render_skim_text(rs))
            parts_text.append("")

    parts_html.append(
        "<p style=\"color:#9ca3af;font-size:11px;margin-top:36px;text-align:center\">"
        "explore-os · arXiv + HuggingFace Daily Papers</p></body></html>"
    )
    return "\n".join(parts_html), "\n".join(parts_text)


# ---------------- SMTP send + DeliveryAdapter ----------------

def _write_outbox_eml(
    subject: str, html_body: str, plain_body: str,
    to: list[str], sender: str,
    inline_images: dict[str, Path] | None = None,
) -> Path:
    """ft-022: SMTP 未配置时落 .eml 到 DATA_DIR/outbox/。"""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(to)
    msg.set_content(plain_body or "")
    msg.add_alternative(html_body or "", subtype="html")
    if inline_images:
        for cid, img_path in inline_images.items():
            if not img_path or not img_path.exists():
                continue
            with img_path.open("rb") as f:
                data = f.read()
            subtype = img_path.suffix.lstrip(".").lower() or "png"
            if subtype == "jpg":
                subtype = "jpeg"
            msg.get_payload()[1].add_related(
                data, maintype="image", subtype=subtype, cid=f"<{cid}>",
            )
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_subject = "".join(
        c if c.isalnum() or c in "-_." else "_" for c in subject
    )[:80]
    out = outbox_dir() / f"{ts}__{safe_subject}.eml"
    out.write_bytes(bytes(msg))
    log.info("[email] SMTP not configured, wrote .eml -> %s", out)
    return out


def _send_smtp(
    subject: str, html_body: str, plain_body: str,
    to: str | list[str], from_email: str | None = None,
    inline_images: dict[str, Path] | None = None,
) -> bool:
    recipients = [to] if isinstance(to, str) else list(to)
    sender = from_email or settings.DEFAULT_FROM_EMAIL
    # ft-022: SMTP 未配置时 fallback 写 .eml，不抛错（桌面端用户可手动转发）
    if not getattr(settings, "EMAIL_HOST", ""):
        try:
            _write_outbox_eml(
                subject, html_body, plain_body, recipients, sender,
                inline_images=inline_images,
            )
            return True
        except Exception as exc:  # noqa: BLE001
            log.error("email outbox fallback failed: %r", exc)
            return False
    try:
        connection = get_connection(
            host=settings.EMAIL_HOST,
            port=settings.EMAIL_PORT,
            username=settings.EMAIL_HOST_USER,
            password=settings.EMAIL_HOST_PASSWORD,
            use_tls=settings.EMAIL_USE_TLS,
            use_ssl=settings.EMAIL_USE_SSL,
        )
        msg = EmailMultiAlternatives(
            subject=subject, body=plain_body, from_email=sender,
            to=recipients, connection=connection,
        )
        msg.attach_alternative(html_body, "text/html")
        if inline_images:
            msg.mixed_subtype = "related"
            for cid, img_path in inline_images.items():
                if not img_path or not img_path.exists():
                    continue
                with img_path.open("rb") as f:
                    data = f.read()
                subtype = img_path.suffix.lstrip(".").lower() or "png"
                if subtype == "jpg":
                    subtype = "jpeg"
                image = MIMEImage(data, _subtype=subtype)
                image.add_header("Content-ID", f"<{cid}>")
                image.add_header("Content-Disposition", "inline",
                                  filename=img_path.name)
                msg.attach(image)
        sent = msg.send(fail_silently=False)
        return bool(sent)
    except Exception as exc:  # noqa: BLE001
        log.error("email SMTP send failed: %r", exc)
        return False


@dataclass(slots=True)
class EmailAdapter:
    key: str = "email"

    def deliver(self, digest: Digest, target: DeliveryTarget) -> DeliveryResult:
        to = target.to or settings.EMAIL_TO_DEFAULT
        if not to:
            return DeliveryResult(success=False, detail="no recipient")
        html_body, plain_body = render_html(digest)
        ok = _send_smtp(
            subject=digest.subject,
            html_body=html_body,
            plain_body=plain_body,
            to=to,
            inline_images=digest.inline_images or None,
        )
        return DeliveryResult(
            success=ok,
            detail=f"email -> {to}" + ("" if ok else " FAILED"),
            metadata={"recipient": to, "imgs": len(digest.inline_images)},
        )


register(EmailAdapter())
