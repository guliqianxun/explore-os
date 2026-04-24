"""Tests for ft-004 HuggingFace Daily Papers fetcher."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import pytest

from sources.base import SourceQuery
from sources.fetchers.hf_papers import HFPapersFetcher


DAY_1 = datetime(2026, 4, 20, tzinfo=timezone.utc)
DAY_2 = datetime(2026, 4, 21, tzinfo=timezone.utc)


def _paper(
    arxiv_id: str,
    title: str,
    summary: str = "",
    authors: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "paper": {
            "id": arxiv_id,
            "title": title,
            "summary": summary,
            "authors": [{"name": n} for n in (authors or ["A. Researcher"])],
            "publishedAt": "2026-04-20T00:00:00.000Z",
        },
        "publishedAt": "2026-04-20T12:00:00.000Z",
        "submittedOnDailyAt": "2026-04-20T12:00:00.000Z",
    }


def _make_transport(per_day: dict[str, list[dict] | Exception]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        day = request.url.params.get("date", "")
        result = per_day.get(day, [])
        if isinstance(result, Exception):
            raise result
        return httpx.Response(200, content=json.dumps(result).encode("utf-8"))

    return httpx.MockTransport(handler)


def _freeze_today(monkeypatch, d: datetime) -> None:
    import sources.fetchers.hf_papers as mod

    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            return d if tz is None else d.astimezone(tz)

    monkeypatch.setattr(mod, "datetime", _FrozenDatetime)


# ---------------- tests ----------------

def test_single_day_parse(monkeypatch):
    _freeze_today(monkeypatch, DAY_1)
    transport = _make_transport({
        "2026-04-20": [
            _paper("2401.12345", "Diffusion Foo", "We propose foo."),
            _paper("2401.67890", "Flow Bar", "We propose bar."),
        ]
    })
    fetcher = HFPapersFetcher(transport=transport)

    items = fetcher.fetch(SourceQuery(), since=DAY_1, limit=50)

    assert len(items) == 2
    first = items[0]
    assert first.external_id == "2401.12345"
    assert first.title == "Diffusion Foo"
    assert first.source_key == "hf_papers"
    assert first.group == "papers"
    assert first.authors == ["A. Researcher"]
    assert first.url == "https://huggingface.co/papers/2401.12345"


def test_dedup_key_matches_arxiv(monkeypatch):
    """HF paper.id 是 arxiv id → dedup_key 对齐 arxiv:<id>，可跨源去重。"""
    _freeze_today(monkeypatch, DAY_1)
    transport = _make_transport({
        "2026-04-20": [_paper("2401.12345", "X")]
    })
    fetcher = HFPapersFetcher(transport=transport)

    items = fetcher.fetch(SourceQuery(), since=DAY_1, limit=10)

    assert items[0].dedup_key == "arxiv:2401.12345"


def test_non_arxiv_id_fallback_dedup(monkeypatch):
    _freeze_today(monkeypatch, DAY_1)
    transport = _make_transport({
        "2026-04-20": [_paper("custom-slug-xyz", "X")]
    })
    fetcher = HFPapersFetcher(transport=transport)

    items = fetcher.fetch(SourceQuery(), since=DAY_1, limit=10)

    assert items[0].dedup_key == "hf_papers:custom-slug-xyz"


def test_keyword_filter(monkeypatch):
    _freeze_today(monkeypatch, DAY_1)
    transport = _make_transport({
        "2026-04-20": [
            _paper("2401.00001", "Diffusion model for vision"),
            _paper("2401.00002", "Unrelated NLP benchmark"),
            _paper("2401.00003", "Flow matching for audio", "generative flow model"),
        ]
    })
    fetcher = HFPapersFetcher(transport=transport)

    items = fetcher.fetch(
        SourceQuery(hf_keywords=["diffusion", "flow matching"]),
        since=DAY_1,
        limit=50,
    )

    titles = [it.title for it in items]
    assert "Diffusion model for vision" in titles
    assert "Flow matching for audio" in titles
    assert "Unrelated NLP benchmark" not in titles


def test_empty_keywords_passthrough(monkeypatch):
    _freeze_today(monkeypatch, DAY_1)
    transport = _make_transport({
        "2026-04-20": [
            _paper("2401.00001", "A"),
            _paper("2401.00002", "B"),
        ]
    })
    fetcher = HFPapersFetcher(transport=transport)
    items = fetcher.fetch(SourceQuery(), since=DAY_1, limit=50)
    assert len(items) == 2


def test_multi_day_merge(monkeypatch):
    _freeze_today(monkeypatch, DAY_2)
    transport = _make_transport({
        "2026-04-20": [_paper("2401.00001", "Day1")],
        "2026-04-21": [_paper("2401.00002", "Day2")],
    })
    fetcher = HFPapersFetcher(transport=transport)

    items = fetcher.fetch(SourceQuery(), since=DAY_1, limit=50)

    ids = sorted(it.external_id for it in items)
    assert ids == ["2401.00001", "2401.00002"]


def test_limit_respected(monkeypatch):
    _freeze_today(monkeypatch, DAY_1)
    transport = _make_transport({
        "2026-04-20": [_paper(f"2401.0000{i}", f"T{i}") for i in range(5)]
    })
    fetcher = HFPapersFetcher(transport=transport)
    items = fetcher.fetch(SourceQuery(), since=DAY_1, limit=3)
    assert len(items) == 3


def test_http_failure_returns_empty(monkeypatch):
    _freeze_today(monkeypatch, DAY_1)
    transport = _make_transport({
        "2026-04-20": httpx.ConnectError("boom"),
    })
    fetcher = HFPapersFetcher(transport=transport)

    items = fetcher.fetch(SourceQuery(), since=DAY_1, limit=10)
    assert items == []


def test_single_day_failure_does_not_break_other_days(monkeypatch):
    _freeze_today(monkeypatch, DAY_2)
    transport = _make_transport({
        "2026-04-20": httpx.ConnectError("boom"),
        "2026-04-21": [_paper("2401.00002", "Day2 survives")],
    })
    fetcher = HFPapersFetcher(transport=transport)

    items = fetcher.fetch(SourceQuery(), since=DAY_1, limit=10)

    assert [it.external_id for it in items] == ["2401.00002"]


def test_cross_day_dedup(monkeypatch):
    """同一篇 paper 在两天都出现 → 只保留一次。"""
    _freeze_today(monkeypatch, DAY_2)
    transport = _make_transport({
        "2026-04-20": [_paper("2401.00001", "Same")],
        "2026-04-21": [_paper("2401.00001", "Same")],
    })
    fetcher = HFPapersFetcher(transport=transport)

    items = fetcher.fetch(SourceQuery(), since=DAY_1, limit=10)
    assert len(items) == 1


def test_since_in_future_returns_empty(monkeypatch):
    _freeze_today(monkeypatch, DAY_1)
    transport = _make_transport({})
    fetcher = HFPapersFetcher(transport=transport)

    future = DAY_1 + timedelta(days=5)
    items = fetcher.fetch(SourceQuery(), since=future, limit=10)
    assert items == []
