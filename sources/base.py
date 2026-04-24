"""Source fetcher 接口契约（ft-003 / ft-004 共用）。

两个 fetcher 各自在 sources/fetchers/<key>.py 实现 SourceFetcher，并在模块
加载时通过 register() 注册到 REGISTRY。下游（rewriter / 管线 / CLI）统一
按 SourceKey 查找 fetcher，不做类型分支。

MVP 阶段 fetcher 只负责返回结构化 Item 列表，不负责入库、去重、排序——
这些在后续 feature（ft-005 等）中实现。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


SourceKey = str  # e.g. "arxiv", "hf_papers"
Group = str      # e.g. "papers", "code", "models"


@dataclass(slots=True)
class Item:
    """跨信源的统一条目。"""
    external_id: str                  # source 内唯一 id，如 arxiv id
    title: str
    abstract: str
    url: str
    source_key: SourceKey
    group: Group
    authors: list[str] = field(default_factory=list)
    venue: str = ""
    published_at: datetime | None = None
    # 规范化去重键：优先 arxiv_id > doi > f"{source_key}:{external_id}"
    dedup_key: str = ""
    raw: dict = field(default_factory=dict)  # 原始响应，便于调试/回溯


@dataclass(slots=True)
class SourceQuery:
    """rewriter 产出、fetcher 消费的查询对象。

    各 fetcher 按需读取自己认识的字段，其它字段忽略。
    """
    keywords: list[str] = field(default_factory=list)   # 通用关键词
    arxiv_query: str = ""                                # arXiv 原生布尔串
    arxiv_categories: list[str] = field(default_factory=list)
    hf_keywords: list[str] = field(default_factory=list) # HF Papers 过滤关键词
    raw: dict = field(default_factory=dict)              # rewriter 原始输出


class SourceFetcher(Protocol):
    """所有 fetcher 必须实现的接口。"""
    key: SourceKey
    group: Group

    def fetch(
        self,
        query: SourceQuery,
        since: datetime,
        limit: int = 50,
    ) -> list[Item]:
        """按 query 拉取 since 之后的条目，上限 limit。

        - 必须稳定返回 list[Item]（失败返回空 list 并记录日志，不抛异常到顶层）
        - 必须填充 dedup_key（若无 arxiv_id/doi，用 f"{source_key}:{external_id}"）
        - 实现应内置重试 / 限流退避
        """
        ...


# ---------------- Registry ----------------

REGISTRY: dict[SourceKey, SourceFetcher] = {}


def register(fetcher: SourceFetcher) -> None:
    REGISTRY[fetcher.key] = fetcher


def get(key: SourceKey) -> SourceFetcher:
    if key not in REGISTRY:
        raise KeyError(f"Unknown source key: {key}. Registered: {list(REGISTRY)}")
    return REGISTRY[key]
