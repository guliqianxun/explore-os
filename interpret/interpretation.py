"""ft-009: 分档解读 (skim / deep) + 视角注入.

- skim_interpret: 调 LLM 产 one_liner + keywords（所有非精读档入选篇）
- deep_interpret: iter-002 不调 LLM，仅包装 abstract + 占位；iter-003 由 ft-012 升级为多模态深度解读

视角通过 perspective 前缀注入到 system prompt。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sources.base import Item
from subscriptions.loader import PerspectiveSpec

from .llm import LLMError, chat, extract_json

log = logging.getLogger(__name__)


# ---------------- perspective presets ----------------

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


# ---------------- skim ----------------

SKIM_SYSTEM_SUFFIX = """任务：读输入的 title + abstract，产出中文 JSON：
{
  "one_liner": "10-40字的一句话要点，结合视角措辞",
  "keywords": ["关键词1", "关键词2", "关键词3"]
}
只输出 JSON，不要解释。one_liner 用陈述句，避免"本文""作者"模板词。"""


@dataclass(slots=True)
class SkimOut:
    one_liner: str
    keywords: list[str]
    usage: dict[str, int] = field(default_factory=dict)


def skim_interpret(item: Item, perspective: PerspectiveSpec) -> SkimOut | None:
    if not item.title:
        return None
    system = perspective_prefix(perspective) + SKIM_SYSTEM_SUFFIX
    user = f"title: {item.title}\n\nabstract: {item.abstract or '(no abstract)'}"
    try:
        result = chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.3,
            max_tokens=200,
        )
        parsed = extract_json(result.content)
        return SkimOut(
            one_liner=str(parsed.get("one_liner") or "").strip(),
            keywords=[str(k) for k in parsed.get("keywords") or []][:5],
            usage=result.usage,
        )
    except (LLMError, Exception) as exc:  # noqa: BLE001
        log.warning("skim failed for %s: %r", item.dedup_key, exc)
        return None


# ---------------- deep ----------------

DEEP_PLACEHOLDER = (
    "（深度解读 + 框架图将在 iter-003 填充：方法摘要 / 关键创新 / 局限 / 个人视角）"
)


@dataclass(slots=True)
class DeepOut:
    abstract: str          # 原文 abstract 透传
    placeholder: str       # iter-002 占位
    method_summary: str = ""     # iter-003 ft-012 填
    key_innovation: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    for_you: str = ""
    figure_path: str = ""  # iter-003 ft-012 填
    figure_caption: str = ""


def deep_interpret(item: Item, perspective: PerspectiveSpec) -> DeepOut:
    """iter-002: 仅透传 abstract + 占位。iter-003 将升级。"""
    return DeepOut(
        abstract=item.abstract or "",
        placeholder=DEEP_PLACEHOLDER,
    )
