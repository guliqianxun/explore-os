"""ft-020: catalog 测试 —— 真写 extract_* 行，断言 build_catalog 输出 + allowed."""
from __future__ import annotations

import pytest

from apps.extract.models import Equation, Figure, Section, Table
from apps.interpret.catalog import build_catalog, resolve_short_to_full


pytestmark = pytest.mark.django_db


def _seed(arxiv_id: str = "2401.99001"):
    Section.objects.create(
        material_id=f"{arxiv_id}:section:1",
        paper_arxiv_id=arxiv_id, seq=1, path="Abstract", level=1,
    )
    Section.objects.create(
        material_id=f"{arxiv_id}:section:2",
        paper_arxiv_id=arxiv_id, seq=2, path="3 Method", level=1,
    )
    # noise demoted section（level=2）→ 不应出现在 catalog
    Section.objects.create(
        material_id=f"{arxiv_id}:section:3",
        paper_arxiv_id=arxiv_id, seq=3, path="Algorithm 1", level=2,
    )
    Figure.objects.create(
        material_id=f"{arxiv_id}:figure:1",
        paper_arxiv_id=arxiv_id, seq=1, page=2,
        caption="Figure 1: A demo.",
    )
    Table.objects.create(
        material_id=f"{arxiv_id}:table:1",
        paper_arxiv_id=arxiv_id, seq=1, page=4,
        caption="Table 1: Metrics.",
    )
    Equation.objects.create(
        material_id=f"{arxiv_id}:equation:1",
        paper_arxiv_id=arxiv_id, seq=1, page=3,
        latex_or_text=r"\mathcal{L} = ...",
    )
    return arxiv_id


def test_build_catalog_basic_output():
    arxiv_id = _seed()
    text, allowed = build_catalog(arxiv_id)

    assert "[§:1] Abstract" in text
    assert "[§:2] 3 Method" in text
    assert "Algorithm 1" not in text  # level=2 noise excluded
    assert "[fig:1] p2 Figure 1: A demo." in text
    assert "[tbl:1] p4 Table 1: Metrics." in text
    assert "[eq:1] " in text

    assert allowed == {
        f"{arxiv_id}:section:1",
        f"{arxiv_id}:section:2",
        f"{arxiv_id}:figure:1",
        f"{arxiv_id}:table:1",
        f"{arxiv_id}:equation:1",
    }


def test_build_catalog_empty_paper():
    text, allowed = build_catalog("nonexistent.000")
    assert text == ""
    assert allowed == set()


def test_build_catalog_isolates_by_arxiv():
    _seed("2401.99001")
    _seed("2401.99002")
    _, allowed_a = build_catalog("2401.99001")
    _, allowed_b = build_catalog("2401.99002")
    assert all(m.startswith("2401.99001:") for m in allowed_a)
    assert all(m.startswith("2401.99002:") for m in allowed_b)


def test_resolve_short_to_full_each_kind():
    a = "2401.00001"
    assert resolve_short_to_full("[fig:1]", a) == f"{a}:figure:1"
    assert resolve_short_to_full("fig:1", a) == f"{a}:figure:1"
    assert resolve_short_to_full("[§:3]", a) == f"{a}:section:3"
    assert resolve_short_to_full("[tbl:5]", a) == f"{a}:table:5"
    assert resolve_short_to_full("[eq:2]", a) == f"{a}:equation:2"


def test_resolve_short_to_full_passthrough_full_form():
    a = "2401.00001"
    assert resolve_short_to_full(f"{a}:figure:1", a) == f"{a}:figure:1"


def test_resolve_short_to_full_invalid():
    a = "2401.00001"
    assert resolve_short_to_full("", a) is None
    assert resolve_short_to_full("garbage", a) is None
    assert resolve_short_to_full("[xyz:1]", a) is None
