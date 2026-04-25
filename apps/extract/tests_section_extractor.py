"""Tests for ft-019 section_extractor (搬迁自 interpret/pdf_chunker)."""
from __future__ import annotations

from apps.extract import section_extractor as se
from apps.extract.section_extractor import (
    BUCKET_CHAR_CAP,
    PaperChunks,
    _classify_bucket,
    _split_by_heading,
    chunk_pdf,
)


def test_classify_bucket_keyword_match():
    assert _classify_bucket("Introduction") == "intro"
    assert _classify_bucket("3.2 Method Details") == "method"
    assert _classify_bucket("4 Experiments") == "experiments"
    assert _classify_bucket("5. Conclusion") == "conclusion"
    assert _classify_bucket("References") == "other"


def test_split_by_heading_assigns_buckets():
    md = "# 1 Introduction\nIntro body.\n# 2 Method\nMethod body.\n# 3 Experiments\nExp body.\n"
    sections = _split_by_heading(md)
    buckets = [s.bucket for s in sections]
    assert "intro" in buckets
    assert "method" in buckets
    assert "experiments" in buckets


def test_char_cap_enforced():
    md = f"# 2 Method\n{'word ' * 5000}\n"
    sections = _split_by_heading(md)
    total = sum(len(s.text) for s in sections if s.bucket == "method")
    assert total <= BUCKET_CHAR_CAP["method"] + 20


def test_paper_chunks_by_bucket():
    chunks = PaperChunks(
        arxiv_id="x",
        sections=[
            se.Section("method", "t1", "a"),
            se.Section("method", "t2", "b"),
            se.Section("experiments", "t3", "c"),
        ],
    )
    assert "a" in chunks.by_bucket("method")
    assert chunks.by_bucket("intro") == ""


def test_chunk_pdf_uses_cache(tmp_path, monkeypatch):
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"dummy")
    called = {"n": 0}

    def fake_parse(_p):
        called["n"] += 1
        return "# Method\nbody"

    monkeypatch.setattr(se, "_parse_to_markdown", fake_parse)
    first = chunk_pdf("x", pdf, cache_dir=tmp_path)
    second = chunk_pdf("x", pdf, cache_dir=tmp_path)
    assert first is not None and second is not None
    assert called["n"] == 1


def test_chunk_pdf_missing_file_returns_none(tmp_path):
    assert chunk_pdf("x", tmp_path / "nope.pdf") is None
