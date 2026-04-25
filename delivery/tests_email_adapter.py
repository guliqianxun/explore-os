"""Tests for ft-016 EmailAdapter (render only; SMTP send is mocked separately)."""
from __future__ import annotations

from datetime import datetime, timezone

from delivery.adapters.email import render_html
from delivery.base import Digest, RenderedDeep, RenderedSkim
from interpret.interpretation import DeepOut, SkimOut
from interpret.narrative import Narrative
from sources.base import Item


def _item(title="UniT") -> Item:
    return Item(
        external_id="x", title=title, abstract="EN abstract.", url="u",
        source_key="arxiv", group="papers",
        published_at=datetime(2026, 4, 24, tzinfo=timezone.utc),
        dedup_key="arxiv:x",
    )


def _digest_with_one_deep_one_skim() -> Digest:
    deep_item = _item("Paper A")
    deep_item.raw["score"] = {"total": 0.8, "relevance": 0.9, "hotness": 0.7}
    skim_item = _item("Paper B")
    skim_item.raw["score"] = {"total": 0.5}

    deep_out = DeepOut(
        abstract="EN abstract A.", placeholder="placeholder text",
        method_summary="方法 A", key_innovation=["创新1", "创新2"],
        limitations=["局限1"], for_you="视角解读",
        figure_path="A__arch.png", figure_caption="Fig. 1: Overview",
        qualitative_path="A__qual.png", qualitative_caption="Fig. 5: Results",
    )
    skim_out_a = SkimOut(abstract_zh="A 论文中文摘要", keywords=["k1", "k2"])
    skim_out_b = SkimOut(abstract_zh="B 论文中文摘要", keywords=["k3"])
    deep_out_b = DeepOut(
        abstract="EN abstract B.", placeholder="",
        figure_path="B__arch.png", figure_caption="Fig. 1",
    )

    return Digest(
        subject="Test Subject",
        run_summary="run summary line",
        narrative=Narrative(
            hero_sentence="今日 hero",
            bullets=["bullet 1", "bullet 2"],
            note_for_you="note",
        ),
        deeps=[RenderedDeep(item=deep_item, deep=deep_out, skim=skim_out_a,
                              dup_sources=["arxiv"], index=1)],
        skims=[RenderedSkim(item=skim_item, skim=skim_out_b, deep=deep_out_b,
                              dup_sources=["arxiv", "hf_papers"], index=2)],
    )


def test_render_html_includes_subject():
    digest = _digest_with_one_deep_one_skim()
    html, plain = render_html(digest)
    assert "Test Subject" in html
    assert "Test Subject" in plain


def test_render_html_includes_narrative():
    digest = _digest_with_one_deep_one_skim()
    html, plain = render_html(digest)
    assert "今日主题速览" in html
    assert "今日 hero" in html
    assert "bullet 1" in html
    assert "今日 hero" in plain


def test_render_html_includes_deep_extras():
    digest = _digest_with_one_deep_one_skim()
    html, _ = render_html(digest)
    assert "★ 精读" in html
    assert "Paper A" in html
    assert "方法摘要" in html
    assert "创新1" in html
    assert "局限1" in html
    assert "视角解读" in html
    assert "cid:A__arch.png" in html
    assert "cid:A__qual.png" in html


def test_render_html_includes_skim_card():
    digest = _digest_with_one_deep_one_skim()
    html, plain = render_html(digest)
    assert "略读" in html
    assert "Paper B" in html
    assert "B 论文中文摘要" in html
    assert "arxiv+hf_papers" in html   # 跨源 tag
    assert "B 论文中文摘要" in plain


def test_render_html_collapsed_english():
    digest = _digest_with_one_deep_one_skim()
    html, _ = render_html(digest)
    assert "<details" in html
    # 英文原文取自 item.abstract（fixture 都是 "EN abstract."）
    assert "EN abstract." in html
    assert "原文摘要（English）" in html


def test_render_html_no_narrative():
    digest = _digest_with_one_deep_one_skim()
    digest.narrative = None
    html, _ = render_html(digest)
    assert "今日主题速览" not in html
