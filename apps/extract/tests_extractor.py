"""ft-019 + ft-015 端到端：抽取入口 + 持久化幂等性。

DoclingExtractor 整体 mock —— 不真跑 docling，只验证：
  - DefaultExtractor 委托链
  - persist_result 落库幂等
"""
from __future__ import annotations

import pytest

from apps.extract import extractor as ex
from apps.extract.base import (
    CitationMaterial,
    EquationMaterial,
    ExtractResult,
    FigureMaterial,
    SectionMaterial,
    TableMaterial,
    make_material_id,
)


def _stub_result(arxiv: str) -> ExtractResult:
    return ExtractResult(
        sections=[
            SectionMaterial(
                material_id=make_material_id(arxiv, "section", 1),
                paper_arxiv_id=arxiv, type="section",
                path="1 Introduction", level=1, raw_text="",
            ),
            SectionMaterial(
                material_id=make_material_id(arxiv, "section", 2),
                paper_arxiv_id=arxiv, type="section",
                path="2 Method", level=1, raw_text="",
            ),
        ],
        figures=[
            FigureMaterial(
                material_id=make_material_id(arxiv, "figure", 1),
                paper_arxiv_id=arxiv, type="figure",
                fig_label="Figure 1", page=2, bbox=[0.0, 0.0, 1.0, 1.0],
                caption="Figure 1: caption", image_path="/tmp/fake.png",
            ),
        ],
        tables=[
            TableMaterial(
                material_id=make_material_id(arxiv, "table", 1),
                paper_arxiv_id=arxiv, type="table",
                tbl_label="Table 1", page=3, bbox=[0.0, 0.0, 1.0, 1.0],
                caption="Table 1: caption", raw_text="| a | b |",
            ),
        ],
        equations=[
            EquationMaterial(
                material_id=make_material_id(arxiv, "equation", 1),
                paper_arxiv_id=arxiv, type="equation",
                eq_label=None, page=4, bbox=[0.0, 0.0, 1.0, 1.0],
                latex_or_text=r"y = Wx + b", inline_or_display="display",
            ),
        ],
        citations=[
            CitationMaterial(
                material_id=make_material_id(arxiv, "citation", 1),
                paper_arxiv_id=arxiv, type="citation",
                bibkey="smith2020", raw_text="Smith 2020. A paper.",
                title="A paper", year=2020,
            ),
        ],
    )


@pytest.fixture
def patched_extractor(monkeypatch, tmp_path):
    """整体 mock DoclingExtractor.extract."""
    arxiv = "2401.00001"
    pdf = tmp_path / f"{arxiv}.pdf"
    pdf.write_bytes(b"dummy")

    monkeypatch.setattr(
        "apps.extract.extractor.DoclingExtractor.extract",
        lambda self, p, a: _stub_result(a),
    )
    return arxiv, pdf


def test_extract_returns_five_categories(patched_extractor):
    arxiv, pdf = patched_extractor
    result = ex.extract(pdf, arxiv)
    assert isinstance(result, ExtractResult)
    assert len(result.sections) == 2
    assert len(result.figures) == 1
    assert len(result.tables) == 1
    assert len(result.equations) == 1
    assert len(result.citations) == 1


def test_material_ids_follow_format(patched_extractor):
    arxiv, pdf = patched_extractor
    result = ex.extract(pdf, arxiv)
    assert result.sections[0].material_id == make_material_id(arxiv, "section", 1)
    assert result.figures[0].material_id == make_material_id(arxiv, "figure", 1)
    assert result.tables[0].material_id == make_material_id(arxiv, "table", 1)
    assert result.equations[0].material_id == make_material_id(arxiv, "equation", 1)
    assert result.citations[0].material_id == make_material_id(arxiv, "citation", 1)


@pytest.mark.django_db
def test_persist_result_idempotent(patched_extractor):
    """同一 paper 重复 extract+persist 不增行数."""
    from apps.extract.models import Citation, Equation, Figure, Section, Table

    arxiv, pdf = patched_extractor
    result = ex.extract(pdf, arxiv)
    counts1 = ex.persist_result(result)
    assert counts1["sections"] == 2

    rows_after_first = (
        Section.objects.count() + Figure.objects.count() + Table.objects.count()
        + Equation.objects.count() + Citation.objects.count()
    )

    # 再跑一次
    result2 = ex.extract(pdf, arxiv)
    ex.persist_result(result2)
    rows_after_second = (
        Section.objects.count() + Figure.objects.count() + Table.objects.count()
        + Equation.objects.count() + Citation.objects.count()
    )
    assert rows_after_first == rows_after_second
    # material_id 稳定（取一条断言）
    assert Section.objects.filter(
        material_id=make_material_id(arxiv, "section", 1)
    ).exists()


def test_default_extractor_protocol(patched_extractor):
    arxiv, pdf = patched_extractor
    result = ex.DefaultExtractor().extract(pdf, arxiv)
    assert len(result.sections) == 2
