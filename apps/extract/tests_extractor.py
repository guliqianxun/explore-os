"""ft-019 端到端：抽取入口 + 持久化幂等性 (用 mock 子抽取器，避免依赖真实 PDF)."""
from __future__ import annotations

import pytest

from apps.extract import extractor as ex
from apps.extract.base import ExtractResult, make_material_id
from apps.extract.caption_extractor import Caption
from apps.extract.citation_extractor import Citation as RawCitation
from apps.extract.equation_extractor import Equation as RawEquation
from apps.extract.figure_extractor import Figure as RawFigure
from apps.extract.section_extractor import PaperChunks, Section


@pytest.fixture
def patched_subextractors(monkeypatch, tmp_path):
    """把五个子抽取器替换成确定性 stub，arxiv_id=2401.00001."""
    arxiv = "2401.00001"
    pdf = tmp_path / f"{arxiv}.pdf"
    pdf.write_bytes(b"dummy")

    monkeypatch.setattr(ex, "chunk_pdf", lambda a, p: PaperChunks(
        arxiv_id=a,
        sections=[
            Section("intro", "1 Introduction", "intro body"),
            Section("method", "2 Method", "method body"),
        ],
    ))
    monkeypatch.setattr(ex, "extract_captions", lambda a, p: [
        Caption(arxiv_id=a, kind="figure", number=1,
                text="Figure 1: caption", page=2,
                bbox_caption=(0, 0, 1, 1), bbox_image=(0, 0, 1, 1)),
        Caption(arxiv_id=a, kind="table", number=1,
                text="Table 1: caption", page=3,
                bbox_caption=(0, 0, 1, 1), bbox_image=(0, 0, 1, 1)),
    ])
    monkeypatch.setattr(ex, "extract_figures", lambda a, p: [
        RawFigure(arxiv_id=a, page=2, index=0, path="p02_i00.png", caption="cap"),
    ])
    monkeypatch.setattr(ex, "extract_equations", lambda a, p: [
        RawEquation(arxiv_id=a, page=4, eq_label="1",
                    bbox=(0, 0, 1, 1), text="y = Wx + b (1)"),
    ])
    monkeypatch.setattr(ex, "extract_citations", lambda a, p: [
        RawCitation(arxiv_id=a, bibkey="smith2020",
                    raw_text="Smith 2020. A paper.", title="A paper", year=2020),
    ])
    monkeypatch.setattr(ex, "figures_root", lambda: tmp_path / "figures")
    return arxiv, pdf


def test_extract_returns_five_categories(patched_subextractors):
    arxiv, pdf = patched_subextractors
    result = ex.extract(pdf, arxiv)
    assert isinstance(result, ExtractResult)
    assert len(result.sections) == 2
    assert len(result.figures) == 1
    assert len(result.tables) == 1
    assert len(result.equations) == 1
    assert len(result.citations) == 1


def test_material_ids_follow_format(patched_subextractors):
    arxiv, pdf = patched_subextractors
    result = ex.extract(pdf, arxiv)
    assert result.sections[0].material_id == make_material_id(arxiv, "section", 1)
    assert result.figures[0].material_id == make_material_id(arxiv, "figure", 1)
    assert result.tables[0].material_id == make_material_id(arxiv, "table", 1)
    assert result.equations[0].material_id == make_material_id(arxiv, "equation", 1)
    assert result.citations[0].material_id == make_material_id(arxiv, "citation", 1)


@pytest.mark.django_db
def test_persist_result_idempotent(patched_subextractors):
    """同一 paper 重复 extract+persist 不增行数."""
    from apps.extract.models import Citation, Equation, Figure, Section, Table

    arxiv, pdf = patched_subextractors
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


def test_default_extractor_protocol(patched_subextractors):
    arxiv, pdf = patched_subextractors
    result = ex.DefaultExtractor().extract(pdf, arxiv)
    assert len(result.sections) == 2
