"""ft-008: 综合分 rerank + 自适应 Top-N 分档.

- relevance: embedding(interests) vs embedding(title+abstract) 余弦
- hotness: HF upvotes + 跨源加成
- total = 0.3 * relevance + 0.7 * hotness
- tier: deep (score >= 0.75, 保底 1 上限 3) / skim (其余)
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass

from sources.base import Item

from .embedding import EmbeddingError, cosine, embed

log = logging.getLogger(__name__)

# 综合分权重（用户选择偏热度）
W_RELEVANCE = 0.3
W_HOTNESS = 0.7

# 自适应 Top-N
DEEP_THRESHOLD = 0.75
DEEP_MIN = 1
DEEP_MAX = 3

# 热度信号常量
HF_UPVOTES_CAP = 100        # upvotes / CAP → 0..1
ARXIV_HOTNESS_DEFAULT = 0.1  # arXiv 无热度信号，保底
CROSS_SOURCE_BONUS = 0.1


@dataclass(slots=True)
class Scored:
    item: Item
    relevance: float
    hotness: float
    total: float
    tier: str   # "deep" | "skim"


def rank(
    items: list[Item],
    interests: list[str],
    *,
    dedup_sources: dict[str, list[str]] | None = None,
) -> list[Scored]:
    """Rerank + 分档。返回按 total 降序的 Scored 列表。

    dedup_sources: dedup_key -> [source_key,...]，用于跨源加成。若 None 则从 items 现场构造。
    """
    if not items:
        return []

    if dedup_sources is None:
        dedup_sources = defaultdict(list)
        for it in items:
            dedup_sources[it.dedup_key].append(it.source_key)

    # 1. relevance via embedding
    relevance = _relevance_scores(items, interests)

    # 2. hotness from raw payload
    hotness = [_hotness_of(it, dedup_sources) for it in items]

    # 3. total + tier
    scored: list[Scored] = []
    for it, rel, hot in zip(items, relevance, hotness):
        total = W_RELEVANCE * rel + W_HOTNESS * hot
        # 回写分数到 raw，供渲染层读取
        it.raw.setdefault("score", {})
        it.raw["score"].update({"relevance": rel, "hotness": hot, "total": total})
        scored.append(Scored(item=it, relevance=rel, hotness=hot, total=total, tier="skim"))

    scored.sort(key=lambda s: s.total, reverse=True)

    # 4. 自适应 Top-N
    deep = [s for s in scored if s.total >= DEEP_THRESHOLD]
    if not deep and scored:
        deep = [scored[0]]
    deep = deep[:DEEP_MAX]
    deep_ids = {id(s) for s in deep}
    for s in scored:
        if id(s) in deep_ids:
            s.tier = "deep"
            s.item.raw["tier"] = "deep"
        else:
            s.item.raw["tier"] = "skim"

    log.info(
        "ranker: %d items, %d deep (threshold=%s, min=%d, max=%d)",
        len(scored), len(deep), DEEP_THRESHOLD, DEEP_MIN, DEEP_MAX,
    )
    return scored


def _relevance_scores(items: list[Item], interests: list[str]) -> list[float]:
    """对每个 item 返回 relevance [0,1]。失败统一 0.5 中性。"""
    if not interests:
        return [0.5] * len(items)

    interest_text = " ; ".join(interests)
    item_texts = [f"{it.title}\n{it.abstract}" for it in items]

    try:
        emb = embed([interest_text, *item_texts])
    except (EmbeddingError, Exception) as exc:  # noqa: BLE001
        log.warning("embedding failed, fallback to 0.5: %r", exc)
        return [0.5] * len(items)

    if len(emb.vectors) != len(items) + 1:
        log.warning("embedding vector count mismatch, fallback to 0.5")
        return [0.5] * len(items)

    interest_vec = emb.vectors[0]
    scores = []
    for v in emb.vectors[1:]:
        sim = cosine(interest_vec, v)
        # cosine ∈ [-1, 1]；clamp 到 [0, 1]
        scores.append(max(0.0, min(1.0, sim)))
    return scores


def _hotness_of(item: Item, dedup_sources: dict[str, list[str]]) -> float:
    """MVP: HF upvotes + 跨源加成。"""
    base = 0.0
    if item.source_key == "hf_papers":
        upvotes = _extract_hf_upvotes(item)
        base = min(upvotes / HF_UPVOTES_CAP, 1.0)
    else:
        base = ARXIV_HOTNESS_DEFAULT

    sources_of_this = set(dedup_sources.get(item.dedup_key, []))
    if len(sources_of_this) > 1:
        base = min(1.0, base + CROSS_SOURCE_BONUS)
    return base


def _extract_hf_upvotes(item: Item) -> int:
    """HF daily_papers 条目里 upvotes 常在 paper.upvotes 或顶层。"""
    raw = item.raw or {}
    paper = raw.get("paper") or {}
    for candidate in (paper.get("upvotes"), raw.get("upvotes"), raw.get("numUpvotes")):
        if isinstance(candidate, int):
            return max(0, candidate)
        if isinstance(candidate, float):
            return max(0, int(candidate))
    return 0
