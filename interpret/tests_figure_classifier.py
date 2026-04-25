"""Tests for ft-012 figure classifier."""
from __future__ import annotations

import pytest

from interpret import figure_classifier as fc
from interpret.figure_classifier import (
    VALID_KINDS,
    classify_figures,
    pick_architecture_figure,
)
from interpret.figure_extractor import Figure
from interpret.llm import LLMResult


def _fig(path="p01_i00.png", kind="", confidence=0.0):
    return Figure(
        arxiv_id="x", page=1, index=0, path=path, caption="Fig 1: architecture",
        width=800, height=600, kind=kind, confidence=confidence,
    )


@pytest.fixture
def patch_model_and_file(monkeypatch, tmp_path):
    from django.conf import settings
    settings.LLM_MODEL_VISION_CLASSIFIER = "qwen-vl-plus"
    settings.LLM_MODEL_MULTIMODAL = "qwen3.6-plus"

    # 替换 figures_root 到 tmp
    monkeypatch.setattr(fc, "figures_root", lambda: tmp_path)
    # 准备一张假图
    base = tmp_path / "x"
    base.mkdir()
    (base / "p01_i00.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    yield tmp_path


def _mock_chat(monkeypatch, content: str):
    def fake(messages, **kwargs):
        return LLMResult(content=content, usage={"total_tokens": 5}, model="test")
    monkeypatch.setattr(fc, "chat", fake)


def test_classify_ok(patch_model_and_file, monkeypatch):
    _mock_chat(monkeypatch, '{"kind":"architecture","confidence":0.92}')
    figs = classify_figures("x", [_fig()])
    assert figs[0].kind == "architecture"
    assert figs[0].confidence == pytest.approx(0.92)


def test_classify_invalid_kind_coerced(patch_model_and_file, monkeypatch):
    _mock_chat(monkeypatch, '{"kind":"unknown-bucket","confidence":0.5}')
    figs = classify_figures("x", [_fig()])
    assert figs[0].kind == "misc"


def test_classify_llm_failure_fallback(patch_model_and_file, monkeypatch):
    def boom(*a, **k): raise RuntimeError("api down")
    monkeypatch.setattr(fc, "chat", boom)
    figs = classify_figures("x", [_fig()])
    assert figs[0].kind == "misc"
    assert figs[0].confidence == 0.0


def test_classify_all_valid_kinds_accepted(patch_model_and_file, monkeypatch):
    for kind in VALID_KINDS:
        _mock_chat(monkeypatch, f'{{"kind":"{kind}","confidence":0.8}}')
        figs = classify_figures("x", [_fig()])
        assert figs[0].kind == kind


def test_pick_architecture_prefers_confidence():
    figs = [
        _fig(path="a.png", kind="architecture", confidence=0.6),
        _fig(path="b.png", kind="architecture", confidence=0.9),
        _fig(path="c.png", kind="result_figure", confidence=0.99),
    ]
    pick = pick_architecture_figure(figs)
    assert pick is not None and pick.path == "b.png"


def test_pick_architecture_none():
    figs = [_fig(kind="result_figure", confidence=0.9)]
    assert pick_architecture_figure(figs) is None


def test_classify_skips_missing_file(monkeypatch, tmp_path):
    from django.conf import settings
    settings.LLM_MODEL_VISION_CLASSIFIER = "qwen-vl-plus"
    monkeypatch.setattr(fc, "figures_root", lambda: tmp_path)
    called = {"n": 0}

    def fake(*a, **k):
        called["n"] += 1
        return LLMResult(content='{"kind":"misc","confidence":0}', usage={}, model="t")
    monkeypatch.setattr(fc, "chat", fake)

    figs = [_fig(path="nonexistent.png")]
    classify_figures("x", figs)
    # 文件缺失 → 不调用 LLM，也不改 kind
    assert called["n"] == 0
    assert figs[0].kind == ""
