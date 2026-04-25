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

QUALITATIVE_KEYWORDS = re.compile(
    r"\b(qualitative|comparison|examples?|samples?|generated|visualization|"
    r"visualisations?|demos?|results?\s+on|generation\s+results?|"
    r"reconstruction\s+results?|synthesi[sz]ed)\b",
    re.IGNORECASE,
)


def pick_architecture(
    captions: list[Caption],
    llm_fallback: bool = False,
) -> Caption | None:
    """选架构图。"Fig 1 优先 + 关键词加持"原则：
    - Fig 1 默认胜出（CS 论文 Fig 1 ≈ teaser/architecture）
    - 例外：Fig 1 caption 是明显的定性结果（含 qualitative/comparison/examples
      等 QUALITATIVE_KEYWORDS 但无 arch 关键词）→ 跳过 Fig 1 走关键词搜
    - Fig 1 不存在或被例外排除时：取最小编号的 arch 关键词命中图
    - 都没命中：取最小编号 figure
    """
    figures = [c for c in captions if c.kind == "figure"]
    if not figures:
        return None

    fig1 = next((c for c in figures if c.number == 1), None)
    fig1_is_qualitative_only = bool(
        fig1 and QUALITATIVE_KEYWORDS.search(fig1.text)
        and not ARCH_KEYWORDS.search(fig1.text)
    )

    # 规则 1：Fig 1 默认胜出（除非明显是定性结果）
    if fig1 and not fig1_is_qualitative_only:
        kw_match = bool(ARCH_KEYWORDS.search(fig1.text))
        log.info("figure_picker: Fig 1 wins%s (%s)",
                 " [arch keyword]" if kw_match else "",
                 fig1.text[:60])
        return fig1

    # 规则 2：Fig 1 不可用 → 关键词命中（最小编号）
    keyword_hits = [c for c in figures if ARCH_KEYWORDS.search(c.text)]
    if keyword_hits:
        keyword_hits.sort(key=lambda c: (c.number, c.page))
        log.info("figure_picker: keyword pick %s (%s)",
                 keyword_hits[0].label, keyword_hits[0].text[:60])
        return keyword_hits[0]

    # 规则 3：最小编号 figure
    figures.sort(key=lambda c: c.number)
    fallback = figures[0]
    if not llm_fallback:
        log.info("figure_picker: min-number fallback %s", fallback.label)
        return fallback

    # 规则 4：文本 LLM 兜底
    return _llm_pick(figures) or fallback


# ---------------- LLM 兜底（仅 caption 文本，不喂图） ----------------

LLM_PICK_SYSTEM = """你是论文配图选择助手。给你一组论文的 figure caption（编号 + 文本），
请选出最像"方法/架构总览图"的那张。仅输出 JSON：
{"number": <int>, "reason": "<10字内>"}

判断依据：caption 描述了模型结构、pipeline、framework、approach overview 的优先；
描述定性结果、消融、对比的不优先。"""


def pick_qualitative(
    captions: list[Caption],
    skip: Caption | None = None,
) -> Caption | None:
    """挑一张定性效果图。规则：
    1. 关键词命中（qualitative/comparison/examples/...）
    2. 关键词无命中：取最后一张非 architecture figure（实验图常在中后部）
    skip：跳过这张（通常是 architecture caption，避免重复挑回）。
    """
    figures = [c for c in captions if c.kind == "figure"]
    if skip is not None:
        figures = [c for c in figures if not (c.number == skip.number)]
    if not figures:
        return None

    keyword_hits = [c for c in figures if QUALITATIVE_KEYWORDS.search(c.text)]
    # 排除明显的 framework 配图（容错）
    keyword_hits = [c for c in keyword_hits if not ARCH_KEYWORDS.search(c.text)]
    if keyword_hits:
        keyword_hits.sort(key=lambda c: (c.number, c.page))
        log.info("figure_picker.qualitative: kw pick %s", keyword_hits[0].label)
        return keyword_hits[0]

    # 兜底：取 number 最大的 figure（论文实验图常排在后部）
    figures.sort(key=lambda c: c.number, reverse=True)
    fallback = figures[0]
    log.info("figure_picker.qualitative: fallback %s", fallback.label)
    return fallback


def pick_table(captions: list[Caption]) -> Caption | None:
    """挑一张实验/比较表（按 number 升序首张）."""
    tables = [c for c in captions if c.kind == "table"]
    if not tables:
        return None
    tables.sort(key=lambda c: c.number)
    log.info("figure_picker.table: pick %s", tables[0].label)
    return tables[0]


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
