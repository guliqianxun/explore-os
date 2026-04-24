"""arXiv Export API fetcher.

实现 ``SourceFetcher`` Protocol，抓取 arXiv 最近新增 paper。

- Endpoint: ``http://export.arxiv.org/api/query``（Atom XML 响应）
- 查询构造：优先使用 ``query.arxiv_query``；若为空则用
  ``query.keywords`` 合成 ``all:"kw1" OR all:"kw2"``；若存在
  ``query.arxiv_categories`` 则以 ``AND (cat:xxx OR cat:yyy)`` 追加。
- 网络层用 httpx + tenacity，重试 3 次（指数退避），最终失败返回 ``[]``。
- Atom 解析用标准库 ``xml.etree.ElementTree``，仅依赖 stdlib。
- ``dedup_key`` 规范化：从 ``http://arxiv.org/abs/2401.12345v2`` 抽 ``arxiv:2401.12345``（去 version）。
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

import httpx
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from sources.base import Group, Item, SourceFetcher, SourceKey, SourceQuery, register


log = logging.getLogger(__name__)


ARXIV_API_URL = "https://export.arxiv.org/api/query"
ATOM_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}

# 形如 2401.12345 或 2401.12345v2 的 arXiv id（新格式）
_ARXIV_NEW_ID = re.compile(r"(\d{4}\.\d{4,5})(v\d+)?$")
# 旧格式：archive/subj-class/YYMMNNN（如 math.GT/0309136）
_ARXIV_OLD_ID = re.compile(r"([a-z\-]+(?:\.[A-Z]{2})?/\d{7})(v\d+)?$")


def _build_search_query(query: SourceQuery) -> str:
    """根据 SourceQuery 构造 arXiv ``search_query`` 参数。"""
    if query.arxiv_query:
        base = query.arxiv_query.strip()
    elif query.keywords:
        base = " OR ".join(f'all:"{kw}"' for kw in query.keywords)
    else:
        base = ""

    if query.arxiv_categories:
        cats = " OR ".join(f"cat:{c}" for c in query.arxiv_categories)
        if base:
            return f"({base}) AND ({cats})"
        return f"({cats})"
    return base


def _normalize_dedup_key(arxiv_url_or_id: str) -> str:
    """从 arXiv id URL 抽取规范化 dedup_key。

    - ``http://arxiv.org/abs/2401.12345v2`` -> ``arxiv:2401.12345``
    - ``http://arxiv.org/abs/math.GT/0309136`` -> ``arxiv:math.GT/0309136``
    - 失败时回退为 ``arxiv:<raw>``。
    """
    s = arxiv_url_or_id.strip()
    m = _ARXIV_NEW_ID.search(s) or _ARXIV_OLD_ID.search(s)
    if m:
        return f"arxiv:{m.group(1)}"
    # 兜底：去掉协议/前缀
    tail = s.rsplit("/", 1)[-1]
    tail = re.sub(r"v\d+$", "", tail)
    return f"arxiv:{tail}" if tail else "arxiv:unknown"


def _external_id_from_entry_id(entry_id: str) -> str:
    """从 entry id 抽 external_id（保留 version，作为原样标识）。"""
    tail = entry_id.rsplit("/abs/", 1)[-1]
    return tail or entry_id


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        # arXiv 返回 RFC3339（形如 2024-01-02T12:00:00Z）
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _parse_atom(xml_text: str) -> list[Item]:
    items: list[Item] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        log.error("arxiv: failed to parse atom xml: %s", e)
        return items

    for entry in root.findall("atom:entry", ATOM_NS):
        entry_id = (entry.findtext("atom:id", default="", namespaces=ATOM_NS) or "").strip()
        if not entry_id:
            continue
        title = (entry.findtext("atom:title", default="", namespaces=ATOM_NS) or "").strip()
        summary = (entry.findtext("atom:summary", default="", namespaces=ATOM_NS) or "").strip()
        published = _parse_datetime(
            (entry.findtext("atom:published", default="", namespaces=ATOM_NS) or "").strip()
        )

        authors: list[str] = []
        for a in entry.findall("atom:author", ATOM_NS):
            name = (a.findtext("atom:name", default="", namespaces=ATOM_NS) or "").strip()
            if name:
                authors.append(name)

        # 首选 rel="alternate" 的 link，否则用 entry id
        url = ""
        for link in entry.findall("atom:link", ATOM_NS):
            if link.get("rel") == "alternate":
                url = link.get("href", "") or ""
                break
        if not url:
            url = entry_id

        external_id = _external_id_from_entry_id(entry_id)
        dedup_key = _normalize_dedup_key(entry_id)

        items.append(
            Item(
                external_id=external_id,
                title=re.sub(r"\s+", " ", title),
                abstract=re.sub(r"\s+", " ", summary),
                url=url,
                source_key="arxiv",
                group="papers",
                authors=authors,
                venue="arXiv",
                published_at=published,
                dedup_key=dedup_key,
                raw={"id": entry_id},
            )
        )
    return items


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((httpx.HTTPError,)),
)
def _http_get(client: httpx.Client, params: dict) -> httpx.Response:
    resp = client.get(ARXIV_API_URL, params=params)
    resp.raise_for_status()
    return resp


class ArxivFetcher:
    """arXiv Export API fetcher。"""

    key: SourceKey = "arxiv"
    group: Group = "papers"

    def __init__(self, client: httpx.Client | None = None, timeout: float = 20.0):
        self._client = client
        self._timeout = timeout

    def _get_client(self) -> tuple[httpx.Client, bool]:
        if self._client is not None:
            return self._client, False
        return httpx.Client(timeout=self._timeout, follow_redirects=True), True

    def fetch(
        self,
        query: SourceQuery,
        since: datetime,
        limit: int = 50,
    ) -> list[Item]:
        search_query = _build_search_query(query)
        if not search_query:
            log.warning("arxiv: empty search query, skipping fetch")
            return []

        params = {
            "search_query": search_query,
            "start": 0,
            "max_results": max(1, min(int(limit), 2000)),
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }

        client, owns = self._get_client()
        try:
            try:
                resp = _http_get(client, params)
            except (httpx.HTTPError, RetryError) as e:
                log.error("arxiv: HTTP failed after retries: %s", e)
                return []
            items = _parse_atom(resp.text)
        finally:
            if owns:
                client.close()

        # 过滤 since（since 应为 aware；若 naive，视为 UTC）
        if since is not None:
            since_aware = since if since.tzinfo else since.replace(tzinfo=timezone.utc)
            items = [
                it
                for it in items
                if it.published_at is None
                or (
                    it.published_at if it.published_at.tzinfo else it.published_at.replace(tzinfo=timezone.utc)
                )
                >= since_aware
            ]

        return items[:limit]


register(ArxivFetcher())
