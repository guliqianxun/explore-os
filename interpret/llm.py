"""Shared LLM client: OpenAI-compatible HTTP calls (DashScope / OpenAI / etc.)."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx
from django.conf import settings
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

log = logging.getLogger(__name__)


@dataclass(slots=True)
class LLMResult:
    content: str
    usage: dict[str, int]  # prompt_tokens / completion_tokens / total_tokens
    model: str


class LLMError(RuntimeError):
    pass


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
    max_tokens: int = 512,
    response_format: dict | None = None,
    timeout: float = 30.0,
) -> LLMResult:
    """单轮 chat completion。model 默认用 LLM_MODEL_TEXT。"""
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


def build_image_content(text: str, image_path: str | None = None,
                         image_b64: str | None = None,
                         mime: str = "image/png") -> list[dict[str, Any]]:
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
        blocks.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{image_b64}"},
        })
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
