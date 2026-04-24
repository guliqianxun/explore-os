"""Tests for ft-009 interpretation."""
from __future__ import annotations

import pytest

from interpret import interpretation
from interpret.interpretation import (
    DEEP_PLACEHOLDER,
    PRESETS,
    deep_interpret,
    perspective_prefix,
    skim_interpret,
)
from interpret.llm import LLMResult
from sources.base import Item
from subscriptions.loader import PerspectiveSpec


def _item(title="Diffusion foo", abstract="We propose...") -> Item:
    return Item(
        external_id="x", title=title, abstract=abstract, url="u",
        source_key="arxiv", group="papers", dedup_key="arxiv:x",
    )


# ---------------- perspective ----------------

def test_perspective_prefix_empty():
    assert perspective_prefix(PerspectiveSpec()) == ""


def test_perspective_prefix_preset():
    p = PerspectiveSpec(preset="researcher")
    out = perspective_prefix(p)
    assert "视角" in out
    assert PRESETS["researcher"] in out


def test_perspective_prefix_custom_overrides_preset():
    p = PerspectiveSpec(preset="researcher", custom="我是博士生……")
    out = perspective_prefix(p)
    assert "我是博士生" in out
    # 不应同时包含 preset 文本
    assert PRESETS["researcher"] not in out


def test_perspective_prefix_unknown_preset():
    p = PerspectiveSpec(preset="nobody")
    assert perspective_prefix(p) == ""


# ---------------- skim ----------------

def _mock_chat(monkeypatch, content: str):
    calls = {"messages": None}

    def fake(messages, **kwargs):
        calls["messages"] = messages
        return LLMResult(content=content, usage={"total_tokens": 10}, model="test")

    monkeypatch.setattr(interpretation, "chat", fake)
    return calls


def test_skim_ok(monkeypatch):
    _mock_chat(monkeypatch, '{"one_liner": "语速控制生成", "keywords": ["diffusion","speed","video"]}')
    out = skim_interpret(_item(), PerspectiveSpec())
    assert out is not None
    assert out.one_liner == "语速控制生成"
    assert out.keywords == ["diffusion", "speed", "video"]


def test_skim_perspective_injected(monkeypatch):
    calls = _mock_chat(monkeypatch, '{"one_liner":"x","keywords":["a"]}')
    skim_interpret(_item(), PerspectiveSpec(preset="engineer"))
    system = calls["messages"][0]["content"]
    assert PRESETS["engineer"] in system


def test_skim_empty_title_returns_none():
    out = skim_interpret(_item(title=""), PerspectiveSpec())
    assert out is None


def test_skim_llm_failure_returns_none(monkeypatch):
    def boom(messages, **kwargs):
        raise RuntimeError("api down")
    monkeypatch.setattr(interpretation, "chat", boom)
    out = skim_interpret(_item(), PerspectiveSpec())
    assert out is None


def test_skim_handles_code_fence(monkeypatch):
    _mock_chat(monkeypatch, '```json\n{"one_liner":"a","keywords":["b"]}\n```')
    out = skim_interpret(_item(), PerspectiveSpec())
    assert out is not None
    assert out.one_liner == "a"


def test_skim_keywords_capped(monkeypatch):
    _mock_chat(
        monkeypatch,
        '{"one_liner":"a","keywords":["1","2","3","4","5","6","7"]}',
    )
    out = skim_interpret(_item(), PerspectiveSpec())
    assert out is not None
    assert len(out.keywords) == 5


# ---------------- deep ----------------

def test_deep_is_abstract_passthrough():
    it = _item(abstract="Exact abstract text")
    out = deep_interpret(it, PerspectiveSpec())
    assert out.abstract == "Exact abstract text"
    assert out.placeholder == DEEP_PLACEHOLDER
    # iter-002 不填这些字段
    assert out.method_summary == ""
    assert out.key_innovation == []
    assert out.for_you == ""


def test_deep_does_not_call_llm(monkeypatch):
    # 任何 chat 调用都算失败
    def boom(*a, **k):
        raise AssertionError("deep_interpret should not call chat in iter-002")

    monkeypatch.setattr(interpretation, "chat", boom)
    out = deep_interpret(_item(), PerspectiveSpec(preset="researcher"))
    assert out.abstract
