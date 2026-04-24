"""Tests for embedding client."""
from __future__ import annotations

import json

import httpx
import pytest

from interpret import embedding
from interpret.embedding import EmbeddingError, cosine, embed


def _mock_transport(per_call_vectors):
    """per_call_vectors: list of list[list[float]] — one item per HTTP call."""
    calls = {"i": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        inputs = payload["input"]
        idx = calls["i"]
        calls["i"] += 1
        vectors = per_call_vectors[idx]
        assert len(vectors) == len(inputs), "mock mismatch"
        data = {
            "data": [
                {"index": i, "embedding": v} for i, v in enumerate(vectors)
            ],
            "usage": {"total_tokens": sum(len(s) for s in inputs)},
        }
        return httpx.Response(200, content=json.dumps(data).encode("utf-8"))

    return httpx.MockTransport(handler), calls


@pytest.fixture
def configured(monkeypatch, settings):
    settings.LLM_API_KEY = "sk-test"
    settings.LLM_API_BASE = "https://example.test/v1"
    yield


def _patch_client(monkeypatch, transport):
    orig = httpx.Client

    def factory(*args, **kwargs):
        kwargs["transport"] = transport
        return orig(*args, **kwargs)

    monkeypatch.setattr(embedding.httpx, "Client", factory)


def test_single_batch(configured, monkeypatch):
    transport, calls = _mock_transport([[[1.0, 0.0], [0.0, 1.0]]])
    _patch_client(monkeypatch, transport)
    res = embed(["hello", "world"])
    assert res.vectors == [[1.0, 0.0], [0.0, 1.0]]
    assert calls["i"] == 1
    assert res.usage.get("total_tokens") == len("hello") + len("world")


def test_multi_batch_auto_split(configured, monkeypatch):
    big = [f"t{i}" for i in range(60)]
    transport, calls = _mock_transport([
        [[float(i), 0.0] for i in range(0, 25)],
        [[float(i), 0.0] for i in range(25, 50)],
        [[float(i), 0.0] for i in range(50, 60)],
    ])
    _patch_client(monkeypatch, transport)
    res = embed(big)
    assert len(res.vectors) == 60
    assert calls["i"] == 3
    assert res.vectors[0] == [0.0, 0.0]
    assert res.vectors[59] == [59.0, 0.0]


def test_empty_input(configured):
    res = embed([])
    assert res.vectors == []


def test_missing_api_key(monkeypatch, settings):
    settings.LLM_API_KEY = ""
    with pytest.raises(EmbeddingError):
        embed(["x"])


def test_cosine():
    assert cosine([1, 0], [1, 0]) == pytest.approx(1.0)
    assert cosine([1, 0], [0, 1]) == pytest.approx(0.0)
    assert cosine([1, 0], [-1, 0]) == pytest.approx(-1.0)
    assert cosine([], [1, 0]) == 0.0
    assert cosine([0, 0], [1, 0]) == 0.0
