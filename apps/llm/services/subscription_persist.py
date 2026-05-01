"""Bridge: subscription pipeline → Paper + PaperBrief.

订阅 legacy pipeline (subscriptions/run_subscription.py) 跑完 skim/deep
后，把结果落进 ``papers_paper`` + ``papers_brief``，让产物在前端 brief
feed 里可见。Trial / single-user 场景下，作为「订阅 → feed」最短路径。

不替代 brief_generator —— 后者基于 docling Section 表，是 detail 页 UI 的
canonical 路径；本桥仅把 legacy 已算好的 SkimOut/DeepOut 直接落库。
"""
from __future__ import annotations

import logging

from apps.llm.budgets import TLDR_MAX_LEN
from apps.papers.models import Paper, PaperBrief
from sources.base import Item
from sources.pdf_fetcher import arxiv_id_of
from subscriptions.loader import PerspectiveSpec

log = logging.getLogger(__name__)


def _compose_tldr(text: str, max_len: int = TLDR_MAX_LEN) -> str:
    """与 apps.llm.services.brief_generate._compose_tldr 同语义，独立 copy 避循环."""
    if not text:
        return ""
    text = text.strip()
    if len(text) <= max_len:
        return text
    head = text[:max_len]
    min_idx = max_len // 3
    for sep in ("。", "；", ". ", ";"):
        idx = head.rfind(sep)
        if idx >= min_idx:
            return head[: idx + len(sep)].strip()
    return head + "…"


def persist_subscription_results(
    items: list[Item],
    skim_out_by_id: dict,
    deep_out_by_id: dict,
    perspective: PerspectiveSpec,
) -> tuple[int, int]:
    """把 subscription run 的产物落 Paper + PaperBrief。

    Args
    ----
    items : 订阅命中并保留的 items（已 dedup + rerank）
    skim_out_by_id : ``it.dedup_key -> SkimOut``（可能缺失：LLM 失败 / 跳过）
    deep_out_by_id : ``it.dedup_key -> DeepOut``（同上）
    perspective : sub.perspective

    Returns
    -------
    ``(paper_n, brief_n)`` —— 实际写入 / 更新的 Paper 行 + PaperBrief 行数
    """
    persp_label = (perspective.custom or perspective.preset or "")[:128]
    paper_n = 0
    brief_n = 0
    for it in items:
        arxiv_id = arxiv_id_of(it)
        if not arxiv_id:
            log.debug("[persist] skip %r: no arxiv_id", it.dedup_key)
            continue

        paper, _created = Paper.objects.update_or_create(
            arxiv_id=arxiv_id,
            defaults={
                "title": it.title or arxiv_id,
                "abstract": it.abstract or "",
            },
        )
        paper_n += 1

        skim = skim_out_by_id.get(it.dedup_key)
        deep = deep_out_by_id.get(it.dedup_key)
        if skim is None and deep is None:
            continue  # 没 LLM 输出，不建 brief 行

        abstract_zh = getattr(skim, "abstract_zh", "") or ""
        keywords = list(getattr(skim, "keywords", []) or [])
        method_summary_zh = getattr(deep, "method_summary", "") or ""
        key_innovation = list(getattr(deep, "key_innovation", []) or [])
        limitations = list(getattr(deep, "limitations", []) or [])
        for_you = getattr(deep, "for_you", "") or ""
        tldr_zh = _compose_tldr(abstract_zh) if abstract_zh else _compose_tldr(it.abstract or "")
        # ft-040: paper 语言，skim/deep 都带；缺一取另一；都缺 fallback 'zh'
        lang = getattr(skim, "lang", None) or getattr(deep, "lang", None) or "zh"

        PaperBrief.objects.update_or_create(
            paper=paper,
            defaults={
                "abstract_zh": abstract_zh,
                "keywords": keywords,
                "method_summary_zh": method_summary_zh,
                "key_innovation": key_innovation,
                "limitations": limitations,
                "for_you": for_you,
                "tldr_zh": tldr_zh,
                "perspective_used": persp_label,
                "model_used": "",  # SkimOut/DeepOut 暂未带 model 名
                "lang": lang,
            },
        )
        brief_n += 1
    return paper_n, brief_n


__all__ = ["persist_subscription_results"]
