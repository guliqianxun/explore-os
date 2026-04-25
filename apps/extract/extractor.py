"""ft-019: 统一抽取入口.

调度 section / figure / table / equation / citation 五类抽取，转 dataclass 列表，
并提供幂等的持久化（`update_or_create`）。

外部典型用法：

    >>> from apps.extract.extractor import DefaultExtractor, persist_result
    >>> result = DefaultExtractor().extract(pdf_path, arxiv_id="2401.12345")
    >>> persist_result(result)
"""
from __future__ import annotations

import logging
from dataclasses import asdict
from pathlib import Path

from .base import (
    CitationMaterial,
    EquationMaterial,
    ExtractResult,
    FigureMaterial,
    SectionMaterial,
    TableMaterial,
    make_material_id,
)
from .caption_extractor import extract_captions
from .citation_extractor import extract_citations
from .equation_extractor import extract_equations
from .figure_extractor import extract_figures, figures_root
from .section_extractor import chunk_pdf

log = logging.getLogger(__name__)


class DefaultExtractor:
    """组合 pymupdf 系列子抽取器，产出 ExtractResult。"""

    def extract(self, paper_pdf_path: Path, paper_arxiv_id: str) -> ExtractResult:
        return extract(paper_pdf_path, paper_arxiv_id)


def extract(paper_pdf_path: Path, paper_arxiv_id: str) -> ExtractResult:
    """单步函数式入口。caption + figure 共一次扫描，避免重复 IO。"""
    sections = _extract_sections(paper_pdf_path, paper_arxiv_id)
    figures, tables = _extract_figures_and_tables(paper_pdf_path, paper_arxiv_id)
    equations = _extract_equations(paper_pdf_path, paper_arxiv_id)
    citations = _extract_citations(paper_pdf_path, paper_arxiv_id)
    return ExtractResult(
        sections=sections,
        figures=figures,
        tables=tables,
        equations=equations,
        citations=citations,
    )


def persist_result(result: ExtractResult) -> dict[str, int]:
    """把 ExtractResult 落库，幂等：material_id 不变则 update。

    返回每类写入条数，方便 CLI 输出。
    """
    # 延迟 import 避免在 settings 未配置时导入 models
    from .models import Citation, Equation, Figure, Section, Table

    counts = {"sections": 0, "figures": 0, "tables": 0, "equations": 0, "citations": 0}

    for s in result.sections:
        Section.objects.update_or_create(
            material_id=s.material_id,
            defaults={
                "paper_arxiv_id": s.paper_arxiv_id,
                "seq": _seq_from_id(s.material_id),
                "path": s.path,
                "level": s.level,
                "char_offset_start": s.char_offset_start,
                "char_offset_end": s.char_offset_end,
                "raw_text": s.raw_text,
                "raw_payload": s.raw_payload,
            },
        )
        counts["sections"] += 1

    for f in result.figures:
        Figure.objects.update_or_create(
            material_id=f.material_id,
            defaults={
                "paper_arxiv_id": f.paper_arxiv_id,
                "seq": _seq_from_id(f.material_id),
                "fig_label": f.fig_label,
                "page": f.page,
                "bbox": list(f.bbox) if f.bbox else None,
                "caption": f.caption,
                "image_path": f.image_path,
                "raw_payload": f.raw_payload,
            },
        )
        counts["figures"] += 1

    for t in result.tables:
        Table.objects.update_or_create(
            material_id=t.material_id,
            defaults={
                "paper_arxiv_id": t.paper_arxiv_id,
                "seq": _seq_from_id(t.material_id),
                "tbl_label": t.tbl_label,
                "page": t.page,
                "bbox": list(t.bbox) if t.bbox else None,
                "caption": t.caption,
                "raw_text": t.raw_text,
                "raw_payload": t.raw_payload,
            },
        )
        counts["tables"] += 1

    for eq in result.equations:
        Equation.objects.update_or_create(
            material_id=eq.material_id,
            defaults={
                "paper_arxiv_id": eq.paper_arxiv_id,
                "seq": _seq_from_id(eq.material_id),
                "eq_label": eq.eq_label,
                "page": eq.page,
                "bbox": list(eq.bbox) if eq.bbox else None,
                "latex_or_text": eq.latex_or_text,
                "inline_or_display": eq.inline_or_display,
                "raw_payload": eq.raw_payload,
            },
        )
        counts["equations"] += 1

    for c in result.citations:
        Citation.objects.update_or_create(
            material_id=c.material_id,
            defaults={
                "paper_arxiv_id": c.paper_arxiv_id,
                "seq": _seq_from_id(c.material_id),
                "bibkey": c.bibkey,
                "raw_text": c.raw_text,
                "title": c.title,
                "year": c.year,
                "raw_payload": c.raw_payload,
            },
        )
        counts["citations"] += 1

    return counts


# ---------------- internals ----------------

