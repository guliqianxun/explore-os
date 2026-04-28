"""ft-029: PDF 路径解析助手。

封装 ``Paper.pdf_path`` + legacy fallback 的解析顺序，避免散落到每个调用方。
``papers_dir / pdf_legacy_dir`` 仍由 ``apps.core.paths`` 拥有；本模块仅做 re-export
+ 业务级解析。
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from apps.core.paths import papers_dir, pdf_legacy_dir

if TYPE_CHECKING:  # 避免循环 import
    from apps.papers.models import Paper

__all__ = ["papers_dir", "pdf_legacy_dir", "resolve_pdf_path"]


def resolve_pdf_path(paper: "Paper") -> Path | None:
    """返回 paper 关联的 PDF 绝对路径，找不到则 None。

    解析顺序：
    1. ``paper.pdf_path``（ft-029 字段，ingest 链路写入）；存在即用。
    2. legacy fallback：``papers_dir() / <arxiv>.pdf`` 或 ``pdf_legacy_dir() / <arxiv>.pdf``
       — 兼容 ft-028 之前未写 pdf_path 的旧记录。
    """
    if paper.pdf_path:
        p = Path(paper.pdf_path)
        if p.exists():
            return p
    if paper.arxiv_id:
        for d in (papers_dir(), pdf_legacy_dir()):
            p = d / f"{paper.arxiv_id}.pdf"
            if p.exists():
                return p
    return None
