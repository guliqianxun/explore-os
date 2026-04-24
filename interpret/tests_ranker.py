"""Tests for ft-008 ranker."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from interpret import ranker
from interpret.ranker import (
    ARXIV_HOTNESS_DEFAULT,
    CROSS_SOURCE_BONUS,
    DEEP_MAX,
    Scored,
    rank,
)
from sources.base import Item


def _make_item(
    dedup_key: str,
    title: str = "T",
    abstract: str = "A",
    source_key: str = "arxiv",
    hf_upvotes: int | None = None,
) -> Item:
    raw: dict = {}
    if hf_upvotes is not None:
        raw = {"paper": {"upvotes": hf_upvotes}}
    return Item(
        external_id=dedup_key,
        title=title,
        abstract=abstract,
        url="https://example.com",
        source_key=source_key,
        group="papers",
        published_at=datetime(2026, 4, 24, tzinfo=timezone.utc),
        dedup_key=dedup_key,
        raw=raw,
    )


def _fake_embed(texts):
    # 第 0 个是 interests；之后每个 item。
    # 通过 title 中的关键字决定"相似度"——返回轴方向不同的单位向量模拟相似度。
    from interpret.embedding import EmbeddingResult

    vectors = []
    for t in texts:
        if "interests" in t or t == "video generation":
            vectors.append([1.0, 0.0, 0.0])
        elif "HIT" in t:
            vectors.append([1.0, 0.0, 0.0])  # 完全相关
        elif "HALF" in t:
            vectors.append([0.5, 0.866, 0.0])  # cos=0.5
        else:
            vectors.append([0.0, 1.0, 0.0])  # 正交，cos=0
    return EmbeddingResult(vectors=vectors, usage={})


@pytest.fixture
def patch_embed(monkeypatch):
    monkeypatch.setattr(ranker, "embed", _fake_embed)


# ---------------- relevance ----------------

def test_relevance_from_embedding(patch_embed):
    items = [
        _make_item("a", title="HIT topic"),
        _make_item("b", title="HALF topic"),
        _make_item("c", title="totally unrelated"),
    ]
    scored = rank(items, interests=["video generation"])
    by_key = {s.item.dedup_key: s for s in scored}
    assert by_key["a"].relevance == pytest.approx(1.0, abs=1e-3)
    assert by_key["b"].relevance == pytest.approx(0.5, abs=1e-3)
    assert by_key["c"].relevance == pytest.approx(0.0, abs=1e-3)


def test_empty_interests_gives_neutral(patch_embed):
    items = [_make_item("a", title="HIT topic")]
    scored = rank(items, interests=[])
    assert scored[0].relevance == pytest.approx(0.5)


def test_embedding_failure_fallback(monkeypatch):
    def boom(_texts):
        raise ranker.EmbeddingError("api down")

    monkeypatch.setattr(ranker, "embed", boom)
    items = [_make_item("a", title="HIT")]
    scored = rank(items, interests=["video generation"])
    assert scored[0].relevance == pytest.approx(0.5)


# ---------------- hotness ----------------

def test_hotness_hf_upvotes(patch_embed):
    items = [
        _make_item("a", source_key="hf_papers", hf_upvotes=0),
        _make_item("b", source_key="hf_papers", hf_upvotes=50),
        _make_item("c", source_key="hf_papers", hf_upvotes=200),
    ]
    scored = rank(items, interests=["video generation"])
    by_key = {s.item.dedup_key: s for s in scored}
    assert by_key["a"].hotness == pytest.approx(0.0)
    assert by_key["b"].hotness == pytest.approx(0.5)
    assert by_key["c"].hotness == pytest.approx(1.0)  # capped


def test_hotness_arxiv_default(patch_embed):
    items = [_make_item("a", source_key="arxiv")]
    scored = rank(items, interests=["video generation"])
    assert scored[0].hotness == pytest.approx(ARXIV_HOTNESS_DEFAULT)


def test_cross_source_bonus(patch_embed):
    items = [
        _make_item("arxiv:1", source_key="arxiv"),
        _make_item("arxiv:1", source_key="hf_papers", hf_upvotes=0),
    ]
    scored = rank(items, interests=["video generation"])
    for s in scored:
        expected_base = 0.0 if s.item.source_key == "hf_papers" else ARXIV_HOTNESS_DEFAULT
        assert s.hotness == pytest.approx(expected_base + CROSS_SOURCE_BONUS)


# ---------------- total + tier ----------------

def test_total_weights(patch_embed):
    items = [_make_item("a", title="HIT", source_key="hf_papers", hf_upvotes=100)]
    scored = rank(items, interests=["video generation"])
    assert scored[0].relevance == pytest.approx(1.0, abs=1e-3)
    assert scored[0].hotness == pytest.approx(1.0)
    assert scored[0].total == pytest.approx(0.3 * 1.0 + 0.7 * 1.0)


def test_tier_threshold_and_max(patch_embed):
    # 5 个 HIT + 高 upvotes = 都 >= 0.75 → cap 到 3
    items = [
        _make_item(f"a{i}", title="HIT", source_key="hf_papers", hf_upvotes=100)
        for i in range(5)
    ]
    scored = rank(items, interests=["video generation"])
    deep = [s for s in scored if s.tier == "deep"]
    skim = [s for s in scored if s.tier == "skim"]
    assert len(deep) == DEEP_MAX
    assert len(skim) == 2


def test_tier_min_fallback_when_all_low(patch_embed):
    # 全部低分（unrelated + arxiv 0.1 hotness） → 保底 1 篇 deep
    items = [
        _make_item(f"a{i}", title="totally unrelated", source_key="arxiv") for i in range(3)
    ]
    scored = rank(items, interests=["video generation"])
    deep = [s for s in scored if s.tier == "deep"]
    assert len(deep) == 1
    assert deep[0].total == max(s.total for s in scored)


def test_sort_descending(patch_embed):
    items = [
        _make_item("low", title="unrelated", source_key="arxiv"),
        _make_item("high", title="HIT", source_key="hf_papers", hf_upvotes=100),
        _make_item("mid", title="HALF", source_key="hf_papers", hf_upvotes=50),
    ]
    scored = rank(items, interests=["video generation"])
    totals = [s.total for s in scored]
    assert totals == sorted(totals, reverse=True)


def test_raw_score_tier_written_back(patch_embed):
    items = [_make_item("a", title="HIT", source_key="hf_papers", hf_upvotes=100)]
    scored = rank(items, interests=["video generation"])
    it = scored[0].item
    assert "score" in it.raw
    assert set(it.raw["score"].keys()) == {"relevance", "hotness", "total"}
    assert it.raw["tier"] == "deep"


def test_empty_items():
    assert rank([], interests=["x"]) == []
