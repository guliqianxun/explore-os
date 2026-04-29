"""apps.llm.services 单测（ft-034 P0-3）.

覆盖 skim_interpret / deep_interpret / brief_generate 三个 service 的 happy
path + LLMError / 边缘路径。**绝不真跑** LLM —— 一律 mock ``apps.llm.client.chat``。
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.test import override_settings

from apps.llm.client import LLMResult
from apps.llm.errors import LLMError
from apps.llm.services import brief_generate as brief_mod
from apps.llm.services import deep_interpret as deep_mod
from apps.llm.services import skim_interpret as skim_mod
from apps.llm.services.deep_interpret import DEEP_PLACEHOLDER, DeepOut, deep_interpret_rich
from apps.llm.services.skim_interpret import SkimOut, skim_interpret
from sources.base import Item
from subscriptions.loader import PerspectiveSpec


pytestmark = pytest.mark.django_db


# ---------------- fixtures ----------------


def _make_item(title="Self-Rewarding LM", abstract="We propose a method.") -> Item:
    return Item(
        external_id="2401.10000",
        title=title,
        abstract=abstract,
        url="https://arxiv.org/abs/2401.10000",
        source_key="arxiv",
        group="papers",
    )


def _researcher() -> PerspectiveSpec:
    return PerspectiveSpec(preset="researcher")


# ---------------- skim_interpret ----------------


@override_settings(
    LLM_API_KEY="k", LLM_API_BASE="https://e.test/v1",
    LLM_MODEL_TEXT="m-text", LLM_MODEL="m",
)
def test_skim_happy_returns_skimout():
    fake = LLMResult(
        content='{"abstract_zh": "中文摘要测试", "keywords": ["a", "b", "c"]}',
        usage={"prompt_tokens": 5, "completion_tokens": 10, "total_tokens": 15},
        model="m-text",
    )
    with patch.object(skim_mod, "chat", return_value=fake) as mock_chat:
        out = skim_interpret(_make_item(), _researcher())
    assert isinstance(out, SkimOut)
    assert out.abstract_zh == "中文摘要测试"
    assert out.keywords == ["a", "b", "c"]
    assert out.usage["total_tokens"] == 15
    # 校验：chat 被调用，model + max_tokens 走 profile
    kw = mock_chat.call_args.kwargs
    assert kw["model"] == "m-text"
    assert kw["max_tokens"] == 600  # ModelProfile.skim


def test_skim_returns_none_when_abstract_empty():
    out = skim_interpret(_make_item(abstract=""), _researcher())
    assert out is None


@override_settings(LLM_API_KEY="k", LLM_API_BASE="https://e.test/v1", LLM_MODEL_TEXT="m")
def test_skim_returns_none_on_llm_error():
    with patch.object(skim_mod, "chat", side_effect=LLMError("boom")):
        out = skim_interpret(_make_item(), _researcher())
    assert out is None


# ---------------- deep_interpret_rich ----------------


@override_settings(
    LLM_API_KEY="k", LLM_API_BASE="https://e.test/v1",
    LLM_MODEL_TEXT="m-text", LLM_MODEL="m",
)
def test_deep_happy_returns_full_deepout():
    """body+caption 都有 → 真调 chat → 解析 JSON → 填充字段。"""
    chunks = SimpleNamespace(by_bucket=lambda b: f"{b} body" if b == "method" else "")
    captions = [SimpleNamespace(label="Fig. 1", text="架构图", references=[])]
    fake = LLMResult(
        content=(
            '{"method_summary": "提出 X 框架",'
            ' "key_innovation": ["创新 1", "创新 2"],'
            ' "limitations": ["限制 A"],'
            ' "for_you": "对你视角的看法"}'
        ),
        usage={},
        model="m-text",
    )
    with patch.object(deep_mod, "chat", return_value=fake):
        out = deep_interpret_rich(_make_item(), chunks, captions, [], _researcher())
    assert isinstance(out, DeepOut)
    assert out.method_summary == "提出 X 框架"
    assert out.key_innovation == ["创新 1", "创新 2"]
    assert out.limitations == ["限制 A"]
    assert out.for_you == "对你视角的看法"
    # placeholder 仍带（contract）
    assert out.placeholder == DEEP_PLACEHOLDER


def test_deep_no_body_no_captions_returns_placeholder():
    """无 body 无 caption → 直接占位 DeepOut，不调 LLM。"""
    chunks = SimpleNamespace(by_bucket=lambda b: "")
    with patch.object(deep_mod, "chat") as mock_chat:
        out = deep_interpret_rich(_make_item(), chunks, [], [], _researcher())
    mock_chat.assert_not_called()
    assert out.method_summary == ""
    assert out.placeholder == DEEP_PLACEHOLDER


@override_settings(LLM_API_KEY="k", LLM_API_BASE="https://e.test/v1", LLM_MODEL_TEXT="m")
def test_deep_llm_error_returns_placeholder():
    chunks = SimpleNamespace(by_bucket=lambda b: "method body" if b == "method" else "")
    with patch.object(deep_mod, "chat", side_effect=LLMError("boom")):
        out = deep_interpret_rich(_make_item(), chunks, [], [], _researcher())
    assert out.method_summary == ""
    assert out.for_you == ""
    assert out.placeholder == DEEP_PLACEHOLDER


# ---------------- brief_generate.generate_brief_data ----------------


@pytest.fixture
def paper(db):
    from apps.papers.models import Paper
    return Paper.objects.create(
        key="brf12345",
        title="Self-Rewarding LM",
        arxiv_id="2401.99999",
        abstract="We propose a self-rewarding framework.",
    )


def test_brief_data_happy(paper, monkeypatch):
    """skim + deep 都成功 → 6 个字段都填上。"""
    fake_skim = SkimOut(
        abstract_zh="一种自奖励的 LM 框架。",
        keywords=["self-rewarding", "DPO", "alignment"],
        usage={"total_tokens": 100},
    )
    fake_deep = DeepOut(
        abstract="...",
        placeholder=DEEP_PLACEHOLDER,
        method_summary="方法 X",
        key_innovation=["创新 1"],
        limitations=["限制 1"],
        for_you="给你的视角看法",
    )
    monkeypatch.setattr(brief_mod, "skim_interpret", lambda item, persp: fake_skim)
    monkeypatch.setattr(
        brief_mod, "deep_interpret_rich",
        lambda item, chunks, captions, mem, persp: fake_deep,
    )

    data = brief_mod.generate_brief_data(paper)
    assert data["abstract_zh"] == "一种自奖励的 LM 框架。"
    assert data["keywords"] == ["self-rewarding", "DPO", "alignment"]
    assert data["method_summary_zh"] == "方法 X"
    assert data["key_innovation"] == ["创新 1"]
    assert data["limitations"] == ["限制 1"]
    assert data["for_you"] == "给你的视角看法"
    assert data["tldr_zh"]  # 非空
    assert data["perspective_used"] == "researcher"  # fallback


def test_brief_data_skim_fail_keeps_empty_zh(paper, monkeypatch):
    """skim 失败 → abstract_zh 为空，但 deep 字段仍可能填充。"""
    monkeypatch.setattr(brief_mod, "skim_interpret", lambda item, persp: None)
    fake_deep = DeepOut(
        abstract="...",
        placeholder=DEEP_PLACEHOLDER,
        method_summary="方法 Y",
        for_you="视角 Y",
    )
    monkeypatch.setattr(
        brief_mod, "deep_interpret_rich",
        lambda item, chunks, captions, mem, persp: fake_deep,
    )
    data = brief_mod.generate_brief_data(paper)
    assert data["abstract_zh"] == ""
    assert data["keywords"] == []
    assert data["method_summary_zh"] == "方法 Y"
    # tldr fallback 走 paper.abstract（英文）
    assert data["tldr_zh"]


def test_brief_data_returns_typeddict_with_all_keys(paper, monkeypatch):
    """ft-033 brief 字段稳定性合同：6 个核心字段 + perspective_used + model_used 必在."""
    monkeypatch.setattr(brief_mod, "skim_interpret", lambda item, persp: None)
    monkeypatch.setattr(
        brief_mod, "deep_interpret_rich",
        lambda item, chunks, captions, mem, persp: DeepOut(
            abstract="", placeholder=DEEP_PLACEHOLDER,
        ),
    )
    data = brief_mod.generate_brief_data(paper)
    expected_keys = {
        "abstract_zh", "keywords", "tldr_zh",
        "method_summary_zh", "key_innovation", "limitations", "for_you",
        "perspective_used", "model_used",
    }
    assert expected_keys.issubset(set(data.keys()))


def test_brief_compose_tldr_truncates_long_text():
    """_compose_tldr 私有 helper smoke：长文本走句末截断。"""
    long_zh = "第一句。" + "中文长描述。" * 20
    out = brief_mod._compose_tldr(long_zh, max_len=30)
    assert len(out) <= 31  # 含可能的句末符号
    assert out.endswith("。") or out.endswith("…")
