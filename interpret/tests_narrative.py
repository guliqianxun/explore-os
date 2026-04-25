"""Tests for ft-010 narrative."""
from __future__ import annotations

import pytest

from interpret import narrative as nar_mod
from interpret.interpretation import SkimOut
from interpret.llm import LLMResult
from interpret.narrative import build_narrative
from sources.base import Item
from subscriptions.loader import PerspectiveSpec


def _item(title="T", abstract="A") -> Item:
    return Item(
        external_id="x", title=title, abstract=abstract, url="u",
        source_key="arxiv", group="papers", dedup_key="arxiv:x",
    )


def _mock_chat(monkeypatch, content: str):
    calls = {"messages": None}

    def fake(messages, **kwargs):
        calls["messages"] = messages
        return LLMResult(content=content, usage={"total_tokens": 50}, model="test")

    monkeypatch.setattr(nar_mod, "chat", fake)
    return calls


def test_narrative_ok(monkeypatch):
    _mock_chat(monkeypatch, (
        '{"hero_sentence":"今日主题：视频世界模型",'
        '"bullets":["#1 #3 视频世界模型","#2 推测解码"],'
        '"note_for_you":"先读 #1"}'
    ))
    entries = [
        (1, _item("World Model paper"), SkimOut(abstract_zh="世界模型", keywords=["a"])),
        (2, _item("Speculative decoding"), SkimOut(abstract_zh="加速", keywords=["b"])),
    ]
    nar = build_narrative(entries, PerspectiveSpec())
    assert nar is not None
    assert nar.hero_sentence == "今日主题：视频世界模型"
    assert len(nar.bullets) == 2
    assert nar.note_for_you == "先读 #1"


def test_narrative_empty_entries():
    assert build_narrative([], PerspectiveSpec()) is None


def test_narrative_llm_failure_returns_none(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("oops")
    monkeypatch.setattr(nar_mod, "chat", boom)
    entries = [(1, _item(), None)]
    assert build_narrative(entries, PerspectiveSpec()) is None


def test_narrative_perspective_injected(monkeypatch):
    calls = _mock_chat(monkeypatch, '{"hero_sentence":"x","bullets":[],"note_for_you":""}')
    entries = [(1, _item(), None)]
    build_narrative(entries, PerspectiveSpec(preset="engineer"))
    system = calls["messages"][0]["content"]
    # PRESET 的关键词
    assert "工程" in system


def test_narrative_uses_skim_when_available(monkeypatch):
    calls = _mock_chat(monkeypatch, '{"hero_sentence":"h","bullets":[],"note_for_you":""}')
    entries = [
        (1, _item(title="paper A", abstract="long abstract"),
         SkimOut(abstract_zh="短要点 A", keywords=["k"])),
    ]
    build_narrative(entries, PerspectiveSpec())
    user = calls["messages"][1]["content"]
    assert "短要点 A" in user
    assert "paper A" in user
