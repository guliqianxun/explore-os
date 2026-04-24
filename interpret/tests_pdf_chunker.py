"""Tests for ft-011 PDF chunker."""
from __future__ import annotations

import pytest

from interpret import pdf_chunker
from interpret.pdf_chunker import (
    BUCKET_CHAR_CAP,
    PaperChunks,
    _classify_bucket,
    _split_by_heading,
    chunk_pdf,
)


def test_classify_bucket_keyword_match():
    assert _classify_bucket("Introduction") == "intro"
    assert _classify_bucket("1. Introduction") == "intro"
    assert _classify_bucket("3.2 Method Details") == "method"
    assert _classify_bucket("Architecture Overview") == "method"
    assert _classify_bucket("4 Experiments") == "experiments"
    assert _classify_bucket("Ablation Study") == "experiments"
    assert _classify_bucket("5. Conclusion") == "conclusion"
    assert _classify_bucket("Limitations") == "conclusion"
    assert _classify_bucket("Appendix A") == "other"
    assert _classify_bucket("References") == "other"


def test_split_by_heading_assigns_buckets():
    md = """# 1 Introduction
This paper studies X.

# 2 Method
We propose a new model.

## 2.1 Architecture
Details here.

# 3 Experiments
We evaluate on Y.

# 4 Conclusion
Works well.

# References
[1] ..."""
    sections = _split_by_heading(md)
    buckets = [s.bucket for s in sections]
    assert "intro" in buckets
    assert buckets.count("method") >= 1
    assert "experiments" in buckets
    assert "conclusion" in buckets
    # References 被丢弃（other 的 cap=0）
    assert "other" not in buckets


def test_char_cap_enforced():
    long_text = "word " * 5000  # 25000 chars
    md = f"# 2 Method\n{long_text}\n"
    sections = _split_by_heading(md)
    total = sum(len(s.text) for s in sections if s.bucket == "method")
    assert total <= BUCKET_CHAR_CAP["method"] + 20  # 允许少量尾部余量


def test_paper_chunks_by_bucket():
    chunks = PaperChunks(
        arxiv_id="x",
        sections=[
            pdf_chunker.Section("method", "t1", "a"),
            pdf_chunker.Section("method", "t2", "b"),
            pdf_chunker.Section("experiments", "t3", "c"),
        ],
    )
    assert "a" in chunks.by_bucket("method")
    assert "b" in chunks.by_bucket("method")
    assert chunks.by_bucket("experiments") == "c"
    assert chunks.by_bucket("intro") == ""


def test_chunk_pdf_uses_cache(tmp_path, monkeypatch):
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"dummy")

    called = {"n": 0}

    def fake_parse(_path):
        called["n"] += 1
        return "# Method\nbody"

    monkeypatch.setattr(pdf_chunker, "_parse_to_markdown", fake_parse)

    first = chunk_pdf("x", pdf, cache_dir=tmp_path)
    second = chunk_pdf("x", pdf, cache_dir=tmp_path)
    assert first is not None and second is not None
    assert called["n"] == 1
    assert (tmp_path / "x.chunks.json").exists()


def test_chunk_pdf_missing_file_returns_none(tmp_path):
    missing = tmp_path / "nope.pdf"
    assert chunk_pdf("x", missing) is None


def test_chunk_pdf_parse_failure_returns_none(tmp_path, monkeypatch):
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"dummy")
    monkeypatch.setattr(pdf_chunker, "_parse_to_markdown", lambda _p: "")
    assert chunk_pdf("x", pdf, cache_dir=tmp_path) is None
