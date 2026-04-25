"""Tests for ft-012 deep_interpret_rich."""
from __future__ import annotations

import pytest

from interpret import deep_interpret as di
from interpret.deep_interpret import deep_interpret_rich
from interpret.figure_extractor import Figure
from interpret.interpretation import DEEP_PLACEHOLDER
from interpret.llm import LLMResult
from interpret.pdf_chunker import PaperChunks, Section
from sources.base import Item
from subscriptions.loader import PerspectiveSpec


def _item() -> Item:
    return Item(
        external_id="2401.12345", title="AnyRecon", abstract="We propose...",
        url="u", source_key="hf_papers", group="papers",
        dedup_key="arxiv:2401.12345",
    )


def _chunks() -> PaperChunks:
    return PaperChunks(
        arxiv_id="2401.12345",
        sections=[
            Section("method", "2 Method", "We build a diffusion model..."),
            Section("experiments", "4 Experiments", "On ImageNet we achieve..."),
            Section("conclusion", "5 Conclusion", "We show..."),
        ],
    )


def _mock_chat(monkeypatch, content: str):
    calls = {"messages": None}

    def fake(messages, **kwargs):
        calls["messages"] = messages
        return LLMResult(content=content, usage={"total_tokens": 100}, model="t")

    monkeypatch.setattr(di, "chat", fake)
    return calls


GOOD_JSON = '''{
  "method_summary": "通过构建全局场景记忆与几何感知条件，扩展扩散模型处理任意稀疏视图。",
  "key_innovation": ["持久全局场景记忆", "几何感知条件策略", "4 步蒸馏 + 稀疏注意力"],
  "limitations": ["对大型室外场景泛化有限", "推理时图像缓存开销"],
  "for_you": "作为研究者关注的核心是几何驱动的视图检索机制。"
}'''


def test_rich_with_chunks_and_text(monkeypatch):
    _mock_chat(monkeypatch, GOOD_JSON)
    out = deep_interpret_rich(_item(), _chunks(), figure=None,
                              perspective=PerspectiveSpec(preset="researcher"))
    assert "全局场景记忆" in out.method_summary
    assert len(out.key_innovation) == 3
    assert len(out.limitations) == 2
    assert "几何驱动" in out.for_you
    # abstract 仍然透传
    assert out.abstract.startswith("We propose")
    # 无 figure 不设 figure_path
    assert out.figure_path == ""


def test_rich_no_chunks_no_figure_returns_placeholder(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("should not call LLM when no data")
    monkeypatch.setattr(di, "chat", boom)
    out = deep_interpret_rich(_item(), chunks=None, figure=None,
                              perspective=PerspectiveSpec())
    assert out.placeholder == DEEP_PLACEHOLDER
    assert out.method_summary == ""


def test_rich_llm_failure_degrades(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("api down")
    monkeypatch.setattr(di, "chat", boom)
    out = deep_interpret_rich(_item(), _chunks(), figure=None,
                              perspective=PerspectiveSpec())
    assert out.method_summary == ""
    assert out.placeholder == DEEP_PLACEHOLDER


def test_rich_perspective_injected(monkeypatch):
    calls = _mock_chat(monkeypatch, GOOD_JSON)
    deep_interpret_rich(_item(), _chunks(), figure=None,
                        perspective=PerspectiveSpec(preset="engineer"))
    system = calls["messages"][0]["content"]
    assert "工程" in system


def test_rich_figure_fields_written_when_figure_exists(monkeypatch, tmp_path):
    _mock_chat(monkeypatch, GOOD_JSON)
    # figure 路径存在
    from interpret import figure_extractor as fe
    monkeypatch.setattr(fe, "figures_root", lambda: tmp_path)
    monkeypatch.setattr(di, "figures_root", lambda: tmp_path)
    base = tmp_path / "2401.12345"
    base.mkdir()
    (base / "p01_i00.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)

    fig = Figure(arxiv_id="2401.12345", page=1, index=0, path="p01_i00.png",
                 caption="Figure 1: Framework", width=800, height=600,
                 kind="architecture", confidence=0.9)
    out = deep_interpret_rich(_item(), _chunks(), figure=fig,
                              perspective=PerspectiveSpec())
    assert out.figure_path == "p01_i00.png"
    assert out.figure_caption == "Figure 1: Framework"
