"""ft-022: 集中路径管理 + docling 模型缓存重定向 (HF_HOME / TRANSFORMERS_CACHE)。

设计决策
========

1. **不依赖 ``django.conf.settings``**：本模块的 import 副作用要在 ``config.settings``
   加载早期就生效（确保 ``HF_HOME`` 在 docling 任何 import 之前定下来）。
   因此 ``data_dir()`` 只读环境变量 + 跨平台默认，**与** settings 里 ``_resolve_data_dir``
   保持完全一致即可（settings 里也复用本模块的 ``data_dir()``）。

2. **环境变量 ``EXPLORE_OS_DATA_DIR`` 优先**：Electron sidecar 启动时由壳传入。

3. **跨平台默认**：
   * Windows: ``%APPDATA%/explore-os``
   * macOS:  ``~/Library/Application Support/explore-os``
   * Linux:  ``~/.config/explore-os``

4. **副作用**：模块 import 时设置 ``HF_HOME`` 与 ``TRANSFORMERS_CACHE`` 到
   ``data_dir() / "cache" / "huggingface"`` 子树。``setdefault`` 保证用户
   显式 export 的优先级更高。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def data_dir() -> Path:
    """返回数据根目录。

    优先级：``EXPLORE_OS_DATA_DIR`` env > 平台默认。
    """
    env_dir = os.environ.get("EXPLORE_OS_DATA_DIR")
    if env_dir:
        p = Path(env_dir)
    elif os.name == "nt":
        appdata = os.environ.get("APPDATA")
        # 极端情况下 APPDATA 缺失（CI 容器），退化到 home/.config
        base = Path(appdata) if appdata else Path.home() / ".config"
        p = base / "explore-os"
    elif sys.platform == "darwin":
        p = Path.home() / "Library" / "Application Support" / "explore-os"
    else:
        p = Path.home() / ".config" / "explore-os"
    p.mkdir(parents=True, exist_ok=True)
    return p


def media_dir() -> Path:
    p = data_dir() / "media"
    p.mkdir(parents=True, exist_ok=True)
    return p


def papers_dir() -> Path:
    """arXiv PDF 缓存。历史路径是 ``media/papers``，保持同名以减少改动。"""
    p = media_dir() / "papers"
    p.mkdir(parents=True, exist_ok=True)
    return p


def figures_dir(arxiv_id: str) -> Path:
    p = media_dir() / "figures" / arxiv_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def equations_dir(arxiv_id: str) -> Path:
    p = media_dir() / "equations" / arxiv_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def render_dir(arxiv_id: str) -> Path:
    p = media_dir() / "render" / arxiv_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def memory_dir() -> Path:
    """订阅级记忆线根（``media/memory/<sub_name>/``）."""
    p = media_dir() / "memory"
    p.mkdir(parents=True, exist_ok=True)
    return p


def cache_dir() -> Path:
    """通用缓存根（HF / docling / 模型权重等都挂这下）."""
    p = data_dir() / "cache"
    p.mkdir(parents=True, exist_ok=True)
    return p


def outbox_dir() -> Path:
    """SMTP fallback 写 ``.eml`` 的位置。"""
    p = data_dir() / "outbox"
    p.mkdir(parents=True, exist_ok=True)
    return p


def pdf_legacy_dir() -> Path:
    """ft-014 旧路径 ``media/pdf``：用于兼容现有 CLI 默认 pdf 位置。"""
    p = media_dir() / "pdf"
    p.mkdir(parents=True, exist_ok=True)
    return p


# ---- 副作用：HF_HOME / TRANSFORMERS_CACHE 重定向 ----
# 必须在 docling 任何 import 前生效。``config.settings`` 在文件顶部 import
# 本模块以触发副作用。``setdefault`` 让用户显式 export 优先。
_HF_CACHE = cache_dir() / "huggingface"
os.environ.setdefault("HF_HOME", str(_HF_CACHE))
os.environ.setdefault("TRANSFORMERS_CACHE", str(_HF_CACHE / "transformers"))
