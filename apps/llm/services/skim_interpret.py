"""apps.llm.services.skim_interpret — skim 解读 service（ft-034 P0-3）.

搬自 ``interpret/interpretation.py:skim_interpret``。canonical 实现落在中台层；
legacy ``interpret/interpretation.py:skim_interpret`` 函数体保持不变，仍由老
email 链 (``subscriptions/run_subscription.py``) + ``delivery/`` 直接 import
（PHASE-2-DECISION P2-1：legacy 模块保留 1 周观察期）。

外部消费方依赖 ``SkimOut`` dataclass 字段，**不可改字段**。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from apps.llm.client import chat, extract_json
from apps.llm.errors import LLMError
from apps.llm.models import get_profile
from apps.llm.prompts.skim import SYSTEM as SKIM_SYSTEM_SUFFIX
from sources.base import Item
from subscriptions.loader import PerspectiveSpec

log = logging.getLogger(__name__)


# ---------------- perspective presets ----------------
# 与 interpret/interpretation.py:PRESETS 1:1（保持视角注入语义不变）。

PRESETS: dict[str, str] = {
    "researcher": (
        "读者是该领域的研究者，关注方法的创新点、理论贡献、与已有工作的差异、实验设计合理性、"
        "以及遗留的开放问题。用精准的学术语言。"
    ),
    "engineer": (
        "读者是工程师，关注是否能落地、实现成本、依赖、是否有开源代码、推理/训练资源需求。"
        "用务实的工程语言。"
    ),
    "pm": (
        "读者是产品经理，关注这项技术能做成什么产品形态、能服务什么用户场景、"
        "距离产品化还有多远、竞争格局。用业务语言。"
    ),
    "student": (
        "读者是刚入门该领域的学生，关注这篇适不适合入门阅读、需要什么前置知识、"
        "有无官方代码可复现。用通俗清晰的语言。"
    ),
}


def perspective_prefix(p: PerspectiveSpec) -> str:
    """把 perspective 转成 system prompt 前缀段。空则返回空串。"""
    if p.custom.strip():
        return f"【视角】{p.custom.strip()}\n\n"
    if p.preset and p.preset in PRESETS:
        return f"【视角】{PRESETS[p.preset]}\n\n"
    return ""


# ---------------- SkimOut ----------------


@dataclass(slots=True)
class SkimOut:
    """skim 输出。**字段不可改**（外部消费方依赖：brief_generator / email pipeline）。"""

    abstract_zh: str = ""
    keywords: list[str] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)


# ---------------- skim_interpret ----------------


def skim_interpret(item: Item, perspective: PerspectiveSpec) -> SkimOut | None:
    """对单 item 跑 skim：英文 abstract → 中文 + 3–5 个 keywords。

    title 或 abstract 空 → 返回 None（caller 据此判断 skip）。
    LLM 失败 → log.warning + 返回 None。
    """
    if not item.title or not (item.abstract or "").strip():
        return None

    profile = get_profile("skim")
    system = perspective_prefix(perspective) + SKIM_SYSTEM_SUFFIX
    user = f"title: {item.title}\n\nabstract: {item.abstract}"
    try:
        result = chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            model=profile.model,
            temperature=profile.temperature,
            max_tokens=profile.max_tokens,
        )
        parsed = extract_json(result.content)
        return SkimOut(
            abstract_zh=str(parsed.get("abstract_zh") or "").strip(),
            keywords=[str(k) for k in parsed.get("keywords") or []][:5],
            usage=result.usage,
        )
    except (LLMError, Exception) as exc:  # noqa: BLE001
        log.warning("skim failed for %s: %r", item.dedup_key, exc)
        return None


__all__ = ["SkimOut", "skim_interpret", "perspective_prefix", "PRESETS"]
