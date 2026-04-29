"""apps.llm.client 单测 —— mock httpx + chat_json 链路.

ft-034 P0-1 验收：
- chat() 走 httpx 发 POST，按 settings 拼 model + URL
- chat_json() 强制 JSON object 返回，配合 ``response_format``
- extract_json() 容错 markdown 围栏 + 截 {...}
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from apps.llm import client as llm_client
from apps.llm.client import LLMResult, chat, chat_json, extract_json
from apps.llm.errors import LLMError


def _fake_response(content: str = '{"ok": true}') -> MagicMock:
    """构造一个 httpx.Response 假对象。"""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13},
    }
    return resp


@override_settings(
    LLM_API_KEY="test-key",
    LLM_API_BASE="https://example.test/v1",
    LLM_MODEL_TEXT="m-text",
    LLM_MODEL="m-default",
)
def test_chat_returns_llmresult_and_uses_text_model():
    fake_post = MagicMock(return_value=_fake_response("hello"))
    with patch("httpx.Client") as cm:
        cm.return_value.__enter__.return_value.post = fake_post
        res = chat(messages=[{"role": "user", "content": "hi"}])
    assert isinstance(res, LLMResult)
    assert res.content == "hello"
    assert res.model == "m-text"
    # 校验 URL + payload
    call = fake_post.call_args
    assert call.args[0] == "https://example.test/v1/chat/completions"
    body = call.kwargs["json"]
    assert body["model"] == "m-text"
    assert body["temperature"] == 0.3
    assert body["max_tokens"] == 1024  # H14 修正：默认 1024


@override_settings(LLM_API_KEY="")
def test_chat_raises_when_api_key_missing():
    with pytest.raises(LLMError):
        chat(messages=[{"role": "user", "content": "x"}])


@override_settings(LLM_API_KEY="k", LLM_API_BASE="https://e.test/v1", LLM_MODEL_TEXT="m")
def test_chat_json_strict_json():
    with patch.object(llm_client, "chat",
                      return_value=LLMResult(content='{"a": 1}', usage={}, model="m")) as m:
        out = chat_json(system="s", user="u")
    assert out == {"a": 1}
    kw = m.call_args.kwargs
    assert kw["response_format"] == {"type": "json_object"}


@override_settings(LLM_API_KEY="k", LLM_API_BASE="https://e.test/v1", LLM_MODEL_TEXT="m")
def test_chat_json_falls_back_to_extract_on_fenced():
    fenced = "```json\n{\"x\": 2}\n```"
    with patch.object(llm_client, "chat",
                      return_value=LLMResult(content=fenced, usage={}, model="m")):
        out = chat_json(system="s", user="u")
    assert out == {"x": 2}


@override_settings(LLM_API_KEY="k", LLM_API_BASE="https://e.test/v1", LLM_MODEL_TEXT="m")
def test_chat_json_raises_on_array():
    with patch.object(llm_client, "chat",
                      return_value=LLMResult(content="[1,2,3]", usage={}, model="m")):
        with pytest.raises(LLMError):
            chat_json(system="s", user="u")


def test_extract_json_strips_fence():
    assert extract_json("```json\n{\"k\":1}\n```") == {"k": 1}


def test_extract_json_falls_back_to_brace_window():
    # 第一次 json.loads 失败 → fallback 找首 { 到末 }
    raw = "noise prefix {\"k\":2}"
    assert extract_json(raw) == {"k": 2}
