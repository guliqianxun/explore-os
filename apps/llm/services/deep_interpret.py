"""apps.llm.services.deep_interpret — 精读 service（ft-034 P0-3）.

搬自 ``interpret/deep_interpret.py:deep_interpret_rich``。canonical 实现落在中
台层；legacy ``interpret/deep_interpret.py`` 函数体保持不变（老 email 链仍走它）。

外部消费方依赖 ``DeepOut`` dataclass 字段，**不可改字段**。

review-A H13 / DEEP_CAPTION_LIMIT：``captions[:8]`` 改用
``apps.llm.budgets.DEEP_CAPTION_LIMIT`` 常量（值 = 8，行为不变）。
"""
from __future__ import annotations

import logging

from apps.llm.budgets import DEEP_CAPTION_LIMIT
from apps.llm.client import chat, extract_json
from apps.llm.errors import LLMError
from apps.llm.models import get_profile
from apps.llm.prompts.deep import SYSTEM as DEEP_SYSTEM_SUFFIX
from apps.llm.services.skim_interpret import perspective_prefix
from sources.base import Item
from subscriptions.loader import PerspectiveSpec

log = logging.getLogger(__name__)


# ---------------- DeepOut（迁自 interpret/interpretation.py 的 dataclass） ----------------
# 注意：DeepOut 与 DEEP_PLACEHOLDER 在 legacy ``interpret/interpretation.py`` 仍
# 保留（老 email 链 import）；这里复制一份避免 services 反向 import legacy。

from dataclasses import dataclass, field


DEEP_PLACEHOLDER = (
    "（深度解读 + 框架图将在 iter-003 填充：方法摘要 / 关键创新 / 局限 / 个人视角）"
)


@dataclass(slots=True)
class DeepOut:
    """精读输出。**字段不可改**（外部消费方依赖：brief_generator / email pipeline）。"""

    abstract: str          # 原文 abstract 透传
    placeholder: str       # iter-002 占位
    method_summary: str = ""
    key_innovation: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    for_you: str = ""
    # 架构图（略读和精读都用）
    figure_path: str = ""
    figure_caption: str = ""
    # 效果图（略读和精读都用）
    qualitative_path: str = ""
    qualitative_caption: str = ""
    # 表（仅精读）
    table_path: str = ""
    table_caption: str = ""


# ---------------- deep_interpret_rich ----------------


def deep_interpret_rich(
    item: Item,
    chunks,  # apps.extract.section_extractor.PaperChunks | None
    captions,  # list[apps.extract.caption_extractor.Caption] | None
    memory_papers,  # list[subscriptions.memory.PaperRecord] | None
    perspective: PerspectiveSpec,
) -> DeepOut:
    """对单论文跑精读：method/exp/conclusion 文本 + caption 列表 + 引用上下文 + memory.

    无 body 也无 caption → 直接返回占位 ``DeepOut``（避免无意义 LLM call）。
    LLM 失败 → log.warning + 返回占位 ``DeepOut``。
    """
    out = DeepOut(abstract=item.abstract or "", placeholder=DEEP_PLACEHOLDER)
    body = _compose_body(chunks) if chunks else ""
    cap_block = _compose_captions(captions or [])
    mem_block = _compose_memory(memory_papers or [])

    if not body and not cap_block:
        log.info(
            "deep_interpret_rich: no body & no captions for %s, placeholder",
            item.dedup_key,
        )
        return out

    profile = get_profile("deep")
    system = perspective_prefix(perspective) + DEEP_SYSTEM_SUFFIX
    user = (
        f"title: {item.title}\n\n"
        f"abstract: {item.abstract}\n"
    )
    if body:
        user += f"\n=== 方法 / 实验 / 结论文本 ===\n{body}\n"
    if cap_block:
        user += f"\n=== 论文配图 captions + 引用上下文 ===\n{cap_block}\n"
    if mem_block:
        user += f"\n=== 近期推送过的相关论文（供联想/对比） ===\n{mem_block}\n"
    user += "\n请产出 JSON 四段。"

    try:
        res = chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            model=profile.model,
            temperature=profile.temperature,
            max_tokens=profile.max_tokens,
            timeout=60.0,
        )
        parsed = extract_json(res.content)
    except (LLMError, Exception) as exc:  # noqa: BLE001
        log.warning("deep_interpret_rich failed for %s: %r", item.dedup_key, exc)
        return out

    out.method_summary = str(parsed.get("method_summary") or "").strip()
    out.key_innovation = [str(s).strip() for s in parsed.get("key_innovation") or []][:4]
    out.limitations = [str(s).strip() for s in parsed.get("limitations") or []][:3]
    out.for_you = str(parsed.get("for_you") or "").strip()
    return out


# ---------------- helpers（与 interpret/deep_interpret.py 对齐） ----------------


def _compose_body(chunks) -> str:
    parts = []
    for b in ("method", "experiments", "conclusion"):
        txt = chunks.by_bucket(b)
        if txt:
            parts.append(f"## {b}\n{txt}")
    return "\n\n".join(parts)


def _compose_captions(captions) -> str:
    if not captions:
        return ""
    lines = []
    for c in captions[:DEEP_CAPTION_LIMIT]:
        lines.append(f"[{c.label}] {c.text}")
        for ref in c.references[:2]:
            lines.append(f"    引用上下文：{ref}")
    return "\n".join(lines)


def _compose_memory(papers) -> str:
    if not papers:
        return ""
    # 只取最近 8 条避免 token 膨胀
    recent = papers[-8:]
    lines = []
    for p in recent:
        kw = "/".join(p.keywords[:3]) if p.keywords else ""
        zh = (p.abstract_zh or p.one_liner)[:120]
        lines.append(f"- {p.target_date}  {p.title}  ({kw})  ::  {zh}")
    return "\n".join(lines)


__all__ = ["DeepOut", "DEEP_PLACEHOLDER", "deep_interpret_rich"]
