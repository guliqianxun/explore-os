"""ft-013: 抽取论文 captions + bbox + 正文引用上下文（确定性工具，不调 LLM）.

Caption 形如:
  Figure 1: Overview of UniT framework.
  Fig. 3: Comparison results on ...
  Table 2: Quantitative metrics ...

bbox 是该 caption 文本块在 PDF 页面上的位置，用于 pdf_renderer 把
caption 上方的图像区域渲染为 PNG。
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

# Caption 正则（行首，宽松匹配中英文期刊常见前缀）
CAPTION_PREFIX_RE = re.compile(
    # 兼容 "Figure 1: ..." / "Fig. 3. ..." / "Figure 1 We propose ..."（无冒号）
    r"^\s*(Figure|Fig\.?|Table|Tab\.?)\s*(\d+)\s*[:.。：]?\s+(.+)$",
    re.IGNORECASE,
)
# 正文里对图的引用，如 "Figure 1" / "Fig. 3" / "Tab. 2"
REFERENCE_RE = re.compile(
    r"\b(Figure|Fig\.?|Table|Tab\.?)\s*(\d+)\b",
    re.IGNORECASE,
)

# Caption 上方 PDF 单位中允许的图像高度，用于 bbox 推算
DEFAULT_FIG_BAND_ABOVE = 380   # PDF points; 大约能盖住单栏一张图


@dataclass(slots=True)
class Caption:
    arxiv_id: str
    kind: str           # "figure" | "table"
    number: int         # 1, 2, 3, ...
    text: str           # caption 全文（"Figure 1: Overview of ..."）
    page: int           # 1-indexed
    bbox_caption: tuple[float, float, float, float]   # caption 文本块 (x0,y0,x1,y1)
    bbox_image: tuple[float, float, float, float]     # 推算出的图像区域
    references: list[str] = field(default_factory=list)  # 正文引用上下文片段

    @property
    def label(self) -> str:
        prefix = "Fig." if self.kind == "figure" else "Tab."
        return f"{prefix} {self.number}"


def extract_captions(arxiv_id: str, pdf_path: Path) -> list[Caption]:
    """从 PDF 抽取所有 figure/table captions + bbox + 正文引用上下文."""
    if not pdf_path.exists():
        return []
    try:
        import pymupdf
    except ImportError:
        log.error("pymupdf not installed")
        return []

    captions: list[Caption] = []
    full_text_blocks: list[tuple[int, str]] = []  # (page_idx, text) 用于搜引用

    try:
        with pymupdf.open(pdf_path) as doc:
            page_widths: list[float] = []
            for page_idx, page in enumerate(doc):
                page_widths.append(page.rect.width)
                blocks = page.get_text("blocks")
                for b in blocks:
                    if len(b) < 5:
                        continue
                    x0, y0, x1, y1, text = b[0], b[1], b[2], b[3], b[4]
                    if not text or not text.strip():
                        continue
                    text_one = text.strip().replace("\n", " ")
                    full_text_blocks.append((page_idx + 1, text_one))

                    # block 内可能多行，逐行尝试 caption 匹配
                    matched = None
                    for line in text.splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        m = CAPTION_PREFIX_RE.match(line)
                        if m:
                            matched = (m, line)
                            break
                    if not matched:
                        continue
                    m, caption_line = matched
                    kind_raw, num_raw = m.group(1), m.group(2)
                    kind = "figure" if kind_raw.lower().startswith("fig") else "table"
                    try:
                        num = int(num_raw)
                    except ValueError:
                        continue
                    # caption 整段：从匹配行开始到 block 末尾（caption 常跨多行）
                    full_caption = " ".join(
                        ln.strip() for ln in text.splitlines()
                        if ln.strip() and (ln.strip() == caption_line
                                            or text.find(caption_line) <= text.find(ln))
                    )[:600]
                    img_y1 = y0 - 2
                    img_y0 = max(0.0, img_y1 - DEFAULT_FIG_BAND_ABOVE)
                    captions.append(Caption(
                        arxiv_id=arxiv_id,
                        kind=kind,
                        number=num,
                        text=full_caption or caption_line[:600],
                        page=page_idx + 1,
                        bbox_caption=(x0, y0, x1, y1),
                        bbox_image=(x0, img_y0, x1, img_y1),
                    ))
    except Exception as exc:  # noqa: BLE001
        log.error("extract_captions failed: %r", exc)
        return []

    # 同一图重复 caption（如双栏对照）按 (kind, number) 去重，保留首次
    dedup: dict[tuple[str, int], Caption] = {}
    for c in captions:
        key = (c.kind, c.number)
        if key not in dedup:
            dedup[key] = c
    captions = list(dedup.values())
    captions.sort(key=lambda c: (c.kind, c.number))

    # 抽正文引用上下文
    _attach_references(captions, full_text_blocks)
    log.info("extract_captions: %s -> %d captions", arxiv_id, len(captions))
    return captions


def _attach_references(captions: list[Caption], blocks: list[tuple[int, str]]) -> None:
    """对每个 caption 找正文里 "Figure N" / "Fig. N" 提及的片段（去除 caption 自身）."""
    by_kn: dict[tuple[str, int], list[str]] = {}
    for caption in captions:
        by_kn.setdefault((caption.kind, caption.number), [])

    for _page, text in blocks:
        # caption 行本身先过掉
        if CAPTION_PREFIX_RE.match(text):
            continue
        for m in REFERENCE_RE.finditer(text):
            kind_raw, num_raw = m.group(1), m.group(2)
            kind = "figure" if kind_raw.lower().startswith("fig") else "table"
            try:
                num = int(num_raw)
            except ValueError:
                continue
            key = (kind, num)
            if key not in by_kn:
                continue
            # 取引用周围 ≈100 字上下文
            start = max(0, m.start() - 60)
            end = min(len(text), m.end() + 80)
            snippet = text[start:end].strip().replace("  ", " ")
            if len(by_kn[key]) >= 4:
                continue
            by_kn[key].append(snippet)

    for c in captions:
        c.references = by_kn.get((c.kind, c.number), [])
