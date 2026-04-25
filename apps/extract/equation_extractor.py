"""ft-019: 最简 display equation 抽取（pymupdf 文本扫描）.

只追求最低召回：识别 PDF 文本中带 ``(\\d+)`` 编号的"独立行"作为 display equation。
真实 latex 抽取留给 Nougat / pdffigures2 阶段（ft-015）。
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

# 一行末尾形如 "... = ... (12)" 的编号方程
EQ_NUMBERED_RE = re.compile(r"^(?P<body>.{4,}?)\s*\((?P<num>\d{1,3})\)\s*$")
# 含数学算子的最简启发：=、∑、∫、≤、≥、α-ω 等（避免拿到普通带括号编号文本）
MATH_HINT_RE = re.compile(
    r"[=≈≤≥±×÷∂∇∑∏∫√αβγδεζηθικλμνξπρστυφχψω]"
    r"|\b(sin|cos|log|exp|argmax|argmin)\b",
    re.IGNORECASE,
)


@dataclass(slots=True)
class Equation:
    arxiv_id: str
    page: int                # 1-indexed
    eq_label: str | None     # "(12)" → "12"; 无编号则 None
    bbox: tuple[float, float, float, float] | None
    text: str                # 原始文本行
    inline_or_display: str = "display"


def extract_equations(arxiv_id: str, pdf_path: Path) -> list[Equation]:
    """扫描 PDF 文本块，识别带编号的 display equation 行.

    最简启发：行尾匹配 ``(N)`` 且行内含数学算子。MVP 不追求高召回。
    """
    if not pdf_path.exists():
        return []
    try:
        import pymupdf
    except ImportError:
        log.error("pymupdf not installed")
        return []

    out: list[Equation] = []
    try:
        with pymupdf.open(pdf_path) as doc:
            for page_idx, page in enumerate(doc):
                blocks = page.get_text("blocks")
                for b in blocks:
                    if len(b) < 5:
                        continue
                    x0, y0, x1, y1, text = b[0], b[1], b[2], b[3], b[4]
                    if not text or not text.strip():
                        continue
                    for line in text.splitlines():
                        line = line.strip()
                        if not line or len(line) > 240:
                            continue
                        m = EQ_NUMBERED_RE.match(line)
                        if not m:
                            continue
                        body = m.group("body")
                        if not MATH_HINT_RE.search(body):
                            continue
                        out.append(Equation(
                            arxiv_id=arxiv_id,
                            page=page_idx + 1,
                            eq_label=m.group("num"),
                            bbox=(float(x0), float(y0), float(x1), float(y1)),
                            text=line[:500],
                            inline_or_display="display",
                        ))
    except Exception as exc:  # noqa: BLE001
        log.error("extract_equations failed: %r", exc)
        return []

    # 同一编号去重
    seen: set[str] = set()
    dedup: list[Equation] = []
    for eq in out:
        key = eq.eq_label or f"_anon:{eq.page}:{eq.text[:32]}"
        if key in seen:
            continue
        seen.add(key)
        dedup.append(eq)
    log.info("extract_equations: %s -> %d equations", arxiv_id, len(dedup))
    return dedup
