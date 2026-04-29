"""Prompt registry（ft-034 P0-2）.

7 处 SYSTEM 字符串集中地。每个 prompt 模块只导出 ``SYSTEM: str`` 常量。

使用：

    from apps.llm.prompts import get_prompt

    sys = get_prompt("skim")

或直接 import：

    from apps.llm.prompts.skim import SYSTEM
"""
from __future__ import annotations

from apps.llm.prompts import (
    deep,
    figure_classifier,
    figure_picker,
    narrative,
    rewriter,
    skim,
    tldr,
)

_REGISTRY: dict[str, str] = {
    "skim": skim.SYSTEM,
    "deep": deep.SYSTEM,
    "tldr": tldr.SYSTEM,
    "narrative": narrative.SYSTEM,
    "rewriter": rewriter.SYSTEM,
    "figure_picker": figure_picker.SYSTEM,
    "figure_classifier": figure_classifier.SYSTEM,
}


def get_prompt(name: str) -> str:
    """取一个 prompt 的 SYSTEM 字符串；name 不存在时 raise KeyError。"""
    if name not in _REGISTRY:
        raise KeyError(
            f"unknown prompt: {name!r}; known={sorted(_REGISTRY)}"
        )
    return _REGISTRY[name]


def list_prompts() -> list[str]:
    return sorted(_REGISTRY.keys())


__all__ = ["get_prompt", "list_prompts"]
