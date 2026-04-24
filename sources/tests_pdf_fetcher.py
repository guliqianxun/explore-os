"""Tests for ft-011 PDF fetcher."""
from __future__ import annotations

import httpx
import pytest

from sources import pdf_fetcher
from sources.base import Item


def _item(dedup_key="arxiv:2401.12345") -> Item:
    return Item(
        external_id="x", title="t", abstract="a", url="u",
        source_key="arxiv", group="papers", dedup_key=dedup_key,
    )


@pytest.fixture
def fake_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(pdf_fetcher, "cache_root", lambda: tmp_path)
    yield tmp_path


def _patch_stream(monkeypatch, payload: bytes, status: int = 200):
    class _Resp:
        status_code = status

        def __init__(self):
            self._payload = payload

        def raise_for_status(self):
            if status >= 400:
                raise httpx.HTTPStatusError("fail", request=None, response=None)

        def iter_bytes(self, chunk_size=65536):
            buf = self._payload
            for i in range(0, len(buf), chunk_size):
                yield buf[i:i + chunk_size]

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    def fake_stream(method, url, **kwargs):
        return _Resp()

    monkeypatch.setattr(pdf_fetcher.httpx, "stream", fake_stream)


# ---------------- tests ----------------

def test_arxiv_id_extraction():
    assert pdf_fetcher.arxiv_id_of(_item("arxiv:2401.12345")) == "2401.12345"
    assert pdf_fetcher.arxiv_id_of(_item("doi:10.xxx")) is None
    assert pdf_fetcher.arxiv_id_of(_item("")) is None


def test_fetch_downloads_and_caches(fake_cache, monkeypatch):
    _patch_stream(monkeypatch, b"PDFDATA" * 100)
    path = pdf_fetcher.fetch_pdf(_item())
    assert path is not None
    assert path.exists()
    assert path.read_bytes() == b"PDFDATA" * 100


def test_fetch_skips_non_arxiv(fake_cache, monkeypatch):
    # Even if stream is wired, non-arxiv item should return None before HTTP
    def boom(*a, **k):
        raise AssertionError("should not call stream")

    monkeypatch.setattr(pdf_fetcher.httpx, "stream", boom)
    assert pdf_fetcher.fetch_pdf(_item("hf_papers:custom-slug")) is None


def test_fetch_hits_cache_on_second_call(fake_cache, monkeypatch):
    call_count = {"n": 0}

    def counting_stream(method, url, **kwargs):
        call_count["n"] += 1
        return _mock_resp(b"PDF")

    class _MockResp:
        def __init__(self, data):
            self._data = data

        def raise_for_status(self):
            pass

        def iter_bytes(self, chunk_size=65536):
            yield self._data

        def __enter__(self): return self
        def __exit__(self, *a): pass

    def _mock_resp(data):
        return _MockResp(data)

    monkeypatch.setattr(pdf_fetcher.httpx, "stream", counting_stream)

    p1 = pdf_fetcher.fetch_pdf(_item())
    p2 = pdf_fetcher.fetch_pdf(_item())
    assert p1 == p2
    assert call_count["n"] == 1


def test_fetch_size_cap(fake_cache, monkeypatch):
    # 33MB exceeds 30MB cap
    big = b"\x00" * (33 * 1024 * 1024)
    _patch_stream(monkeypatch, big)
    path = pdf_fetcher.fetch_pdf(_item())
    assert path is None
    # tmp file should not remain
    partial = pdf_fetcher.local_pdf_path("2401.12345").with_suffix(".pdf.part")
    assert not partial.exists()


def test_fetch_http_error_returns_none(fake_cache, monkeypatch):
    def raiser(*a, **k):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(pdf_fetcher.httpx, "stream", raiser)
    assert pdf_fetcher.fetch_pdf(_item()) is None
