"""ft-020: llm_client.chat_json 单测 —— 全 mock interpret.llm.chat."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from interpret.llm import LLMError, LLMResult

from apps.interpret import llm_client


def _result(content: str) -> LLMResult:
    return LLMResult(content=content, usage={}, model="test")


def test_chat_json_parses_strict_json():
    with patch.object(llm_client, "chat", return_value=_result('{"claims": [{"a": 1}]}')) as m:
        out = llm_client.chat_json(system="s", user="u")
    assert out == {"claims": [{"a": 1}]}
    # response_format 必须是 json_object
    kw = m.call_args.kwargs
    assert kw["response_format"] == {"type": "json_object"}


def test_chat_json_falls_back_to_extract_json_on_fenced():
    fenced = "```json\n{\"x\": 2}\n```"
    with patch.object(llm_client, "chat", return_value=_result(fenced)):
        out = llm_client.chat_json(system="s", user="u")
    assert out == {"x": 2}


def test_chat_json_raises_on_unparseable():
    with patch.object(llm_client, "chat", return_value=_result("not json at all")):
        with pytest.raises(LLMError):
            llm_client.chat_json(system="s", user="u")


def test_chat_json_raises_on_non_object():
    """LLM 返回 JSON array / string → reject。"""
    with patch.object(llm_client, "chat", return_value=_result("[1, 2, 3]")):
        with pytest.raises(LLMError):
            llm_client.chat_json(system="s", user="u")
