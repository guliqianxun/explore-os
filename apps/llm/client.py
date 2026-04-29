"""LLM HTTP client：OpenAI-compatible chat completions（ft-034 P0-1）.

搬自 ``interpret/llm.py`` + 合并 ``apps/interpret/llm_client.py:chat_json``。

设计要点：
- 默认 ``max_tokens=1024``（review-A H14：原 512 偏低，长输出被截）
- 默认 ``temperature=0.3`` 不变
- httpx + tenacity 重试逻辑保留
- 暂时所有失败均 raise ``LLMError`` 基类（与老代码兼容）；后续可按
  httpx 异常类型细分到 ``LLMTimeout`` / ``LLMRateLimit``（errors.py 已声明）
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx
from django.conf import settings
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from apps.llm.errors import LLMError

log = logging.getLogger(__name__)


@dataclass(slots=True)
class LLMResult:
    """单次 chat 返回：内容 + token 用量 + 实际 model。"""

    content: str
    usage: dict[str, int]  # prompt_tokens / completion_tokens / total_tokens
    model: str


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
)
def chat(
    messages: list[dict[str, Any]],
    *,
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 1024,
    response_format: dict | None = None,
    timeout: float = 30.0,
) -> LLMResult:
    """单轮 chat completion。model 默认走 ``settings.LLM_MODEL_TEXT``。

    review-A H14：``max_tokens`` 默认从 512 上调到 1024，避开长输出被截的退化路径。
    具体能力（skim / deep / tldr / ...）应通过 ``apps.llm.models.get_profile``
    取自己的 max_tokens，而不是依赖 default。
    """
    if not settings.LLM_API_KEY:
        raise LLMError("LLM_API_KEY is not configured")

    model = model or settings.LLM_MODEL_TEXT or settings.LLM_MODEL
    url = f"{settings.LLM_API_BASE.rstrip('/')}/chat/completions"
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format:
        payload["response_format"] = response_format

    with httpx.Client(timeout=timeout) as client:
        resp = client.post(
            url,
            headers={
                "Authorization": f"Bearer {settings.LLM_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise LLMError(f"unexpected response shape: {data!r}") from exc

    usage = data.get("usage") or {}
    return LLMResult(content=content or "", usage=usage, model=model)


def build_image_content(
    text: str,
    image_path: str | None = None,
    image_b64: str | None = None,
    mime: str = "image/png",
) -> list[dict[str, Any]]:
    """构造 OpenAI 兼容多模态 content blocks。

    image_path 和 image_b64 二选一；image_b64 优先。
    返回：[{"type":"image_url","image_url":{"url":"data:..."}}, {"type":"text","text":"..."}]
    """
    import base64

    blocks: list[dict[str, Any]] = []
    if image_b64 is None and image_path:
        from pathlib import Path as _P

        data = _P(image_path).read_bytes()
        image_b64 = base64.b64encode(data).decode("ascii")
    if image_b64:
        blocks.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{image_b64}"},
            }
        )
    blocks.append({"type": "text", "text": text})
    return blocks


def extract_json(text: str) -> Any:
    """容错地从 LLM 输出中提取 JSON。支持 ```json``` 围栏。"""
    s = text.strip()
    if s.startswith("```"):
        # strip fence
        s = s.split("```", 2)[1]
        if s.startswith("json"):
            s = s[4:]
        s = s.rsplit("```", 1)[0]
    s = s.strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        # 退化：找第一个 { 到最后一个 }
        lb, rb = s.find("{"), s.rfind("}")
        if lb >= 0 and rb > lb:
            return json.loads(s[lb : rb + 1])
        raise


def chat_json(
    *,
    system: str,
    user: str,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 2048,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """单轮 chat，强制 JSON object 返回（合并自 apps/interpret/llm_client.py）.

    返回解析后的 dict；解析失败时 raise ``LLMError``。
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
            log.warning("[apps.llm] chat_json parse failed: %r raw=%r", exc, raw[:200])
            raise LLMError(f"invalid JSON from LLM: {raw[:200]!r}") from exc
        if not isinstance(obj, dict):
            raise LLMError(f"expected JSON object, got {type(obj).__name__}")
        return obj


__all__ = [
    "LLMResult",
    "chat",
    "chat_json",
    "extract_json",
    "build_image_content",
]
