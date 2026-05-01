"""ft-039 (planned) 配套：用 pdfplumber 给 fast lane 做轻量图抽。

与 docling 的 figure_extractor 解耦：
- docling 出 (caption, bbox, picture) 三元组，落 ``media/figures/``
- 这里只做 "找到 image-heavy 页 → 整页裁出来 → PNG"，落 ``media/figures-fast/``

适用：brief / primary 卡显示 paper 的"封面级"框架图，不需要 caption/bbox。
触发：detail 页 GET 时若 fast figures 缺失，类似 ``ensure_pdf_async`` 异步抽。

策略（粗暴但够用）：
1. 跳过纯文本页（page.images 为空）
2. 把页面上所有 image 对象的 bbox 取并集（union），只保留并集占页面 >=10% 的页
3. 对这些页，在 union bbox 上做 ``page.crop().to_image(resolution=150).save()``
4. 同 paper 累计裁满 N=3 张就停（"封面级"够用）

没做：
- caption 关联（markitdown 文本流没位置信息）
- 图分类（method / chart / table），后续可叠 LLM 判
- 多列布局合并（双栏论文跨列图当作两块裁出）
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

import pdfplumber

from apps.core.paths import data_dir

log = logging.getLogger(__name__)

MIN_AREA_RATIO = 0.10  # 并集占页面比例阈值
MAX_FIGURES = 3
RESOLUTION = 150  # DPI


def figures_fast_dir(arxiv_id: str) -> Path:
    """``<DATA_DIR>/media/figures-fast/<arxiv_id>/``。"""
    p = data_dir() / "media" / "figures-fast" / arxiv_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def _bbox_union(boxes: Iterable[tuple[float, float, float, float]]) -> tuple[float, float, float, float] | None:
    boxes = list(boxes)
    if not boxes:
        return None
    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    x1 = max(b[2] for b in boxes)
    y1 = max(b[3] for b in boxes)
    return (x0, y0, x1, y1)


def _img_bbox(img: dict) -> tuple[float, float, float, float]:
    """pdfplumber image dict → (x0, top, x1, bottom)，pdfplumber 坐标系。"""
    return (
        float(img.get("x0", 0)),
        float(img.get("top", 0)),
        float(img.get("x1", 0)),
        float(img.get("bottom", 0)),
    )


def extract_figures_fast(pdf_path: Path, arxiv_id: str) -> list[Path]:
    """从 PDF 抽前 ``MAX_FIGURES`` 张"图密集页整裁"。返回写出的 PNG 路径列表。

    幂等：目标目录已有 ``1.png`` … ``MAX_FIGURES.png`` 时直接返回（不重抽）。
    """
    out_dir = figures_fast_dir(arxiv_id)
    existing = sorted(out_dir.glob("*.png"))
    if existing:
        log.info("[figures-fast] %s cache hit (%d files)", arxiv_id, len(existing))
        return existing

    out: list[Path] = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                if not page.images:
                    continue
                page_area = (page.bbox[2] - page.bbox[0]) * (page.bbox[3] - page.bbox[1])
                if page_area <= 0:
                    continue
                union = _bbox_union(_img_bbox(im) for im in page.images)
                if union is None:
                    continue
                area = (union[2] - union[0]) * (union[3] - union[1])
                if area / page_area < MIN_AREA_RATIO:
                    continue
                # 给 union 加 ~16pt padding（露 caption / 上下文）
                pad = 16.0
                x0 = max(page.bbox[0], union[0] - pad)
                y0 = max(page.bbox[1], union[1] - pad)
                x1 = min(page.bbox[2], union[2] + pad)
                y1 = min(page.bbox[3], union[3] + pad)
                try:
                    cropped = page.crop((x0, y0, x1, y1))
                    pil = cropped.to_image(resolution=RESOLUTION)
                    seq = len(out) + 1
                    dst = out_dir / f"{seq}.png"
                    pil.save(str(dst), format="PNG")
                    out.append(dst)
                    log.info(
                        "[figures-fast] %s p%d → %s (%.1f%% area)",
                        arxiv_id, page_num, dst.name, 100 * area / page_area,
                    )
                except Exception as exc:  # noqa: BLE001
                    log.warning(
                        "[figures-fast] %s p%d crop failed: %r",
                        arxiv_id, page_num, exc,
                    )
                    continue
                if len(out) >= MAX_FIGURES:
                    break
    except Exception as exc:  # noqa: BLE001
        log.error("[figures-fast] %s open failed: %r", arxiv_id, exc)
        return out

    log.info("[figures-fast] %s wrote %d figures", arxiv_id, len(out))
    return out
