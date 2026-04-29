"""ft-019 + ft-015 + ft-034 P0-4: 统一抽取入口 + paper-level markdown public API.

ft-019 的 5 类 material 接口契约保留；具体实现 ft-015 切到 IBM Docling
（替换原 pymupdf 启发式 + equation/citation 启发式）。

ft-034 P0-4：暴露 ``get_paper_markdown(paper_id) -> str`` public API，封装
docling 的 paper-level convert + markdown 导出 + 截断。跨 app 调用方
（``apps.interpret.interpreter`` 等）应走此 API，不要 import 私有
``apps.extract.extractors.docling_ext._convert``。

外部典型用法：

    >>> from apps.extract.extractor import DefaultExtractor, persist_result
    >>> result = DefaultExtractor().extract(pdf_path, arxiv_id="2401.12345")
    >>> persist_result(result)

    >>> from apps.extract.extractor import get_paper_markdown
    >>> md = get_paper_markdown(paper_id)
"""
from __future__ import annotations

import logging
from pathlib import Path

from apps.llm.budgets import MARKDOWN_CHAR_BUDGET

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


def _markdown_from(arxiv_id: str, pdf_path: Path) -> str:
    """Internal: 从 arxiv_id + pdf_path 跑 docling convert + markdown 导出 + 截断.

    ``_convert`` 带 ``_DOC_CACHE``（key=arxiv_id），同一 paper 多次调用只 convert
    一次。截断阈值走 ``apps.llm.budgets.MARKDOWN_CHAR_BUDGET``（30k chars）。
    """
    from apps.extract.extractors.docling_ext import _convert

    doc = _convert(arxiv_id, pdf_path)
    md = doc.export_to_markdown() or ""
    if len(md) > MARKDOWN_CHAR_BUDGET:
        log.warning(
            "[extract] markdown truncated arxiv_id=%s len=%d budget=%d",
            arxiv_id, len(md), MARKDOWN_CHAR_BUDGET,
        )
        md = md[:MARKDOWN_CHAR_BUDGET]
    return md


def get_paper_markdown(paper_id: int) -> str:
    """Public API: paper → markdown 字符串（ft-034 P0-4）.

    封装 docling paper-level convert + markdown 导出 + 截断。``_convert`` 已
    带 ``_DOC_CACHE``（key=arxiv_id），同一 paper 多次调用只 convert 一次。

    截断阈值走 ``apps.llm.budgets.MARKDOWN_CHAR_BUDGET``（30k chars）。

    用法：
        >>> from apps.extract.extractor import get_paper_markdown
        >>> md = get_paper_markdown(paper.id)

    跨 app 调用（``apps.interpret`` / ``apps.llm.services``）请走本函数；
    **禁止** 直接 import ``apps.extract.extractors.docling_ext._convert``。
    """
    from apps.papers.models import Paper

    paper = Paper.objects.get(id=paper_id)
    if not paper.pdf_path:
        raise ValueError(f"Paper id={paper_id} has no pdf_path")
    arxiv_id = paper.arxiv_id or paper.key
    return _markdown_from(arxiv_id, Path(paper.pdf_path))


def get_paper_markdown_by_arxiv(arxiv_id: str, pdf_path: Path) -> str:
    """Public sibling: 跨 app 调用方手上有 ``arxiv_id + pdf_path`` 时使用.

    封装与 ``get_paper_markdown(paper_id)`` 相同的 docling convert + markdown
    导出逻辑；调用方无需查 ``Paper`` instance（如 ``apps.interpret`` 测试链不建
    Paper 行）。
    """
    return _markdown_from(arxiv_id, Path(pdf_path))


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
