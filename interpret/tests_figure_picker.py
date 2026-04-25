"""Tests for ft-013 figure_picker."""
from __future__ import annotations

from interpret import figure_picker as fp
from interpret.caption_extractor import Caption
from interpret.figure_picker import (
    pick_architecture,
    pick_qualitative,
    pick_table,
)
from interpret.llm import LLMResult


def _cap(kind: str, num: int, text: str, page: int = 1) -> Caption:
    return Caption(
        arxiv_id="x", kind=kind, number=num, text=text, page=page,
        bbox_caption=(0, 0, 1, 1), bbox_image=(0, 0, 1, 1),
    )


def test_fig1_wins_with_arch_keyword():
    """Fig 1 含 architecture/framework → 必胜，最高置信度。"""
    captions = [
        _cap("figure", 1, "Figure 1: Overview of our framework."),
        _cap("figure", 2, "Figure 2: Method pipeline."),
    ]
    assert pick_architecture(captions).number == 1


def test_fig1_wins_without_keyword():
    """Fig 1 优先：没有任何 arch 关键词时，Fig 1 仍胜出（teaser 默认是架构图）。"""
    captions = [
        _cap("figure", 1, "Figure 1: Some teaser image."),
        _cap("figure", 2, "Figure 2: Overview of our framework."),  # 含 framework
        _cap("figure", 3, "Figure 3: Qualitative results."),
    ]
    out = pick_architecture(captions)
    assert out is not None and out.number == 1   # Fig 1 优先


def test_fig1_excluded_when_qualitative_only():
    """Fig 1 caption 明显是定性结果 + 无 arch 词 → 跳过 Fig 1 走关键词。"""
    captions = [
        _cap("figure", 1, "Figure 1: Qualitative comparison with baselines."),
        _cap("figure", 2, "Figure 2: Overview of our framework."),
    ]
    assert pick_architecture(captions).number == 2


def test_no_fig1_keyword_hit_wins():
    """Fig 1 不存在 → 关键词命中胜出，最小编号优先。"""
    captions = [
        _cap("figure", 3, "Figure 3: Method pipeline overview."),
        _cap("figure", 5, "Figure 5: Loss curves."),
    ]
    assert pick_architecture(captions).number == 3


def test_no_figures_returns_none():
    captions = [_cap("table", 1, "Table 1: Results.")]
    assert pick_architecture(captions) is None


def test_no_fig1_no_keyword_min_number():
    """Fig 1 不存在 + 无关键词 → 最小编号兜底。"""
    captions = [
        _cap("figure", 3, "Figure 3: ablation"),
        _cap("figure", 5, "Figure 5: comparison"),
    ]
    out = pick_architecture(captions)
    assert out is not None and out.number == 3


def test_llm_fallback_used(monkeypatch):
    """Fig 1 不存在、关键词都不命中 → 启用 llm_fallback 应调 LLM。"""
    captions = [
        _cap("figure", 2, "Figure 2: A vague description."),
        _cap("figure", 3, "Figure 3: Another vague one."),
    ]
    called = {"n": 0}

    def fake_chat(messages, **kwargs):
        called["n"] += 1
        return LLMResult(content='{"number": 3, "reason": "总览"}',
                          usage={}, model="t")

    monkeypatch.setattr(fp, "chat", fake_chat)
    out = pick_architecture(captions, llm_fallback=True)
    assert out is not None and out.number == 3
    assert called["n"] == 1


def test_qualitative_keyword_pick():
    captions = [
        _cap("figure", 1, "Figure 1: Overview of our framework"),
        _cap("figure", 2, "Figure 2: Loss curves on benchmark"),
        _cap("figure", 3, "Figure 3: Qualitative comparison with baselines"),
    ]
    out = pick_qualitative(captions, skip=captions[0])
    assert out is not None and out.number == 3


def test_qualitative_excludes_arch_caption():
    captions = [
        _cap("figure", 5, "Figure 5: Qualitative results from our framework"),
    ]
    # 即使含 qualitative 但同时含 framework，应被排除关键词命中
    # 但兜底会取最大编号 figure（仍是 5）
    out = pick_qualitative(captions)
    assert out is not None and out.number == 5


def test_qualitative_skip_works():
    captions = [
        _cap("figure", 1, "Figure 1: A picture"),
        _cap("figure", 2, "Figure 2: Another"),
    ]
    out = pick_qualitative(captions, skip=captions[1])
    assert out is not None and out.number == 1


def test_qualitative_fallback_largest_number():
    captions = [
        _cap("figure", 1, "Figure 1: Setup"),
        _cap("figure", 2, "Figure 2: Mid"),
        _cap("figure", 5, "Figure 5: Last"),
    ]
    out = pick_qualitative(captions, skip=captions[0])
    assert out is not None and out.number == 5


def test_qualitative_no_figures():
    captions = [_cap("table", 1, "Table 1")]
    assert pick_qualitative(captions) is None


def test_pick_table_first():
    captions = [
        _cap("figure", 1, "Figure 1"),
        _cap("table", 2, "Table 2: Ablation"),
        _cap("table", 1, "Table 1: Main results"),
    ]
    out = pick_table(captions)
    assert out is not None and out.number == 1


def test_pick_table_none():
    captions = [_cap("figure", 1, "Figure 1")]
    assert pick_table(captions) is None


def test_llm_fallback_not_used_by_default(monkeypatch):
    captions = [
        _cap("figure", 2, "Figure 2: A vague description."),
        _cap("figure", 3, "Figure 3: Another vague one."),
    ]

    def boom(*a, **k):
        raise AssertionError("LLM should not be called when llm_fallback=False")

    monkeypatch.setattr(fp, "chat", boom)
    out = pick_architecture(captions)   # llm_fallback default False
    assert out is not None and out.number == 2   # min num fallback (no Fig 1)
