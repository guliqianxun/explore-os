"""User settings: LLM 接口配置。

GET  /api/settings/llm/        当前生效配置（api_key 掩码）+ source-by-field
PUT  /api/settings/llm/        合并写入 user_config.json；空字符串=清空
POST /api/settings/llm/test/   ping 一次 chat 验证连通
"""
from __future__ import annotations

import time
from typing import Any

from rest_framework import status as drf_status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.llm import client as llm_client
from apps.llm.errors import LLMError
from apps.llm.runtime_config import (
    config_path,
    llm_config_with_sources,
    save_user_config,
)


_FIELDS = (
    "api_base",
    "api_key",
    "model_text",
    "model_multimodal",
    "model_vision_classifier",
    "model_deep",
    "daily_budget_cny",
)


def _mask_key(key: str) -> str:
    """完整 key 不外露：仅展示 first2..last4，长度不足直接返回空。"""
    if not key:
        return ""
    if len(key) <= 8:
        return "•" * len(key)
    return f"{key[:2]}...{key[-4:]}"


def _serialize(cfg, sources: dict[str, str]) -> dict[str, Any]:
    return {
        "api_base": cfg.api_base,
        "api_key_masked": _mask_key(cfg.api_key),
        "api_key_set": bool(cfg.api_key),
        "model_text": cfg.model_text,
        "model_multimodal": cfg.model_multimodal,
        "model_vision_classifier": cfg.model_vision_classifier,
        "model_deep": cfg.model_deep,
        "daily_budget_cny": cfg.daily_budget_cny,
        "sources": sources,
        "config_path": str(config_path()),
    }


class SettingsLLMView(APIView):
    """GET 当前配置；PUT 部分更新。"""

    def get(self, request):
        cfg, sources = llm_config_with_sources()
        return Response(_serialize(cfg, sources))

    def put(self, request):
        body = request.data or {}
        if not isinstance(body, dict):
            return Response({"error": "expected JSON object"}, status=drf_status.HTTP_400_BAD_REQUEST)

        patch: dict[str, Any] = {}
        for k in _FIELDS:
            if k not in body:
                continue
            v = body[k]
            if k == "daily_budget_cny":
                if v in (None, ""):
                    patch[k] = None  # ignore
                    continue
                try:
                    patch[k] = float(v)
                except (TypeError, ValueError):
                    return Response(
                        {"error": f"daily_budget_cny must be numeric, got {v!r}"},
                        status=drf_status.HTTP_400_BAD_REQUEST,
                    )
            else:
                if v is None:
                    continue
                patch[k] = str(v)

        # api_base 简单校验：必须 http(s)://
        ab = patch.get("api_base")
        if ab and not (ab.startswith("http://") or ab.startswith("https://")):
            return Response(
                {"error": "api_base must start with http:// or https://"},
                status=drf_status.HTTP_400_BAD_REQUEST,
            )

        save_user_config({"llm": patch})
        cfg, sources = llm_config_with_sources()
        return Response(_serialize(cfg, sources))


class SettingsLLMTestView(APIView):
    """ping 一次 chat 验证 base/key/model 联通。"""

    def post(self, request):
        t0 = time.monotonic()
        try:
            res = llm_client.chat(
                [
                    {"role": "system", "content": "Reply with the single word OK."},
                    {"role": "user", "content": "ping"},
                ],
                temperature=0.0,
                max_tokens=8,
                timeout=15.0,
            )
        except LLMError as exc:
            return Response(
                {"ok": False, "error": str(exc), "kind": "config"},
                status=drf_status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:  # noqa: BLE001  httpx / network / vendor errors
            return Response(
                {"ok": False, "error": f"{type(exc).__name__}: {exc}", "kind": "network"},
                status=drf_status.HTTP_502_BAD_GATEWAY,
            )
        latency_ms = int((time.monotonic() - t0) * 1000)
        return Response(
            {
                "ok": True,
                "model": res.model,
                "content": (res.content or "")[:80],
                "usage": res.usage,
                "latency_ms": latency_ms,
            }
        )


__all__ = ["SettingsLLMView", "SettingsLLMTestView"]
