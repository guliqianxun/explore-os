"""ft-006: LLM TL;DR 解读（MVP depth=tldr）。"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from sources.base import Item

from .llm import LLMError, chat, extract_json

log = logging.getLogger(__name__)


TLDR_SYSTEM = """你是论文速读助手。读输入的 title + abstract，用中文输出 JSON：
{
  "summary": "1-2 句话的核心要点，不超过 60 字",
  "keywords": ["关键词1", "关键词2", "关键词3"]
}
只输出 JSON，不要解释。summary 用陈述句，避免"本文""作者"这种模板词。"""


@dataclass(slots=True)
class TLDR:
    summary: str
    keywords: list[str]
    usage: dict[str, int]


def summarize(item: Item) -> TLDR | None:
    """为单条 Item 产出 TL;DR；失败返回 None（调用方降级展示原 abstract 前 N 字）。"""
    if not item.title:
        return None
    prompt = f"title: {item.title}\n\nabstract: {item.abstract or '(no abstract)'}"
    try:
        result = chat(
            messages=[
                {"role": "system", "content": TLDR_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=200,
        )
        parsed = extract_json(result.content)
        return TLDR(
            summary=str(parsed.get("summary") or "").strip(),
            keywords=[str(k) for k in parsed.get("keywords") or []][:5],
            usage=result.usage,
        )
    except (LLMError, Exception) as exc:  # noqa: BLE001
        log.warning("tldr failed for %s: %r", item.dedup_key, exc)
        return None
