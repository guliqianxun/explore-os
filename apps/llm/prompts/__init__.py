"""Prompt registry（ft-034 P0-2 / P1-2 死码清理后剩 5 个 prompt）.

5 处 SYSTEM 字符串集中地。每个 prompt 模块只导出 ``SYSTEM: str`` 常量。

ft-034 P1-2: 删除 tldr / figure_classifier 两个 prompt（顶级 interpret 同名模块
已无业务引用，整体删除）。

使用：

    from apps.llm.prompts import get_prompt

    sys = get_prompt("skim")

或直接 import：

    from apps.llm.prompts.skim import SYSTEM
"""
from __future__ import annotations

from apps.llm.prompts import (
    deep,
    figure_picker,
    narrative,
    rewriter,
    skim,
)

_REGISTRY: dict[str, str] = {
    "skim": skim.SYSTEM,
    "deep": deep.SYSTEM,
    "narrative": narrative.SYSTEM,
    "rewriter": rewriter.SYSTEM,
    "figure_picker": figure_picker.SYSTEM,
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
