"""ft-013: 渲染 PDF 某一页指定 bbox 区域为 PNG（确定性工具）.

替代 figure_extractor 的"抽嵌入图像"策略——后者会把矢量图分解成无数碎片。
bbox 由 caption_extractor 推算而来。
"""
from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)

# 渲染 DPI（72 = PDF 原生；144 = 2x）
DEFAULT_DPI = 144


def render_bbox_to_png(
    pdf_path: Path,
    page: int,             # 1-indexed
    bbox: tuple[float, float, float, float],
    out_path: Path,
    dpi: int = DEFAULT_DPI,
) -> bool:
    """渲染 PDF 第 page 页 bbox 区域为 PNG 落到 out_path。失败返回 False."""
    if not pdf_path.exists():
        return False
    try:
        import pymupdf
    except ImportError:
        log.error("pymupdf not installed")
        return False

    try:
        with pymupdf.open(pdf_path) as doc:
            if page < 1 or page > doc.page_count:
                return False
            pg = doc[page - 1]
            x0, y0, x1, y1 = bbox
            # clip 到页面边界，防越界
            page_rect = pg.rect
            x0 = max(page_rect.x0, x0)
            y0 = max(page_rect.y0, y0)
            x1 = min(page_rect.x1, x1)
            y1 = min(page_rect.y1, y1)
            if x1 <= x0 or y1 <= y0:
                return False
            clip = pymupdf.Rect(x0, y0, x1, y1)
            zoom = dpi / 72.0
            mat = pymupdf.Matrix(zoom, zoom)
            pix = pg.get_pixmap(matrix=mat, clip=clip, alpha=False)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            pix.save(str(out_path))
            return True
    except Exception as exc:  # noqa: BLE001
        log.error("render_bbox failed: %r", exc)
        return False
