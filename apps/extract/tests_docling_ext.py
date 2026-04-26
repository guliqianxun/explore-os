"""ft-015: DoclingExtractor 单测 —— 全 mock，绝不真跑 docling.

构造 fake DoclingDocument（types.SimpleNamespace），patch 模块级 `_convert`
返回它，断言 5 类 material 映射规则。
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from apps.extract.base import (
    CitationMaterial,
    EquationMaterial,
    ExtractResult,
    FigureMaterial,
    SectionMaterial,
    TableMaterial,
)
from apps.extract.extractors import docling_ext as dx
from apps.extract.extractors.docling_ext import DoclingExtractor


# ---------------- fake doc fixture ----------------

class _FakeImage:
    """伪造 PIL.Image：仅实现 save()。"""

    def __init__(self) -> None:
        self.saved_to: str | None = None

    def save(self, path) -> None:  # noqa: D401
        self.saved_to = str(path)
        # 真写一个 1-byte 文件，模拟落盘
        Path(path).write_bytes(b"\x89")


def _bbox(left=10.0, top=400.0, right=300.0, bottom=20.0):  # docling BOTTOMLEFT 坐标系
    return SimpleNamespace(l=left, t=top, r=right, b=bottom)


def _prov(page_no=1, **bbox_kwargs):
    return [SimpleNamespace(page_no=page_no, bbox=_bbox(**bbox_kwargs))]


def make_fake_doc(*, picture_image=True, table_md_signature: str = "with_doc"):
    """构造覆盖 5 类 material 的 fake DoclingDocument。

    table_md_signature: "with_doc" → export_to_markdown(doc) 兼容；"no_doc" →
                       仅 export_to_markdown() 兼容（测 try/except fallback）
    """
    abstract = SimpleNamespace(
        label="section_header", text="Abstract", level=1, prov=_prov(1),
    )
    section = SimpleNamespace(
        label="section_header", text="3 Method", level=1, prov=_prov(2),
    )
    formula = SimpleNamespace(
        label="formula",
        text=r"\mathcal{L} = \|x - y\|^2",
        prov=_prov(3),
    )
    refs_header = SimpleNamespace(
        label="section_header", text="References", level=1, prov=_prov(8),
    )
    cite1 = SimpleNamespace(
        label="list_item",
        text="Smith, J. 2024. Foo bar baz. NeurIPS.",
        prov=_prov(8),
    )
    cite2 = SimpleNamespace(
        label="list_item",
        text="Doe, A. 2023. Another paper. ICLR.",
        prov=_prov(8),
    )
    # picture
    cap_text = SimpleNamespace(text="Figure 1: A test figure showing X.")
    cap_ref = SimpleNamespace(resolve=lambda doc: cap_text)
    fake_img = _FakeImage() if picture_image else None
    pic = SimpleNamespace(
        prov=_prov(2),
        captions=[cap_ref],
        get_image=lambda doc: fake_img,
    )
    # table
    tbl_cap = SimpleNamespace(text="Table 1: Quantitative metrics.")
    tbl_cap_ref = SimpleNamespace(resolve=lambda doc: tbl_cap)
    if table_md_signature == "with_doc":
        def _md(doc):  # noqa: ARG001
            return "| a | b |\n|---|---|\n| 1 | 2 |"
    else:
        def _md():
            return "| a | b |\n|---|---|\n| 1 | 2 |"
    tbl = SimpleNamespace(
        prov=_prov(4),
        captions=[tbl_cap_ref],
        export_to_markdown=_md,
    )
    return SimpleNamespace(
        texts=[abstract, section, formula, refs_header, cite1, cite2],
        pictures=[pic],
        tables=[tbl],
    )


@pytest.fixture(autouse=True)
def _clear_doc_cache():
    """每个测试前清缓存，避免 paper_id 串扰。"""
    dx._DOC_CACHE.clear()
    yield
    dx._DOC_CACHE.clear()


# ---------------- tests ----------------

def test_extract_returns_five_categories(tmp_path, settings):
    settings.BASE_DIR = tmp_path
    fake_doc = make_fake_doc()
    pdf = tmp_path / "fake.pdf"
    pdf.write_bytes(b"dummy")
    with patch.object(dx, "_convert", return_value=fake_doc):
        result = DoclingExtractor().extract(pdf, "2401.00001")

    assert isinstance(result, ExtractResult)
    assert len(result.sections) == 3   # Abstract + 3 Method + References
    assert len(result.figures) == 1
    assert len(result.tables) == 1
    assert len(result.equations) == 1
    assert len(result.citations) == 2


def test_section_mapping(tmp_path, settings):
    settings.BASE_DIR = tmp_path
    fake_doc = make_fake_doc()
    pdf = tmp_path / "fake.pdf"
    pdf.write_bytes(b"")
    with patch.object(dx, "_convert", return_value=fake_doc):
        result = DoclingExtractor().extract(pdf, "2401.00001")

    s = result.sections[1]
    assert isinstance(s, SectionMaterial)
    assert s.material_id == "2401.00001:section:2"
    assert s.path == "3 Method"
    assert s.level == 1
    assert s.raw_text == ""
    assert s.raw_payload.get("parser") == "docling"


def test_figure_mapping_writes_image(tmp_path, settings):
    settings.BASE_DIR = tmp_path
    fake_doc = make_fake_doc()
    pdf = tmp_path / "fake.pdf"
    pdf.write_bytes(b"")
    with patch.object(dx, "_convert", return_value=fake_doc):
        result = DoclingExtractor().extract(pdf, "2401.00001")

    f = result.figures[0]
    assert isinstance(f, FigureMaterial)
    assert f.material_id == "2401.00001:figure:1"
    assert f.fig_label == "Figure 1"
    assert f.caption.startswith("Figure 1:")
    assert f.page == 2
    assert f.bbox is not None and len(f.bbox) == 4
    assert f.image_path
    assert Path(f.image_path).exists()
    # 落在 media/figures/<arxiv_id>/ 下
    assert "2401.00001" in f.image_path


def test_figure_skipped_when_no_image(tmp_path, settings):
    settings.BASE_DIR = tmp_path
    fake_doc = make_fake_doc(picture_image=False)
    pdf = tmp_path / "fake.pdf"
    pdf.write_bytes(b"")
    with patch.object(dx, "_convert", return_value=fake_doc):
        result = DoclingExtractor().extract(pdf, "2401.00001")
    assert result.figures == []


def test_table_mapping_with_doc_arg(tmp_path, settings):
    settings.BASE_DIR = tmp_path
    fake_doc = make_fake_doc(table_md_signature="with_doc")
    pdf = tmp_path / "fake.pdf"
    pdf.write_bytes(b"")
    with patch.object(dx, "_convert", return_value=fake_doc):
        result = DoclingExtractor().extract(pdf, "2401.00001")

    t = result.tables[0]
    assert isinstance(t, TableMaterial)
    assert t.material_id == "2401.00001:table:1"
    assert t.tbl_label == "Table 1"
    assert "| a | b |" in t.raw_text
    assert t.page == 4


def test_table_mapping_without_doc_arg(tmp_path, settings):
    """API 兼容：旧版 export_to_markdown() 无参也能跑。"""
    settings.BASE_DIR = tmp_path
    fake_doc = make_fake_doc(table_md_signature="no_doc")
    pdf = tmp_path / "fake.pdf"
    pdf.write_bytes(b"")
    with patch.object(dx, "_convert", return_value=fake_doc):
        result = DoclingExtractor().extract(pdf, "2401.00001")
    assert "| a | b |" in result.tables[0].raw_text


def test_equation_mapping(tmp_path, settings):
    settings.BASE_DIR = tmp_path
    fake_doc = make_fake_doc()
    pdf = tmp_path / "fake.pdf"
    pdf.write_bytes(b"")
    with patch.object(dx, "_convert", return_value=fake_doc):
        result = DoclingExtractor().extract(pdf, "2401.00001")

    eq = result.equations[0]
    assert isinstance(eq, EquationMaterial)
    assert eq.material_id == "2401.00001:equation:1"
    assert eq.latex_or_text == r"\mathcal{L} = \|x - y\|^2"
    assert eq.inline_or_display == "display"
    assert eq.page == 3


def test_citation_mapping_only_after_references(tmp_path, settings):
    settings.BASE_DIR = tmp_path
    fake_doc = make_fake_doc()
    pdf = tmp_path / "fake.pdf"
    pdf.write_bytes(b"")
    with patch.object(dx, "_convert", return_value=fake_doc):
        result = DoclingExtractor().extract(pdf, "2401.00001")

    assert len(result.citations) == 2
    c0 = result.citations[0]
    assert isinstance(c0, CitationMaterial)
    assert c0.material_id == "2401.00001:citation:1"
    assert c0.year == 2024
    assert c0.bibkey.startswith("smith")
    assert "Smith" in c0.raw_text
    assert result.citations[1].year == 2023


def test_citations_stop_at_next_section_header(tmp_path, settings):
    """References 之后再来一个 section_header 应停止收集 list_item。"""
    settings.BASE_DIR = tmp_path
    refs_header = SimpleNamespace(
        label="section_header", text="References", level=1, prov=_prov(8),
    )
    cite1 = SimpleNamespace(
        label="list_item", text="Smith 2024. Foo.", prov=_prov(8),
    )
    appendix = SimpleNamespace(
        label="section_header", text="Appendix A", level=1, prov=_prov(9),
    )
    list_after = SimpleNamespace(
        label="list_item", text="Should not be a citation.", prov=_prov(9),
    )
    fake_doc = SimpleNamespace(
        texts=[refs_header, cite1, appendix, list_after],
        pictures=[],
        tables=[],
    )
    pdf = tmp_path / "fake.pdf"
    pdf.write_bytes(b"")
    with patch.object(dx, "_convert", return_value=fake_doc):
        result = DoclingExtractor().extract(pdf, "2401.00002")

    assert len(result.citations) == 1
    assert "Smith" in result.citations[0].raw_text


def test_doc_cache_avoids_reconvert(tmp_path, settings):
    """同 arxiv_id 多次 extract 只 convert 一次。"""
    settings.BASE_DIR = tmp_path
    fake_doc = make_fake_doc()
    pdf = tmp_path / "fake.pdf"
    pdf.write_bytes(b"")
    call_count = {"n": 0}

    def fake_convert_inner(*_args, **_kw):
        call_count["n"] += 1
        return SimpleNamespace(document=fake_doc)

    with patch.object(dx, "_get_converter", return_value=SimpleNamespace(convert=fake_convert_inner)):
        DoclingExtractor().extract(pdf, "2401.99999")
        DoclingExtractor().extract(pdf, "2401.99999")
    assert call_count["n"] == 1


# ---------------- 清洁层测试（ConvNeXt V2 双栏实测后加） ----------------

def test_section_noise_demoted_to_level2(tmp_path, settings):
    """非数字章节号且不在白名单（如 "Algorithm 1 Pseudocode" / 图内 block 标签）
    应保留但 level 弱化到 2，避免污染主章节流。"""
    settings.BASE_DIR = tmp_path
    canonical = SimpleNamespace(
        label="section_header", text="3. Method", level=1, prov=_prov(2),
    )
    noise = SimpleNamespace(
        label="section_header",
        text="Algorithm 1 Pseudocode of GRN in a PyTorch-like style.",
        level=1, prov=_prov(5),
    )
    block_label = SimpleNamespace(
        label="section_header",
        text="ConvNeXtV1Block ConvNeXtV2Block",
        level=1, prov=_prov(6),
    )
    abstract = SimpleNamespace(
        label="section_header", text="Abstract", level=1, prov=_prov(1),
    )
    fake_doc = SimpleNamespace(
        texts=[abstract, canonical, noise, block_label], pictures=[], tables=[],
    )
    pdf = tmp_path / "fake.pdf"
    pdf.write_bytes(b"")
    with patch.object(dx, "_convert", return_value=fake_doc):
        result = DoclingExtractor().extract(pdf, "2401.00003")
    by_path = {s.path: s for s in result.sections}
    assert by_path["Abstract"].level == 1            # 白名单
    assert by_path["3. Method"].level == 1           # 数字章节号
    assert by_path["Algorithm 1 Pseudocode of GRN in a PyTorch-like style."].level == 2
    assert by_path["ConvNeXtV1Block ConvNeXtV2Block"].level == 2


def test_figure_dropped_when_no_caption_and_tiny(tmp_path, settings):
    """无 caption + 小图（< 5KB）被识别为出版社 logo / 装饰图，丢。"""
    settings.BASE_DIR = tmp_path
    # picture: no caption, tiny image
    tiny_img = _FakeImage()
    pic_logo = SimpleNamespace(
        prov=_prov(1), captions=[], get_image=lambda doc: tiny_img,
    )
    # 正常 figure 作对照（与 make_fake_doc 一致）
    cap_text = SimpleNamespace(text="Figure 1: real figure.")
    cap_ref = SimpleNamespace(resolve=lambda doc: cap_text)
    pic_real = SimpleNamespace(
        prov=_prov(2), captions=[cap_ref], get_image=lambda doc: _FakeImage(),
    )
    fake_doc = SimpleNamespace(texts=[], pictures=[pic_logo, pic_real], tables=[])
    pdf = tmp_path / "fake.pdf"
    pdf.write_bytes(b"")
    with patch.object(dx, "_convert", return_value=fake_doc):
        result = DoclingExtractor().extract(pdf, "2401.00004")
    assert len(result.figures) == 1
    assert result.figures[0].caption.startswith("Figure 1:")


def test_equation_dropped_when_too_short(tmp_path, settings):
    """LaTeX 长度 < 20 字符 → OCR 渣，丢。"""
    settings.BASE_DIR = tmp_path
    short = SimpleNamespace(label="formula", text="x = 1", prov=_prov(3))
    real = SimpleNamespace(
        label="formula",
        text=r"\mathcal{L} = \sum_i (y_i - \hat{y}_i)^2",
        prov=_prov(3),
    )
    fake_doc = SimpleNamespace(texts=[short, real], pictures=[], tables=[])
    pdf = tmp_path / "fake.pdf"
    pdf.write_bytes(b"")
    with patch.object(dx, "_convert", return_value=fake_doc):
        result = DoclingExtractor().extract(pdf, "2401.00005")
    assert len(result.equations) == 1
    assert result.equations[0].latex_or_text.startswith(r"\mathcal{L}")


def test_equation_dropped_when_garbage_pattern(tmp_path, settings):
    """ConvNeXt V2 实测：双栏表格碎片渗漏成 formula（含 \\V {... 标记）→ 丢。"""
    settings.BASE_DIR = tmp_path
    garbage = SimpleNamespace(
        label="formula",
        text=r"\frac { \V { 1 + \sup , 3 0 0 e p . } \quad \V { 1 + F C M A E } } { 8 3 . 8 }",
        prov=_prov(6),
    )
    real = SimpleNamespace(
        label="formula",
        text=r"X_i = X_i * \mathcal{N}(\mathcal{G}(X)_i)",
        prov=_prov(5),
    )
    fake_doc = SimpleNamespace(texts=[garbage, real], pictures=[], tables=[])
    pdf = tmp_path / "fake.pdf"
    pdf.write_bytes(b"")
    with patch.object(dx, "_convert", return_value=fake_doc):
        result = DoclingExtractor().extract(pdf, "2401.00006")
    assert len(result.equations) == 1
    assert result.equations[0].latex_or_text.startswith("X_i")


def test_table_dropped_when_no_caption_and_few_rows(tmp_path, settings):
    """无 caption 且 markdown 行数 ≤ 2 → 误识别小布局，丢；保留有 caption 的真表。"""
    settings.BASE_DIR = tmp_path
    fragment = SimpleNamespace(
        prov=_prov(3), captions=[],
        export_to_markdown=lambda doc=None: "| a |\n| 1 |",   # 2 行换行 = 1 row
    )
    real_cap = SimpleNamespace(text="Table 3: Real table.")
    real_ref = SimpleNamespace(resolve=lambda doc: real_cap)
    real_tbl = SimpleNamespace(
        prov=_prov(7), captions=[real_ref],
        export_to_markdown=lambda doc=None: "| a | b |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |",
    )
    fake_doc = SimpleNamespace(texts=[], pictures=[], tables=[fragment, real_tbl])
    pdf = tmp_path / "fake.pdf"
    pdf.write_bytes(b"")
    with patch.object(dx, "_convert", return_value=fake_doc):
        result = DoclingExtractor().extract(pdf, "2401.00007")
    assert len(result.tables) == 1
    assert result.tables[0].tbl_label == "Table 3"


def test_material_ids_follow_format(tmp_path, settings):
    settings.BASE_DIR = tmp_path
    fake_doc = make_fake_doc()
    pdf = tmp_path / "fake.pdf"
    pdf.write_bytes(b"")
    with patch.object(dx, "_convert", return_value=fake_doc):
        result = DoclingExtractor().extract(pdf, "2401.00001")

    assert result.sections[0].material_id == "2401.00001:section:1"
    assert result.figures[0].material_id == "2401.00001:figure:1"
    assert result.tables[0].material_id == "2401.00001:table:1"
    assert result.equations[0].material_id == "2401.00001:equation:1"
    assert result.citations[0].material_id == "2401.00001:citation:1"
