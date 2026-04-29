"""ft-002: Interest Rewriter.

把订阅 interests + exclude 翻译成各 source 的 query。一次 LLM 调用产出结构化
JSON；失败时降级为"关键词原样透传"。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from apps.llm.prompts.rewriter import SYSTEM as REWRITE_SYSTEM  # ft-034 P0-2
from sources.base import SourceQuery

from .llm import LLMError, chat, extract_json

log = logging.getLogger(__name__)


@dataclass(slots=True)
class RewriteInput:
    interests: list[str]
    exclude: list[str]


def rewrite(ri: RewriteInput) -> SourceQuery:
    """调一次 LLM，产出 SourceQuery。失败降级为关键词透传。"""
    if not ri.interests:
        return SourceQuery()

    user = (
        f"interests: {ri.interests}\n"
        f"exclude (informational, not in query): {ri.exclude}\n"
        "Return JSON only."
    )

    try:
        result = chat(
            messages=[
                {"role": "system", "content": REWRITE_SYSTEM},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
            max_tokens=300,
        )
        parsed = extract_json(result.content)
        return SourceQuery(
            keywords=list(ri.interests),
            arxiv_query=str(parsed.get("arxiv_query") or "").strip(),
            hf_keywords=[str(k) for k in parsed.get("hf_keywords") or []],
            raw={"rewriter": parsed, "usage": result.usage, "model": result.model},
        )
    except (LLMError, Exception) as exc:  # noqa: BLE001
        log.warning("rewriter fallback (interests=%s): %r", ri.interests, exc)
        return SourceQuery(
            keywords=list(ri.interests),
            hf_keywords=list(ri.interests),
            raw={"rewriter_fallback": str(exc)},
        )
