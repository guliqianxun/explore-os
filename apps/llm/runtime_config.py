"""LLM 运行时配置：user_config.json 覆盖 .env / settings 默认。

Why
---
打包后的 desktop app 没有 .env 文件，且 Django ``settings.LLM_*`` 在进程启动
时一次性冻结。用户没有方法在不重启 sidecar 的情况下改 API key / 端点。

Behavior
--------
- 配置文件：``<EXPLORE_OS_DATA_DIR>/user_config.json``
- 解析顺序（按字段独立 fallback）：user_config.json > settings (= env / 默认)
- 60s in-process cache，写入时立即失效
- 原子写：tmp 文件 + ``os.replace``

Schema
------
```json
{
  "llm": {
    "api_base":               "https://api.openai.com/v1",
    "api_key":                "sk-...",
    "model_text":             "gpt-4o-mini",
    "model_multimodal":       "",
    "model_vision_classifier":"",
    "model_deep":             "",
    "daily_budget_cny":       30.0
  }
}
```

任何字段缺失/空字符串都触发 fallback。``daily_budget_cny`` 为 None / 0 时同样回落到 settings。
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from django.conf import settings

from apps.core.paths import data_dir

log = logging.getLogger(__name__)

CONFIG_FILENAME = "user_config.json"
_CACHE_TTL = 60.0


@dataclass(frozen=True, slots=True)
class LLMConfig:
    """运行时生效的 LLM 配置（合并后）。"""

    api_base: str
    api_key: str
    model_text: str
    model_multimodal: str
    model_vision_classifier: str
    model_deep: str
    daily_budget_cny: float


# ---------- Cache ----------

_cache: dict[str, Any] | None = None
_cache_at: float = 0.0


def config_path() -> Path:
    return data_dir() / CONFIG_FILENAME


def _read_raw() -> dict[str, Any]:
    p = config_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("[runtime_config] failed to read %s: %r", p, exc)
        return {}


def load_user_config(*, force: bool = False) -> dict[str, Any]:
    """读 user_config.json。60s cache；force=True 跳过 cache。"""
    global _cache, _cache_at
    now = time.monotonic()
    if not force and _cache is not None and (now - _cache_at) < _CACHE_TTL:
        return _cache
    data = _read_raw()
    _cache = data
    _cache_at = now
    return data


def save_user_config(updates: dict[str, Any]) -> dict[str, Any]:
    """合并写入 user_config.json（top-level merge by section）。

    ``updates`` 形如 ``{"llm": {"api_key": "...", ...}}``。每个 section 内做浅合并；
    传入空字符串值表示**清空**该字段，传入 None 表示**保留**原值。
    """
    global _cache, _cache_at
    current = _read_raw()
    for section, patch in updates.items():
        if not isinstance(patch, dict):
            continue
        existing = current.get(section) or {}
        merged = dict(existing)
        for k, v in patch.items():
            if v is None:
                continue
            merged[k] = v
        current[section] = merged

    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, p)

    _cache = current
    _cache_at = time.monotonic()
    return current


def clear_cache() -> None:
    """测试用：强制下次 load 重读盘。"""
    global _cache, _cache_at
    _cache = None
    _cache_at = 0.0


# ---------- LLM section resolver ----------


def _setting(name: str, default: str = "") -> str:
    return getattr(settings, name, default) or ""


def llm_config() -> LLMConfig:
    """合并 user_config 与 settings，得到当前生效的 LLM 配置。"""
    raw = (load_user_config().get("llm") or {})

    def pick(key: str, *settings_names: str, fallback: str = "") -> str:
        v = raw.get(key)
        if v:
            return str(v)
        for sn in settings_names:
            sv = _setting(sn)
            if sv:
                return sv
        return fallback

    text = pick("model_text", "LLM_MODEL_TEXT", "LLM_MODEL")
    multimodal = pick("model_multimodal", "LLM_MODEL_MULTIMODAL")
    vision = pick(
        "model_vision_classifier",
        "LLM_MODEL_VISION_CLASSIFIER",
        "LLM_MODEL_MULTIMODAL",
    )
    deep = pick("model_deep", "LLM_MODEL_DEEP")

    budget_raw = raw.get("daily_budget_cny")
    try:
        budget = float(budget_raw) if budget_raw not in (None, "") else 0.0
    except (TypeError, ValueError):
        budget = 0.0
    if budget <= 0:
        budget = float(getattr(settings, "LLM_DAILY_BUDGET_CNY", 0.0) or 0.0)

    return LLMConfig(
        api_base=pick("api_base", "LLM_API_BASE", fallback="https://api.openai.com/v1"),
        api_key=pick("api_key", "LLM_API_KEY"),
        model_text=text,
        model_multimodal=multimodal,
        model_vision_classifier=vision,
        model_deep=deep,
        daily_budget_cny=budget,
    )


def llm_config_with_sources() -> tuple[LLMConfig, dict[str, str]]:
    """返回 (config, source-by-field)。source ∈ {"user", "env", "default"}.

    给 settings GET 接口用，让前端展示每个字段是哪一层生效。
    """
    raw = (load_user_config().get("llm") or {})
    cfg = llm_config()

    def src(key: str, *settings_names: str) -> str:
        if raw.get(key):
            return "user"
        for sn in settings_names:
            if _setting(sn):
                return "env"
        return "default"

    sources = {
        "api_base": src("api_base", "LLM_API_BASE"),
        "api_key": src("api_key", "LLM_API_KEY"),
        "model_text": src("model_text", "LLM_MODEL_TEXT", "LLM_MODEL"),
        "model_multimodal": src("model_multimodal", "LLM_MODEL_MULTIMODAL"),
        "model_vision_classifier": src(
            "model_vision_classifier",
            "LLM_MODEL_VISION_CLASSIFIER",
            "LLM_MODEL_MULTIMODAL",
        ),
        "model_deep": src("model_deep", "LLM_MODEL_DEEP"),
        "daily_budget_cny": (
            "user" if raw.get("daily_budget_cny") not in (None, "")
            else ("env" if getattr(settings, "LLM_DAILY_BUDGET_CNY", 0) else "default")
        ),
    }
    return cfg, sources


__all__ = [
    "LLMConfig",
    "CONFIG_FILENAME",
    "config_path",
    "load_user_config",
    "save_user_config",
    "clear_cache",
    "llm_config",
    "llm_config_with_sources",
]
