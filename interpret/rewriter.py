"""ft-002: Interest Rewriter.

把订阅 interests + exclude 翻译成各 source 的 query。一次 LLM 调用产出结构化
JSON；失败时降级为"关键词原样透传"。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from sources.base import SourceQuery

from .llm import LLMError, chat, extract_json

log = logging.getLogger(__name__)


REWRITE_SYSTEM = """你是学术搜索查询改写助手。把用户的研究兴趣翻译成两个目标的查询：
1) arXiv 布尔查询串（支持 all:"phrase" / OR / AND）
2) HuggingFace Daily Papers 的关键词列表（简单子串匹配）

只输出一个 JSON 对象，字段：
{
  "arxiv_query": "布尔串，如 all:\\"video generation\\" OR all:\\"text-to-video\\"",
  "hf_keywords": ["关键词1", "关键词2", ...]
}

规则：
- 英文为主；如果 interests 中出现中文，译为英文。
- arxiv_query 用引号包裹多词短语。
- 忽略 exclude 关键词不要加到查询里（arXiv 源不支持 NOT，后续过滤处理）。
- hf_keywords 保留 3-8 个最核心词/短语。
- 不要输出任何解释，只要 JSON。"""


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
