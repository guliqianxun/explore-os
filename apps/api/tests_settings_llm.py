"""Settings LLM endpoints 测试。"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from django.test import Client
from django.test.utils import override_settings

from apps.llm import runtime_config as rc
from apps.llm.client import LLMResult


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("EXPLORE_OS_DATA_DIR", str(tmp_path))
    rc.clear_cache()
    yield
    rc.clear_cache()


@pytest.fixture
def client():
    return Client()


def test_get_returns_masked_key(client):
    rc.save_user_config({"llm": {"api_key": "sk-abcdef1234567890"}})
    r = client.get("/api/settings/llm/")
    assert r.status_code == 200, r.content
    data = r.json()
    assert data["api_key_masked"] == "sk...7890"
    assert data["api_key_set"] is True
    assert data["sources"]["api_key"] == "user"
    assert "config_path" in data


def test_get_short_key_fully_masked(client):
    rc.save_user_config({"llm": {"api_key": "abc"}})
    data = client.get("/api/settings/llm/").json()
    assert data["api_key_masked"] == "•••"


def test_get_falls_back_to_env(client):
    with override_settings(LLM_API_KEY="env-key", LLM_API_BASE="https://x.test/v1"):
        data = client.get("/api/settings/llm/").json()
    assert data["sources"]["api_key"] == "env"
    assert data["api_base"] == "https://x.test/v1"


def test_put_partial_update(client):
    rc.save_user_config({"llm": {"api_key": "k1", "model_text": "m1"}})
    r = client.put(
        "/api/settings/llm/",
        data={"model_text": "m2"},
        content_type="application/json",
    )
    assert r.status_code == 200
    rc.clear_cache()
    cfg = rc.llm_config()
    assert cfg.api_key == "k1"  # untouched
    assert cfg.model_text == "m2"


def test_put_empty_string_clears(client):
    rc.save_user_config({"llm": {"api_key": "k1"}})
    r = client.put(
        "/api/settings/llm/",
        data={"api_key": ""},
        content_type="application/json",
    )
    assert r.status_code == 200
    rc.clear_cache()
    with override_settings(LLM_API_KEY="env-key"):
        cfg = rc.llm_config()
    assert cfg.api_key == "env-key"  # user 清空后回落 env


def test_put_validates_api_base_protocol(client):
    r = client.put(
        "/api/settings/llm/",
        data={"api_base": "ftp://bad"},
        content_type="application/json",
    )
    assert r.status_code == 400
    assert "api_base" in r.json()["error"]


def test_put_rejects_non_numeric_budget(client):
    r = client.put(
        "/api/settings/llm/",
        data={"daily_budget_cny": "abc"},
        content_type="application/json",
    )
    assert r.status_code == 400


def test_test_endpoint_ok(client):
    rc.save_user_config({"llm": {"api_key": "sk-x", "model_text": "m"}})
    fake = LLMResult(
        content="OK",
        usage={"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6},
        model="m",
    )
    with patch("apps.api.views.settings_llm.llm_client.chat", return_value=fake):
        r = client.post("/api/settings/llm/test/")
    assert r.status_code == 200, r.content
    body = r.json()
    assert body["ok"] is True
    assert body["model"] == "m"
    assert body["content"] == "OK"
    assert body["usage"]["total_tokens"] == 6
    assert "latency_ms" in body


def test_test_endpoint_config_error(client):
    # No api_key anywhere — chat raises LLMError
    with override_settings(LLM_API_KEY=""):
        r = client.post("/api/settings/llm/test/")
    assert r.status_code == 400
    body = r.json()
    assert body["ok"] is False
    assert body["kind"] == "config"


def test_test_endpoint_network_error(client):
    rc.save_user_config({"llm": {"api_key": "sk-x", "model_text": "m"}})
    with patch(
        "apps.api.views.settings_llm.llm_client.chat",
        side_effect=ConnectionError("conn refused"),
    ):
        r = client.post("/api/settings/llm/test/")
    assert r.status_code == 502
    body = r.json()
    assert body["ok"] is False
    assert body["kind"] == "network"
    assert "ConnectionError" in body["error"]
