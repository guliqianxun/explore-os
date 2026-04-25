"""ft-013: 选架构图 — 规则优先，文本 LLM 兜底（不喂图像）.

输入：一组 Caption（已含 caption 文本 + 正文引用上下文）。
输出：被选中的 Caption（或 None）。

规则：
1. caption 含关键词 framework / overview / architecture / pipeline / approach / our model
   → 命中即返回（首图优先）
2. 否则取 figure 1（论文 Figure 1 通常是 teaser/总览）
3. 如果 captions 空或全 table → None
4. 仅当用户显式开启 LLM 兜底（caption_judge_via_llm=True）才走 LLM
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from django.conf import settings

from .caption_extractor import Caption
from .llm import LLMError, chat, extract_json

log = logging.getLogger(__name__)


ARCH_KEYWORDS = re.compile(
    r"\b(framework|overview|architecture|pipeline|approach|our\s+(model|method)|"
    r"our\s+(framework|architecture)|illustration\s+of)\b",
    re.IGNORECASE,
)


def pick_architecture(
    captions: list[Caption],
    llm_fallback: bool = False,
) -> Caption | None:
    figures = [c for c in captions if c.kind == "figure"]
    if not figures:
        return None

    # 规则 1：关键词命中
    keyword_hits = [c for c in figures if ARCH_KEYWORDS.search(c.text)]
    if keyword_hits:
        keyword_hits.sort(key=lambda c: (c.number, c.page))
        log.info("figure_picker: rule-keyword pick %s (%s)",
                 keyword_hits[0].label, keyword_hits[0].text[:60])
        return keyword_hits[0]

    # 规则 2：figure 1 兜底
    fig_by_num = {c.number: c for c in figures}
    if 1 in fig_by_num:
        log.info("figure_picker: rule-fig1 pick (%s)", fig_by_num[1].text[:60])
        return fig_by_num[1]

    # 规则 3：取 number 最小的 figure
    figures.sort(key=lambda c: c.number)
    fallback = figures[0] if figures else None

    if not llm_fallback or fallback is None:
        return fallback

    # 规则 4：文本 LLM 兜底
    return _llm_pick(figures) or fallback


# ---------------- LLM 兜底（仅 caption 文本，不喂图） ----------------

LLM_PICK_SYSTEM = """你是论文配图选择助手。给你一组论文的 figure caption（编号 + 文本），
请选出最像"方法/架构总览图"的那张。仅输出 JSON：
{"number": <int>, "reason": "<10字内>"}

判断依据：caption 描述了模型结构、pipeline、framework、approach overview 的优先；
描述定性结果、消融、对比的不优先。"""


def _llm_pick(figures: list[Caption]) -> Caption | None:
    user = "\n".join(f"#{c.number}  {c.text}" for c in figures[:15])
    try:
        res = chat(
            messages=[
                {"role": "system", "content": LLM_PICK_SYSTEM},
                {"role": "user", "content": user},
            ],
            model=settings.LLM_MODEL_TEXT,
            temperature=0.1,
            max_tokens=80,
            timeout=30.0,
        )
        parsed = extract_json(res.content)
        n = int(parsed.get("number"))
        for c in figures:
            if c.number == n:
                log.info("figure_picker: llm pick #%d (%s)", n, parsed.get("reason"))
                return c
    except (LLMError, Exception) as exc:  # noqa: BLE001
        log.warning("figure_picker llm fallback failed: %r", exc)
    return None
