"""Tests for ft-013 deep_interpret_rich (text-only, with captions + memory)."""
from __future__ import annotations

import pytest

from interpret import deep_interpret as di
from interpret.caption_extractor import Caption
from interpret.deep_interpret import deep_interpret_rich
from interpret.interpretation import DEEP_PLACEHOLDER
from interpret.llm import LLMResult
from interpret.pdf_chunker import PaperChunks, Section
from sources.base import Item
from subscriptions.loader import PerspectiveSpec
from subscriptions.memory import PaperRecord


def _item() -> Item:
    return Item(
        external_id="2401.12345", title="UniT", abstract="We propose...",
        url="u", source_key="hf_papers", group="papers",
        dedup_key="arxiv:2401.12345",
    )


def _chunks() -> PaperChunks:
    return PaperChunks(
        arxiv_id="2401.12345",
        sections=[
            Section("method", "2 Method", "We build a tokenizer..."),
            Section("experiments", "4 Experiments", "On benchmarks we achieve..."),
        ],
    )


def _captions() -> list[Caption]:
    return [
        Caption(arxiv_id="x", kind="figure", number=1,
                text="Figure 1: Overview of UniT framework.",
                page=2, bbox_caption=(0, 0, 1, 1), bbox_image=(0, 0, 1, 1),
                references=["as shown in Fig. 1, ..."]),
        Caption(arxiv_id="x", kind="table", number=1,
                text="Table 1: Quantitative results.",
                page=4, bbox_caption=(0, 0, 1, 1), bbox_image=(0, 0, 1, 1)),
    ]


def _memory() -> list[PaperRecord]:
    return [
        PaperRecord(
            dedup_key="arxiv:2400.99999", title="Earlier related",
            authors=["A"], url="u", source_key="arxiv",
            pushed_at="2026-04-24T00:00:00", target_date="2026-04-24",
            score=0.5, tier="deep", one_liner="related work",
            keywords=["related"],
        ),
    ]


def _mock_chat(monkeypatch, content: str):
    calls = {"messages": None}

    def fake(messages, **kwargs):
        calls["messages"] = messages
        return LLMResult(content=content, usage={"total_tokens": 100}, model="t")

    monkeypatch.setattr(di, "chat", fake)
    return calls


GOOD_JSON = '''{
  "method_summary": "通过统一离散 token 实现跨具身迁移，结构见 [Fig. 1]",
  "key_innovation": ["视觉锚定", "三叉互重建", "离散表征接口"],
  "limitations": ["无力觉建模", "高频运动失真"],
  "for_you": "建议关注 [Fig. 1] 的 fusion 分支。"
}'''


def test_rich_with_chunks_captions_memory(monkeypatch):
    calls = _mock_chat(monkeypatch, GOOD_JSON)
    out = deep_interpret_rich(
        item=_item(), chunks=_chunks(), captions=_captions(),
        memory_papers=_memory(),
        perspective=PerspectiveSpec(preset="researcher"),
    )
    assert "[Fig. 1]" in out.method_summary
    assert len(out.key_innovation) == 3
    assert len(out.limitations) == 2
    assert out.for_you
    assert out.abstract.startswith("We propose")
    user = calls["messages"][1]["content"]
    assert "Overview of UniT framework" in user
    assert "Earlier related" in user      # memory section


def test_rich_no_body_no_captions_returns_placeholder():
    out = deep_interpret_rich(
        item=_item(), chunks=None, captions=None, memory_papers=None,
        perspective=PerspectiveSpec(),
    )
    assert out.placeholder == DEEP_PLACEHOLDER
    assert out.method_summary == ""


def test_rich_llm_failure_degrades(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("api down")
    monkeypatch.setattr(di, "chat", boom)
    out = deep_interpret_rich(
        item=_item(), chunks=_chunks(), captions=None, memory_papers=None,
        perspective=PerspectiveSpec(),
    )
    assert out.method_summary == ""
    assert out.placeholder == DEEP_PLACEHOLDER


def test_rich_perspective_injected(monkeypatch):
    calls = _mock_chat(monkeypatch, GOOD_JSON)
    deep_interpret_rich(
        item=_item(), chunks=_chunks(), captions=None, memory_papers=None,
        perspective=PerspectiveSpec(preset="engineer"),
    )
    system = calls["messages"][0]["content"]
    assert "工程" in system


def test_rich_no_multimodal_call(monkeypatch):
    """ft-013：不再用多模态，user content 应该是 str 而非 list."""
    calls = _mock_chat(monkeypatch, GOOD_JSON)
    deep_interpret_rich(
        item=_item(), chunks=_chunks(), captions=_captions(), memory_papers=None,
        perspective=PerspectiveSpec(),
    )
    user = calls["messages"][1]["content"]
    assert isinstance(user, str)   # 多模态会是 list[dict]
