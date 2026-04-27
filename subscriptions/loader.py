"""YAML 订阅加载（MVP：不走 DB）."""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class PerspectiveSpec:
    preset: str = ""   # researcher | engineer | pm | student
    custom: str = ""   # 自由文本，优先级高于 preset


@dataclass(slots=True)
class SourceSpec:
    key: str
    params: dict = field(default_factory=dict)


@dataclass(slots=True)
class DeliverySpec:
    channel: str = "email"
    to: str = ""
    depth: str = "tldr"
    schedule: str = ""
    max_items: int = 15


@dataclass(slots=True)
class SubscriptionSpec:
    name: str
    interests: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    sources: list[SourceSpec] = field(default_factory=list)
    deliveries: list[DeliverySpec] = field(default_factory=list)
    perspective: PerspectiveSpec = field(default_factory=PerspectiveSpec)
    enabled: bool = True


def load(path: str | Path) -> list[SubscriptionSpec]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    subs: list[SubscriptionSpec] = []
    for raw in data.get("subscriptions") or []:
        persp = raw.get("perspective") or {}
        subs.append(SubscriptionSpec(
            name=raw["name"],
            enabled=raw.get("enabled", True),
            interests=list(raw.get("interests") or []),
            exclude=list(raw.get("exclude") or []),
            sources=[SourceSpec(key=s["key"], params=dict(s.get("params") or {}))
                     for s in (raw.get("sources") or [])],
            deliveries=[DeliverySpec(
                channel=d.get("channel", "email"),
                to=d.get("to", ""),
                depth=d.get("depth", "tldr"),
                schedule=d.get("schedule", ""),
                max_items=int(d.get("max_items", 15)),
            ) for d in (raw.get("deliveries") or [])],
            perspective=PerspectiveSpec(
                preset=str(persp.get("preset") or ""),
                custom=str(persp.get("custom") or ""),
            ),
        ))
    return subs


def find(subs: list[SubscriptionSpec], name: str) -> SubscriptionSpec | None:
    for s in subs:
        if s.name == name:
            return s
    return None


# ---------------------------------------------------------------------------
# ft-027: dict-level load + save (used by DRF subscription endpoints).
# 这两个函数面向 API 层：以 dict 形式读写订阅，并尽量保留 YAML 注释 +
# key 顺序（用 ruamel.yaml）。dataclass 视图（``load`` / ``find``）对历史
# CLI 仍可用，本模块不动。
# ---------------------------------------------------------------------------

def _ruamel():
    """惰性导入 ruamel.yaml 以避免在 dataclass-only 路径上引入硬依赖。"""
    from ruamel.yaml import YAML
    y = YAML()
    y.preserve_quotes = True
    y.indent(mapping=2, sequence=4, offset=2)
    y.width = 4096
    return y


def load_subscriptions(path: str | Path) -> list[dict[str, Any]]:
    """读取整份 YAML，返回 ``subscriptions`` 列表（每项是 dict）。

    文件不存在 → 返回 []。注释/key 顺序由 ruamel.yaml 保留（在 round-trip
    save 路径里有用；纯读者可忽略）。
    """
    p = Path(path)
    if not p.exists():
        return []
    y = _ruamel()
    data = y.load(p.read_text(encoding="utf-8")) or {}
    raw = data.get("subscriptions") or []
    # 转成普通 dict（剥离 CommentedMap），便于 DRF 序列化
    out: list[dict[str, Any]] = []
    for item in raw:
        out.append(_to_plain(item))
    return out


def save_subscriptions(path: str | Path, subs: list[dict[str, Any]]) -> None:
    """保存订阅列表到 YAML。

    - 若文件已存在：用 ruamel round-trip 加载原文，**仅替换** ``subscriptions``
      节点，其余顶层键 + 注释保留。
    - 若不存在：从空文档新建。
    """
    p = Path(path)
    y = _ruamel()
    if p.exists():
        data = y.load(p.read_text(encoding="utf-8")) or {}
    else:
        data = {}
    data["subscriptions"] = subs
    buf = io.StringIO()
    y.dump(data, buf)
    p.write_text(buf.getvalue(), encoding="utf-8")


def _to_plain(obj: Any) -> Any:
    """递归把 ruamel CommentedMap/CommentedSeq 转回普通 dict/list。"""
    if isinstance(obj, dict):
        return {str(k): _to_plain(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_plain(v) for v in obj]
    return obj
