"""ft-016: 推送渠道抽象层。

工具 = 内容生产 + 渠道接口。adapter 实现具体投递。
当前 adapter：email（实现）/ feishu（stub）/ wechat_subscription（stub）。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from interpret.interpretation import DeepOut, SkimOut
from interpret.narrative import Narrative
from sources.base import Item

log = logging.getLogger(__name__)


# ---------------- Renderer-neutral content payloads ----------------

@dataclass(slots=True)
class RenderedDeep:
    item: Item
    deep: DeepOut
    skim: SkimOut | None = None
    dup_sources: list[str] = field(default_factory=list)
    index: int = 0


@dataclass(slots=True)
class RenderedSkim:
    item: Item
    skim: SkimOut | None = None
    deep: DeepOut | None = None    # 复用图字段（framework / qualitative）
    dup_sources: list[str] = field(default_factory=list)
    index: int = 0


@dataclass(slots=True)
class Digest:
    """渠道无关的内容包。所有 adapter 从这里出发自行渲染。"""
    subject: str
    run_summary: str = ""
    narrative: Narrative | None = None
    deeps: list[RenderedDeep] = field(default_factory=list)
    skims: list[RenderedSkim] = field(default_factory=list)
    # cid → 本地文件路径；email 用 CID 内嵌；微信用 media_id 上传；飞书用 image_key
    inline_images: dict[str, Path] = field(default_factory=dict)


# ---------------- Delivery target / result ----------------

@dataclass(slots=True)
class DeliveryTarget:
    """渠道目标。各 adapter 按需读取自己关心的字段。"""
    channel: str
    to: str = ""                # email→addr / feishu→webhook / wechat→openid 或空
    params: dict = field(default_factory=dict)   # adapter-specific


@dataclass(slots=True)
class DeliveryResult:
    success: bool
    detail: str = ""
    metadata: dict = field(default_factory=dict)   # msgid / draft_id / msg_url


class DeliveryError(RuntimeError):
    pass


# ---------------- Adapter protocol + registry ----------------

class DeliveryAdapter(Protocol):
    """每个 adapter 实现：key + deliver(digest, target)."""
    key: str

    def deliver(self, digest: Digest, target: DeliveryTarget) -> DeliveryResult:
        ...


REGISTRY: dict[str, DeliveryAdapter] = {}


def register(adapter: DeliveryAdapter) -> None:
    REGISTRY[adapter.key] = adapter


def get(key: str) -> DeliveryAdapter:
    if key not in REGISTRY:
        raise KeyError(
            f"Unknown delivery channel: {key}. Registered: {list(REGISTRY)}"
        )
    return REGISTRY[key]
