"""ft-012 (搬迁自 interpret/figure_extractor): 从 PDF 提取图像 + 临近 caption.

过滤 tiny / 极端宽高比。
落盘：media/figures/<arxiv_id>/p<page>_i<index>.png 和 .caption.txt
"""
from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from django.conf import settings

log = logging.getLogger(__name__)

MIN_PIX_AREA = 200 * 150     # 30k px：典型论文配图 ≥ 400×300
MAX_ASPECT_RATIO = 8.0       # w/h 或 h/w 超过此值视为装饰条
MAX_FIGURES_PER_PAPER = 15   # 上限，按 (page, index) 升序裁切

# caption 搜索参数
CAPTION_MAX_DIST = 120    # 图像 bbox 之下的搜索距离（PDF points ≈ 1/72 inch）
CAPTION_RE = re.compile(r"^\s*(figure|fig\.?|table)\s*\d", re.IGNORECASE)


@dataclass(slots=True)
class Figure:
    arxiv_id: str
    page: int              # 1-indexed
    index: int             # 该 page 内图序号
    path: str              # 相对 figures/<arxiv_id>/ 的文件名
    caption: str = ""
    width: int = 0
    height: int = 0
    kind: str = ""         # 分类后填；ft-012 classifier 写入
    confidence: float = 0.0


def figures_root() -> Path:
    root = Path(getattr(settings, "BASE_DIR", Path.cwd())) / "media" / "figures"
    root.mkdir(parents=True, exist_ok=True)
    return root


def extract_figures(arxiv_id: str, pdf_path: Path) -> list[Figure]:
    """提取 PDF 全部图像，落盘，返回 Figure 列表。"""
    if not pdf_path.exists():
        return []
    try:
        import pymupdf
    except ImportError:
        log.error("pymupdf not installed")
        return []

    out_dir = figures_root() / arxiv_id
    out_dir.mkdir(parents=True, exist_ok=True)

    import hashlib
    figures: list[Figure] = []
    seen_hashes: set[str] = set()
    try:
        with pymupdf.open(pdf_path) as doc:
            for page_idx, page in enumerate(doc):
                if len(figures) >= MAX_FIGURES_PER_PAPER:
                    break
                images = page.get_images(full=True)
                for fig_idx, info in enumerate(images):
                    if len(figures) >= MAX_FIGURES_PER_PAPER:
                        break
                    xref = info[0]
                    try:
                        pix_info = doc.extract_image(xref)
                    except Exception as exc:  # noqa: BLE001
                        log.debug("extract_image fail p=%d i=%d: %r",
                                  page_idx, fig_idx, exc)
                        continue
                    img_bytes = pix_info.get("image")
                    ext = pix_info.get("ext", "png")
                    w = int(pix_info.get("width") or 0)
                    h = int(pix_info.get("height") or 0)

                    if not img_bytes or w * h < MIN_PIX_AREA:
                        continue
                    aspect = max(w / max(h, 1), h / max(w, 1))
                    if aspect > MAX_ASPECT_RATIO:
                        continue
                    # 去重：相同图像跨页重复（页眉/页脚/重复 logo）
                    digest = hashlib.sha1(img_bytes).hexdigest()
                    if digest in seen_hashes:
                        continue
                    seen_hashes.add(digest)

                    fname = f"p{page_idx+1:02d}_i{fig_idx:02d}.{ext}"
                    (out_dir / fname).write_bytes(img_bytes)

                    caption = _find_caption(page, xref) or ""
                    if caption:
                        (out_dir / f"{fname}.caption.txt").write_text(
                            caption, encoding="utf-8"
                        )

                    figures.append(Figure(
                        arxiv_id=arxiv_id,
                        page=page_idx + 1,
                        index=fig_idx,
                        path=fname,
                        caption=caption,
                        width=w,
                        height=h,
                    ))
    except Exception as exc:  # noqa: BLE001
        log.error("extract_figures failed: %r", exc)
        return []

    log.info("extract_figures: arxiv_id=%s got %d figures", arxiv_id, len(figures))
    return figures


def _find_caption(page, xref) -> str | None:
    """找图像 bbox 正下方最近的文字块；优先带 'Figure N' 前缀者。"""
    try:
        bboxes = page.get_image_bbox(xref)  # 返回 Rect 或 list[Rect]
    except Exception:
        return None
    if bboxes is None:
        return None
    rects = bboxes if isinstance(bboxes, list) else [bboxes]
    if not rects:
        return None
    # 取第一个 bbox（一图可能多处出现）
    rect = rects[0]
    try:
        img_bottom = rect.y1
        img_x0, img_x1 = rect.x0, rect.x1
    except AttributeError:
        return None

    blocks = page.get_text("blocks")  # [(x0,y0,x1,y1,text,block_no,block_type)]
    candidates: list[tuple[float, str]] = []
    for b in blocks:
        if len(b) < 5:
            continue
        x0, y0, x1, _y1, text = b[0], b[1], b[2], b[3], b[4]
        if not text or not text.strip():
            continue
        # 仅考虑图像下方，距离 ≤ CAPTION_MAX_DIST 的块
        dy = y0 - img_bottom
        if dy < 0 or dy > CAPTION_MAX_DIST:
            continue
        # 横向必须有重叠
        if x1 < img_x0 or x0 > img_x1:
            continue
        candidates.append((dy, text.strip()))

    if not candidates:
        return None
    candidates.sort()

    # 优先选包含 "Figure N" / "Fig. N" 前缀的
    for _, text in candidates:
        if CAPTION_RE.match(text):
            return text[:500]
    return candidates[0][1][:500]


# ---------------- index.json ----------------

def save_index(arxiv_id: str, figures: list[Figure]) -> Path:
    import json
    out_dir = figures_root() / arxiv_id
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "index.json"
    path.write_text(
        json.dumps(
            {"arxiv_id": arxiv_id,
             "figures": [asdict(f) for f in figures]},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    return path


def load_index(arxiv_id: str) -> list[Figure]:
    import json
    path = figures_root() / arxiv_id / "index.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [Figure(**f) for f in data.get("figures") or []]
    except Exception as exc:  # noqa: BLE001
        log.warning("load_index corrupt: %r", exc)
        return []