def _seq_from_id(material_id: str) -> int:
    try:
        return int(material_id.rsplit(":", 1)[-1])
    except ValueError:
        return 0


def _extract_sections(pdf_path: Path, arxiv_id: str) -> list[SectionMaterial]:
    chunks = chunk_pdf(arxiv_id, pdf_path)
    if chunks is None:
        return []
    out: list[SectionMaterial] = []
    cursor = 0
    for seq, sec in enumerate(chunks.sections, start=1):
        start = cursor
        end = start + len(sec.text)
        cursor = end + 1
        out.append(SectionMaterial(
            material_id=make_material_id(arxiv_id, "section", seq),
            paper_arxiv_id=arxiv_id,
            type="section",
            raw_payload={"bucket": sec.bucket, "parser": chunks.parser},
            path=sec.title,
            level=0,
            char_offset_start=start,
            char_offset_end=end,
            raw_text=sec.text,
        ))
    return out


def _extract_figures_and_tables(
    pdf_path: Path, arxiv_id: str,
) -> tuple[list[FigureMaterial], list[TableMaterial]]:
    """captions 提供 figure/table 元数据；figure_extractor 提供落盘 image_path."""
    captions = extract_captions(arxiv_id, pdf_path)
    raw_figures = extract_figures(arxiv_id, pdf_path)

    # 把 raw_figures 按 (page,index) 简单匹配到 caption（无 caption 也保留 figure 文件）
    images_by_page: dict[int, list] = {}
    for f in raw_figures:
        images_by_page.setdefault(f.page, []).append(f)

    figs: list[FigureMaterial] = []
    tbls: list[TableMaterial] = []
    fig_seq = 0
    tbl_seq = 0

    for cap in captions:
        if cap.kind == "figure":
            fig_seq += 1
            image_path = ""
            page_imgs = images_by_page.get(cap.page) or []
            if page_imgs:
                # 第一张未被消费的 image
                f = page_imgs.pop(0)
                image_path = str(figures_root() / arxiv_id / f.path)
            figs.append(FigureMaterial(
                material_id=make_material_id(arxiv_id, "figure", fig_seq),
                paper_arxiv_id=arxiv_id,
                type="figure",
                raw_payload={
                    "number": cap.number,
                    "references": list(cap.references),
                    "bbox_caption": list(cap.bbox_caption),
                    "bbox_image": list(cap.bbox_image),
                },
                fig_label=cap.label,
                page=cap.page,
                bbox=list(cap.bbox_image),
                caption=cap.text,
                image_path=image_path,
            ))
        else:
            tbl_seq += 1
            tbls.append(TableMaterial(
                material_id=make_material_id(arxiv_id, "table", tbl_seq),
                paper_arxiv_id=arxiv_id,
                type="table",
                raw_payload={
                    "number": cap.number,
                    "references": list(cap.references),
                    "bbox_caption": list(cap.bbox_caption),
                },
                tbl_label=cap.label,
                page=cap.page,
                bbox=list(cap.bbox_caption),
                caption=cap.text,
                raw_text="",
            ))

    # captions 之外的孤立图（无 caption 的纯 image）也记录下来，避免丢失
    for page, leftover in images_by_page.items():
        for f in leftover:
            fig_seq += 1
            figs.append(FigureMaterial(
                material_id=make_material_id(arxiv_id, "figure", fig_seq),
                paper_arxiv_id=arxiv_id,
                type="figure",
                raw_payload={"orphan": True, **asdict(f)},
                fig_label="",
                page=page,
                bbox=None,
                caption=f.caption or "",
                image_path=str(figures_root() / arxiv_id / f.path),
            ))

    return figs, tbls


def _extract_equations(pdf_path: Path, arxiv_id: str) -> list[EquationMaterial]:
    raw = extract_equations(arxiv_id, pdf_path)
    out: list[EquationMaterial] = []
    for seq, eq in enumerate(raw, start=1):
        out.append(EquationMaterial(
            material_id=make_material_id(arxiv_id, "equation", seq),
            paper_arxiv_id=arxiv_id,
            type="equation",
            raw_payload={},
            eq_label=eq.eq_label,
            page=eq.page,
            bbox=list(eq.bbox) if eq.bbox else None,
            latex_or_text=eq.text,
            inline_or_display=eq.inline_or_display,
        ))
    return out


def _extract_citations(pdf_path: Path, arxiv_id: str) -> list[CitationMaterial]:
    raw = extract_citations(arxiv_id, pdf_path)
    out: list[CitationMaterial] = []
    for seq, c in enumerate(raw, start=1):
        out.append(CitationMaterial(
            material_id=make_material_id(arxiv_id, "citation", seq),
            paper_arxiv_id=arxiv_id,
            type="citation",
            raw_payload={},
            bibkey=c.bibkey,
            raw_text=c.raw_text,
            title=c.title,
            year=c.year,
        ))
    return out
