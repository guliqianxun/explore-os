"""apps.llm.prompts 单测 —— registry 完整性 + 字符串非空."""
from __future__ import annotations

import pytest

from apps.llm.prompts import get_prompt, list_prompts


EXPECTED_NAMES = {
    "skim",
    "deep",
    "narrative",
    "rewriter",
    "figure_picker",
}


def test_registry_contains_all_prompts():
    assert set(list_prompts()) == EXPECTED_NAMES


@pytest.mark.parametrize("name", sorted(EXPECTED_NAMES))
def test_each_prompt_is_non_empty_string(name: str):
    s = get_prompt(name)
    assert isinstance(s, str)
    assert len(s.strip()) >= 20  # 每个 prompt 都至少几十字


def test_get_prompt_unknown_raises_keyerror():
    with pytest.raises(KeyError):
        get_prompt("nonexistent")


def test_skim_prompt_mentions_keywords_field():
    """smoke：skim 必须要求输出 keywords。"""
    assert "keywords" in get_prompt("skim")


def test_deep_prompt_mentions_method_summary():
    """smoke：deep 必须要求 method_summary。"""
    assert "method_summary" in get_prompt("deep")


def test_legacy_constants_match_registry():
    """旧文件 import 时仍能取到同样的字符串。"""
    from apps.llm.prompts.skim import SYSTEM as SKIM
    from apps.llm.prompts.deep import SYSTEM as DEEP

    assert get_prompt("skim") == SKIM
    assert get_prompt("deep") == DEEP
