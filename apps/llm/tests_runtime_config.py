"""runtime_config 单测。"""
from __future__ import annotations

import json
import os

import pytest
from django.test.utils import override_settings

from apps.llm import runtime_config as rc


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path, monkeypatch):
    """每个测试一个独立 EXPLORE_OS_DATA_DIR + clear cache."""
    monkeypatch.setenv("EXPLORE_OS_DATA_DIR", str(tmp_path))
    rc.clear_cache()
    yield
    rc.clear_cache()


def test_default_when_no_file_no_env():
    with override_settings(
        LLM_API_BASE="https://api.openai.com/v1",
        LLM_API_KEY="",
        LLM_MODEL="gpt-4o-mini",
        LLM_MODEL_TEXT="",
        LLM_MODEL_MULTIMODAL="",
        LLM_MODEL_VISION_CLASSIFIER="",
        LLM_DAILY_BUDGET_CNY=30.0,
    ):
        cfg = rc.llm_config()
    assert cfg.api_base == "https://api.openai.com/v1"
    assert cfg.api_key == ""
    assert cfg.model_text == "gpt-4o-mini"
    assert cfg.daily_budget_cny == 30.0


def test_env_only():
    with override_settings(
        LLM_API_BASE="https://x.test/v1",
        LLM_API_KEY="env-key",
        LLM_MODEL_TEXT="env-text",
        LLM_DAILY_BUDGET_CNY=5.0,
    ):
        cfg = rc.llm_config()
    assert cfg.api_key == "env-key"
    assert cfg.model_text == "env-text"
    assert cfg.daily_budget_cny == 5.0


def test_user_overrides_env(tmp_path):
    rc.save_user_config({"llm": {"api_key": "user-key", "model_text": "user-text"}})
    with override_settings(LLM_API_KEY="env-key", LLM_MODEL_TEXT="env-text"):
        cfg = rc.llm_config()
    assert cfg.api_key == "user-key"
    assert cfg.model_text == "user-text"


def test_partial_user_falls_back_per_field():
    rc.save_user_config({"llm": {"api_key": "user-key"}})
    with override_settings(
        LLM_API_KEY="env-key",
        LLM_MODEL_TEXT="env-text",
        LLM_MODEL="env-fallback",
    ):
        cfg = rc.llm_config()
    assert cfg.api_key == "user-key"
    assert cfg.model_text == "env-text"  # user 没填 → 落 env


def test_save_is_idempotent_and_atomic(tmp_path):
    rc.save_user_config({"llm": {"api_key": "k1"}})
    rc.save_user_config({"llm": {"model_text": "m1"}})
    rc.clear_cache()
    data = rc.load_user_config()
    assert data["llm"]["api_key"] == "k1"
    assert data["llm"]["model_text"] == "m1"
    # tmp 文件不残留
    assert not (rc.config_path().with_suffix(".json.tmp")).exists()


def test_save_clear_with_empty_string():
    rc.save_user_config({"llm": {"api_key": "k1"}})
    rc.save_user_config({"llm": {"api_key": ""}})  # 用空字符串清空
    rc.clear_cache()
    with override_settings(LLM_API_KEY="env-key"):
        cfg = rc.llm_config()
    # 空字符串视作"清空" → 落到 env
    assert cfg.api_key == "env-key"


def test_save_none_keeps_existing():
    rc.save_user_config({"llm": {"api_key": "k1"}})
    rc.save_user_config({"llm": {"api_key": None}})  # None 表示不动
    rc.clear_cache()
    cfg = rc.llm_config()
    assert cfg.api_key == "k1"


def test_sources_metadata():
    rc.save_user_config({"llm": {"api_key": "user-key"}})
    with override_settings(LLM_API_KEY="env-key", LLM_MODEL_TEXT="env-text"):
        _cfg, sources = rc.llm_config_with_sources()
    assert sources["api_key"] == "user"
    assert sources["model_text"] == "env"


def test_corrupt_json_falls_back_silently(tmp_path):
    p = rc.config_path()
    p.write_text("{ not json", encoding="utf-8")
    rc.clear_cache()
    # Should not raise; just returns empty
    data = rc.load_user_config(force=True)
    assert data == {}


def test_cache_returns_same_dict():
    rc.save_user_config({"llm": {"api_key": "k1"}})
    a = rc.load_user_config()
    b = rc.load_user_config()
    assert a is b  # cache hit
    rc.clear_cache()
    c = rc.load_user_config()
    assert c is not a  # fresh read after clear
