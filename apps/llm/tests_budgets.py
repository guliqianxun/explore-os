"""apps.llm.budgets 单测 —— 4 个常量类型 + 数值合理."""
from __future__ import annotations

from apps.llm import budgets


def test_markdown_char_budget_reasonable():
    assert isinstance(budgets.MARKDOWN_CHAR_BUDGET, int)
    # 太小：长论文严重信息丢失；太大：触 LLM context 上限。
    assert 10_000 <= budgets.MARKDOWN_CHAR_BUDGET <= 200_000


def test_tldr_max_len_reasonable():
    assert isinstance(budgets.TLDR_MAX_LEN, int)
    # SYSTEM prompt 写死"不超过 60 字"，留 25-50% 余量给 LLM 偶发超长
    assert 60 <= budgets.TLDR_MAX_LEN <= 200


def test_deep_caption_limit_reasonable():
    assert isinstance(budgets.DEEP_CAPTION_LIMIT, int)
    # 论文常含 6-15 张图；< 4 信息丢太多，> 20 token 膨胀
    assert 4 <= budgets.DEEP_CAPTION_LIMIT <= 20


def test_figure_picker_top_k_reasonable():
    assert isinstance(budgets.FIGURE_PICKER_TOP_K, int)
    assert 5 <= budgets.FIGURE_PICKER_TOP_K <= 30


def test_all_constants_exported():
    """__all__ 必须覆盖 4 个常量。"""
    assert set(budgets.__all__) == {
        "MARKDOWN_CHAR_BUDGET",
        "TLDR_MAX_LEN",
        "DEEP_CAPTION_LIMIT",
        "FIGURE_PICKER_TOP_K",
    }
