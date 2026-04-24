"""ft-003 arXiv fetcher 测试（不打真实 API）。"""
from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest

from sources.base import SourceQuery
from sources.fetchers.arxiv import (
    ArxivFetcher,
    _build_search_query,
    _normalize_dedup_key,
)


# ---------------- fixture XML ----------------

SAMPLE_ATOM_TWO_ENTRIES = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>arXiv Query</title>
  <entry>
    <id>http://arxiv.org/abs/2401.12345v2</id>
    <updated>2024-02-01T00:00:00Z</updated>
    <published>2024-01-15T08:30:00Z</published>
    <title>Diffusion Models for Everything</title>
    <summary>  We study diffusion models
    across many domains.  </summary>
    <author><name>Alice Example</name></author>
    <author><name>Bob Example</name></author>
    <link href="http://arxiv.org/abs/2401.12345v2" rel="alternate" type="text/html"/>
    <link href="http://arxiv.org/pdf/2401.12345v2" rel="related" type="application/pdf"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2402.99999</id>
    <updated>2024-03-01T00:00:00Z</updated>
    <published>2024-02-20T10:00:00Z</published>
    <title>Another Paper</title>
    <summary>Short abstract.</summary>
    <author><name>Carol Example</name></author>
    <link href="http://arxiv.org/abs/2402.99999" rel="alternate" type="text/html"/>
  </entry>
</feed>
"""

EMPTY_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>arXiv Query</title>
</feed>
"""


# ---------------- helpers ----------------


def _make_client(handler) -> httpx.Client:
    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport)


# ---------------- tests ----------------


def test_normalize_dedup_key_strips_version():
    assert _normalize_dedup_key("http://arxiv.org/abs/2401.12345v2") == "arxiv:2401.12345"
    assert _normalize_dedup_key("http://arxiv.org/abs/2401.12345") == "arxiv:2401.12345"
    assert _normalize_dedup_key("http://arxiv.org/abs/2401.12345v10") == "arxiv:2401.12345"
    # 旧格式
    assert (
        _normalize_dedup_key("http://arxiv.org/abs/math.GT/0309136v1")
        == "arxiv:math.GT/0309136"
    )


def test_build_search_query_prefers_arxiv_query():
    q = SourceQuery(arxiv_query='ti:"foo" AND cat:cs.AI', keywords=["ignored"])
    assert _build_search_query(q) == 'ti:"foo" AND cat:cs.AI'


def test_build_search_query_falls_back_to_keywords():
    q = SourceQuery(keywords=["diffusion model", "flow matching"])
    assert _build_search_query(q) == 'all:"diffusion model" OR all:"flow matching"'


def test_build_search_query_with_categories():
    q = SourceQuery(keywords=["vlm"], arxiv_categories=["cs.AI", "cs.CV"])
    assert (
        _build_search_query(q)
        == '(all:"vlm") AND (cat:cs.AI OR cat:cs.CV)'
    )


def test_fetch_parses_atom_entries():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, text=SAMPLE_ATOM_TWO_ENTRIES)

    client = _make_client(handler)
    fetcher = ArxivFetcher(client=client)

    items = fetcher.fetch(
        SourceQuery(arxiv_query='all:"diffusion"'),
        since=datetime(2020, 1, 1, tzinfo=timezone.utc),
        limit=50,
    )

    assert len(items) == 2
    first = items[0]
    assert first.source_key == "arxiv"
    assert first.group == "papers"
    assert first.external_id == "2401.12345v2"
    assert first.title == "Diffusion Models for Everything"
    assert "diffusion models" in first.abstract.lower()
    assert first.authors == ["Alice Example", "Bob Example"]
    assert first.dedup_key == "arxiv:2401.12345"
    assert first.url == "http://arxiv.org/abs/2401.12345v2"
    assert first.published_at is not None
    assert first.venue == "arXiv"

    # 请求参数验证
    assert captured["params"]["search_query"] == 'all:"diffusion"'
    assert captured["params"]["sortBy"] == "submittedDate"


def test_fetch_uses_keyword_fallback_when_no_arxiv_query():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, text=EMPTY_FEED)

    client = _make_client(handler)
    fetcher = ArxivFetcher(client=client)

    items = fetcher.fetch(
        SourceQuery(keywords=["llm", "agent"]),
        since=datetime(2020, 1, 1, tzinfo=timezone.utc),
        limit=10,
    )
    assert items == []
    assert captured["params"]["search_query"] == 'all:"llm" OR all:"agent"'


def test_fetch_filters_since():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=SAMPLE_ATOM_TWO_ENTRIES)

    client = _make_client(handler)
    fetcher = ArxivFetcher(client=client)

    # since 晚于第一篇 (2024-01-15), 早于第二篇 (2024-02-20)
    items = fetcher.fetch(
        SourceQuery(arxiv_query="all:x"),
        since=datetime(2024, 2, 1, tzinfo=timezone.utc),
        limit=50,
    )
    assert len(items) == 1
    assert items[0].external_id == "2402.99999"


def test_fetch_returns_empty_on_http_failure(caplog):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503, text="nope")

    client = _make_client(handler)
    fetcher = ArxivFetcher(client=client)

    import logging

    with caplog.at_level(logging.ERROR, logger="sources.fetchers.arxiv"):
        items = fetcher.fetch(
            SourceQuery(arxiv_query="all:x"),
            since=datetime(2020, 1, 1, tzinfo=timezone.utc),
            limit=10,
        )

    assert items == []
    # 重试 3 次
    assert calls["n"] == 3
    assert any("HTTP failed" in rec.message for rec in caplog.records)


def test_fetch_returns_empty_on_empty_query():
    # 无 arxiv_query 也无 keywords -> 直接返回 []
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("should not call HTTP")

    client = _make_client(handler)
    fetcher = ArxivFetcher(client=client)
    assert fetcher.fetch(SourceQuery(), since=datetime(2020, 1, 1, tzinfo=timezone.utc)) == []


def test_registered_in_registry():
    from sources.base import REGISTRY, get

    # 触发注册
    import sources.fetchers  # noqa: F401

    assert "arxiv" in REGISTRY
    assert get("arxiv").key == "arxiv"
    assert get("arxiv").group == "papers"
