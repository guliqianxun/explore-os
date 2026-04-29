"""ft-010: Daily Narrative 跨篇合成。

读完所有 skim 后，一次 LLM 调用产出 2-3 句主题速览。
视角前缀复用 ft-009 的 perspective_prefix。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from apps.llm.prompts.narrative import SYSTEM as NARRATIVE_SYSTEM_SUFFIX  # ft-034 P0-2
from sources.base import Item
from subscriptions.loader import PerspectiveSpec

from .interpretation import SkimOut, perspective_prefix
from .llm import LLMError, chat, extract_json

log = logging.getLogger(__name__)


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
        zh = skim.abstract_zh if skim else (item.abstract or "")[:80]
        score = item.raw.get("score", {}).get("total", 0.0) if item.raw else 0.0
        lines.append(f"#{idx}  score={score:.2f}  {item.title}\n    {zh[:160]}")
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
