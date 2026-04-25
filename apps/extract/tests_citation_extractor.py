"""Tests for ft-019 citation_extractor."""
from __future__ import annotations

from apps.extract.citation_extractor import (
    _parse_entry,
    _slice_references,
    _split_entries,
    extract_citations,
)


def test_slice_references_takes_last_match():
    text = "Body talks about References briefly.\nMore body.\n\nReferences\n[1] foo bar 2020.\n"
    sliced = _slice_references(text)
    assert sliced.startswith("[1]")


def test_slice_references_returns_empty_when_missing():
    assert _slice_references("just body, no refs section") == ""


def test_split_entries_numbered():
    block = "[1] Smith 2020. Title one.\n[2] Doe 2021. Title two.\n"
    entries = _split_entries(block)
    assert len(entries) == 2
    assert entries[0].startswith("Smith")
    assert entries[1].startswith("Doe")


def test_parse_entry_extracts_year_and_bibkey():
    raw = "Smith, J. 2020. A novel approach to X. ICML."
    cit = _parse_entry("2401.00001", raw)
    assert cit is not None
    assert cit.year == 2020
    assert cit.bibkey.startswith("smith")
    assert "2020" in cit.bibkey
    assert "novel approach" in cit.title.lower()


def test_parse_entry_no_year():
    raw = "Anonymous. Untitled draft. n.d."
    cit = _parse_entry("x", raw)
    assert cit is not None
    assert cit.year is None
    assert "n.d" in cit.bibkey


def test_extract_citations_missing_pdf(tmp_path):
    assert extract_citations("x", tmp_path / "no.pdf") == []
