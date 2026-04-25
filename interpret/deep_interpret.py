"""ft-012: 多模态深度解读 — method 文本 + 架构图 + 视角 → 结构化四段."""
from __future__ import annotations

import logging
from pathlib import Path

from django.conf import settings

from interpret.figure_extractor import Figure, figures_root
from interpret.interpretation import DEEP_PLACEHOLDER, DeepOut, perspective_prefix
from interpret.llm import LLMError, build_image_content, chat, extract_json
from interpret.pdf_chunker import PaperChunks
from sources.base import Item
from subscriptions.loader import PerspectiveSpec

log = logging.getLogger(__name__)

DEEP_SYSTEM_SUFFIX = """任务：结合方法章节文本和架构图（若提供），产出论文的结构化深度解读。
输出 JSON：
{
  "method_summary": "方法怎么做的（200-300字，精炼学术语言）",
  "key_innovation": ["关键创新点 1", "关键创新点 2", "可选 3"],
  "limitations": ["局限 1", "可选局限 2"],
  "for_you": "基于视角给读者的 1-2 句个人化解读"
}
规则：
- method_summary 要看架构图与方法文本互相印证，不要复述 abstract。
- key_innovation 必须是"相对于已有工作"的差异点，不要列 trivial 设计。
- limitations 尽量从论文自承或可推断的弱点出发。
- 只输出 JSON，不要解释。"""


def deep_interpret_rich(
    item: Item,
    chunks: PaperChunks | None,
    figure: Figure | None,
    perspective: PerspectiveSpec,
) -> DeepOut:
    """升级版 deep_interpret。调 qwen3.6-plus。失败降级到 ft-009 的占位。"""
    # abstract 仍然透传
    out = DeepOut(abstract=item.abstract or "", placeholder=DEEP_PLACEHOLDER)

    # 构造 method+exp+conclusion 文本
    body = _compose_body(chunks) if chunks else ""
    if not body and not figure:
        log.info("deep_interpret_rich: no chunks & no figure for %s, placeholder-only",
                 item.dedup_key)
        return out

    system = perspective_prefix(perspective) + DEEP_SYSTEM_SUFFIX
    user_text = (
        f"title: {item.title}\n\n"
        f"abstract: {item.abstract}\n\n"
        f"=== 方法与实验章节 ===\n{body or '(无)'}\n"
        f"\n请产出 JSON 四段。"
    )

    model = settings.LLM_MODEL_MULTIMODAL or settings.LLM_MODEL_TEXT

    try:
        if figure:
            img_path = figures_root() / item.dedup_key.replace("arxiv:", "") / figure.path
            if img_path.exists():
                user_content = build_image_content(user_text, image_path=str(img_path),
                                                    mime=_mime_of(img_path))
            else:
                user_content = user_text
        else:
            user_content = user_text

        res = chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
            model=model,
            temperature=0.3,
            max_tokens=900,
            timeout=180.0,   # 多模态 + 长上下文，给足时间
        )
        parsed = extract_json(res.content)
    except (LLMError, Exception) as exc:  # noqa: BLE001
        log.warning("deep_interpret_rich failed for %s: %r", item.dedup_key, exc)
        return out

    out.method_summary = str(parsed.get("method_summary") or "").strip()
    out.key_innovation = [str(s).strip() for s in parsed.get("key_innovation") or []][:4]
    out.limitations = [str(s).strip() for s in parsed.get("limitations") or []][:3]
    out.for_you = str(parsed.get("for_you") or "").strip()
    if figure:
        out.figure_path = figure.path
        out.figure_caption = figure.caption
    return out


def _compose_body(chunks: PaperChunks) -> str:
    parts = []
    for b in ("method", "experiments", "conclusion"):
        txt = chunks.by_bucket(b)
        if txt:
            parts.append(f"## {b}\n{txt}")
    return "\n\n".join(parts)


def _mime_of(path: Path) -> str:
    ext = path.suffix.lstrip(".").lower()
    return {
        "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
    }.get(ext, "image/png")
