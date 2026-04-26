"""ft-020: LLM JSON 调用封装.

复用 ``interpret.llm.chat`` —— 不重新发明 HTTP / 重试。
单测：patch ``apps.interpret.llm_client.chat_json`` 替代真调。
"""
from __future__ import annotations

import json
import logging
from typing import Any

from interpret.llm import LLMError, chat, extract_json

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
    """单轮 chat，强制 JSON object 返回。

    返回解析后的 dict；解析失败时 raise LLMError。
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
