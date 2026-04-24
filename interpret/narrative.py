"""ft-010: Daily Narrative 跨篇合成。

读完所有 skim 后，一次 LLM 调用产出 2-3 句主题速览。
视角前缀复用 ft-009 的 perspective_prefix。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sources.base import Item
from subscriptions.loader import PerspectiveSpec

from .interpretation import SkimOut, perspective_prefix
from .llm import LLMError, chat, extract_json

log = logging.getLogger(__name__)


NARRATIVE_SYSTEM_SUFFIX = """任务：你有一组今日入选的论文要点（含索引号、标题、一句话要点、综合分）。
请产出中文 JSON：
{
  "hero_sentence": "一句统领全天的话，点出主题聚类或最大新闻",
  "bullets": [
    "主题1（#索引 #索引）：1 句话概括这组论文在做的事",
    "主题2（#索引）：...",
    "主题3（#索引）：..."
  ],
  "note_for_you": "基于视角给读者的一句个人化建议，如推荐先读哪几篇"
}

规则：
- hero_sentence 不要用"今日论文""今天我们"模板词。
- bullets 数量 2-4 条，按重要性降序。
- 引用论文用 #索引 形式（索引=输入里提供的 id）。
- 只输出 JSON，不要解释。"""


@dataclass(slots=True)
class Narrative:
    hero_sentence: str
    bullets: list[str] = field(default_factory=list)
    note_for_you: str = ""
    usage: dict[str, int] = field(default_factory=dict)


def build_narrative(
    entries: list[tuple[int, Item, SkimOut | None]],
    perspective: PerspectiveSpec,
) -> Narrative | None:
    """entries: [(索引, item, skim_out_or_None), ...]  索引从 1 起."""
    if not entries:
        return None

    lines = []
    for idx, item, skim in entries:
        one_liner = skim.one_liner if skim else (item.abstract or "")[:80]
        score = item.raw.get("score", {}).get("total", 0.0) if item.raw else 0.0
        lines.append(f"#{idx}  score={score:.2f}  {item.title}\n    {one_liner}")
    user = "今日入选论文：\n\n" + "\n\n".join(lines)

    system = perspective_prefix(perspective) + NARRATIVE_SYSTEM_SUFFIX

    try:
        result = chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.4,
            max_tokens=400,
        )
        parsed = extract_json(result.content)
        return Narrative(
            hero_sentence=str(parsed.get("hero_sentence") or "").strip(),
            bullets=[str(b) for b in parsed.get("bullets") or []][:5],
            note_for_you=str(parsed.get("note_for_you") or "").strip(),
            usage=result.usage,
        )
    except (LLMError, Exception) as exc:  # noqa: BLE001
        log.warning("narrative failed: %r", exc)
        return None
