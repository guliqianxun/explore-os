"""Tests for ft-013 memory."""
from __future__ import annotations

import pytest

from subscriptions import memory as mem
from subscriptions.memory import (
    PaperRecord,
    RunRecord,
    append_digest,
    append_papers,
    append_run,
    known_dedup_keys,
    list_runs,
    load_papers,
    recent_digest_lines,
)


@pytest.fixture
def patch_root(monkeypatch, tmp_path):
    monkeypatch.setattr(mem, "memory_root", lambda: tmp_path)
    yield tmp_path


def test_runs_roundtrip(patch_root):
    rec = RunRecord(
        target_date="2026-04-24", started_at="2026-04-25T00:00:00Z",
        item_count=10, deep_count=2, skim_count=8,
        sources=["arxiv", "hf_papers"], notes="",
    )
    append_run("video-gen", rec)
    runs = list_runs("video-gen")
    assert len(runs) == 1
    assert runs[0].target_date == "2026-04-24"
    assert runs[0].deep_count == 2


def test_papers_append_and_known_keys(patch_root):
    p1 = PaperRecord(
        dedup_key="arxiv:1", title="A", authors=["x"], url="u",
        source_key="arxiv", pushed_at="t", target_date="2026-04-24",
        score=0.5, tier="skim",
    )
    p2 = PaperRecord(
        dedup_key="arxiv:2", title="B", authors=["y"], url="u",
        source_key="hf_papers", pushed_at="t", target_date="2026-04-24",
        score=0.8, tier="deep", one_liner="主题", keywords=["k1", "k2"],
    )
    append_papers("sub", [p1, p2])
    assert known_dedup_keys("sub") == {"arxiv:1", "arxiv:2"}
    loaded = load_papers("sub")
    assert {p.dedup_key for p in loaded} == {"arxiv:1", "arxiv:2"}
    p2_loaded = next(p for p in loaded if p.dedup_key == "arxiv:2")
    assert p2_loaded.keywords == ["k1", "k2"]


def test_papers_append_idempotent_dedup_keys_known(patch_root):
    """两次写入；known 集合应包含两次的并集."""
    p1 = PaperRecord(dedup_key="arxiv:1", title="A", authors=[], url="u",
                      source_key="arxiv", pushed_at="t", target_date="2026-04-24",
                      score=0, tier="skim")
    append_papers("sub", [p1])
    p2 = PaperRecord(dedup_key="arxiv:2", title="B", authors=[], url="u",
                      source_key="arxiv", pushed_at="t", target_date="2026-04-25",
                      score=0, tier="skim")
    append_papers("sub", [p2])
    assert known_dedup_keys("sub") == {"arxiv:1", "arxiv:2"}


def test_digest_appends_and_reads(patch_root):
    append_digest("sub", "2026-04-24", "今日主题",
                   ["bullet 1", "bullet 2"], "建议读 #1")
    text = recent_digest_lines("sub")
    assert "## 2026-04-24" in text
    assert "今日主题" in text
    assert "bullet 1" in text
    assert "建议读" in text


def test_unsafe_subscription_name_sanitized(patch_root, tmp_path):
    # 非安全字符应被替换为下划线
    name = "weird/../name with spaces!"
    rec = RunRecord(target_date="2026-04-24", started_at="t",
                     item_count=0, deep_count=0, skim_count=0)
    append_run(name, rec)
    # 找到生成的目录（不是字面 weird/../）
    children = [p.name for p in tmp_path.iterdir()]
    assert any("weird" in c and "/" not in c for c in children)


def test_empty_memory_returns_empty_lists(patch_root):
    assert list_runs("nope") == []
    assert load_papers("nope") == []
    assert known_dedup_keys("nope") == set()
    assert recent_digest_lines("nope") == ""
