"""ft-019 + ft-015: 统一抽取入口.

ft-019 的 5 类 material 接口契约保留；具体实现 ft-015 切到 IBM Docling
（替换原 pymupdf 启发式 + equation/citation 启发式）。

外部典型用法：

    >>> from apps.extract.extractor import DefaultExtractor, persist_result
    >>> result = DefaultExtractor().extract(pdf_path, arxiv_id="2401.12345")
    >>> persist_result(result)
"""
from __future__ import annotations

import logging
from pathlib import Path

from .base import ExtractResult
from .extractors.docling_ext import DoclingExtractor

log = logging.getLogger(__name__)


class DefaultExtractor:
    """委托到 :class:`DoclingExtractor`。保留类名以兼容既有调用方。"""

    def __init__(self) -> None:
        self._impl = DoclingExtractor()

    def extract(self, paper_pdf_path: Path, paper_arxiv_id: str) -> ExtractResult:
        return self._impl.extract(paper_pdf_path, paper_arxiv_id)


def extract(paper_pdf_path: Path, paper_arxiv_id: str) -> ExtractResult:
    """单步函数式入口。"""
    return DefaultExtractor().extract(paper_pdf_path, paper_arxiv_id)


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
