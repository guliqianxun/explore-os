"""YAML 订阅加载（MVP：不走 DB）."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


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
    enabled: bool = True


def load(path: str | Path) -> list[SubscriptionSpec]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    subs: list[SubscriptionSpec] = []
    for raw in data.get("subscriptions") or []:
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
        ))
    return subs


def find(subs: list[SubscriptionSpec], name: str) -> SubscriptionSpec | None:
    for s in subs:
        if s.name == name:
            return s
    return None
