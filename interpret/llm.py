"""DEPRECATED: 内容已迁至 ``apps.llm``（ft-034 P0-1）.

本文件保留 1 周观察期再删（PHASE-2-DECISION P2-1 决策后）。新代码请直接
``from apps.llm.client import ...`` / ``from apps.llm.errors import LLMError``。
"""
from __future__ import annotations

from apps.llm.client import (
    LLMResult,
    build_image_content,
    chat,
    chat_json,
    extract_json,
)
from apps.llm.errors import LLMError

__all__ = [
    "LLMResult",
    "LLMError",
    "chat",
    "chat_json",
    "extract_json",
    "build_image_content",
]
