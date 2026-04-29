"""LLM 错误体系（ft-034 P0-1）.

子类目前未在 client 内强制 raise（保持向后兼容：所有失败仍 raise ``LLMError``
基类）。子类作为 P0-2 的契约扩展点存在，调用方可逐步开始 ``except LLMTimeout``
精细化处理；后续 sprint 可在 client.chat 内根据 httpx 异常区分 raise。
"""
from __future__ import annotations


class LLMError(RuntimeError):
    """LLM 调用失败基类。"""


class LLMTimeout(LLMError):
    """超时（httpx.TimeoutException 等）。"""


class LLMRateLimit(LLMError):
    """触发限流（HTTP 429 等）。"""


class LLMJsonParse(LLMError):
    """LLM 输出无法解析为预期 JSON。"""


__all__ = ["LLMError", "LLMTimeout", "LLMRateLimit", "LLMJsonParse"]
