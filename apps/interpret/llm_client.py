"""ft-020 + ft-034 P0-1: chat_json 中央实现已迁至 ``apps.llm.client``.

本模块保留 thin wrapper，原因：
1. 现有测试 ``apps/interpret/tests_llm_client.py`` 通过
   ``patch.object(llm_client, "chat", ...)`` 拦截，必须保留本模块级 ``chat`` 名字。
2. ``DefaultInterpreter`` 仍 ``from apps.interpret.llm_client import chat_json``，
   保留同名 wrapper 不破坏调用方。

新代码请直接 ``from apps.llm.client import chat_json``。
"""
from __future__ import annotations

import json
import logging
from typing import Any

# 重新导入到本模块命名空间：测试 patch.object(llm_client, "chat") 才能生效
from apps.llm.client import chat, extract_json
from apps.llm.errors import LLMError

log = logging.getLogger(__name__)


def chat_json(
    *,
    system: str,
    user: str,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 2048,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """单轮 chat，强制 JSON object 返回。失败 raise ``LLMError``.

    本地保留实现（不直接 re-export apps.llm.client.chat_json），因为
    测试通过 patch 本模块的 ``chat`` 注入假 LLM；re-export 会让 patch 失效。
    """
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    res = chat(
        messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
        timeout=timeout,
    )
    raw = res.content or ""
    try:
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            raise LLMError(f"expected JSON object, got {type(obj).__name__}")
        return obj
    except json.JSONDecodeError:
        # 容错：response_format 偶发被忽略，退回 extract_json
        try:
            obj = extract_json(raw)
        except Exception as exc:  # noqa: BLE001
            log.warning("[interpret] LLM JSON parse failed: %r raw=%r", exc, raw[:200])
            raise LLMError(f"invalid JSON from LLM: {raw[:200]!r}") from exc
        if not isinstance(obj, dict):
            raise LLMError(f"expected JSON object, got {type(obj).__name__}")
        return obj


__all__ = ["chat", "chat_json", "extract_json", "LLMError"]
