"""ft-015: DoclingExtractor —— 用 IBM Docling 替换 ft-019 启发式 extractor.

Docling 给 PDF 元素打了干净的 label（section_header / formula / picture /
table / list_item），本质消除写正则做切分的需求：
  - `doc.texts[label=section_header]` → SectionMaterial
  - `doc.texts[label=formula]`        → EquationMaterial（已是 LaTeX）
  - `doc.pictures`                    → FigureMaterial（含矢量图原生 render）
  - `doc.tables`                      → TableMaterial（含 markdown 行）
  - "References" 章节后的 list_item   → CitationMaterial

模块级单例 `_get_converter()` 避免每次重新加载 ~600MB 模型；paper-level
`_DOC_CACHE` 避免同 paper 多次 façade 调用导致重复 convert（一次 30–60s）。

测试策略：单测 **绝不真跑** docling —— 一律 patch ``_convert``。
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from threading import Lock
from typing import Any

from apps.core.paths import figures_dir as _core_figures_dir
from apps.extract.base import (
    CitationMaterial,
    EquationMaterial,
    ExtractResult,
    FigureMaterial,
    SectionMaterial,
    TableMaterial,
    make_material_id,
)

log = logging.getLogger(__name__)

# ---- 模块级 converter 单例 ----
_CONVERTER: Any | None = None
_CONVERTER_LOCK = Lock()

# ---- paper-level doc cache（key = arxiv_id）----
_DOC_CACHE: dict[str, Any] = {}


def _get_converter() -> Any:
    """惰性构造 + 单例缓存 DocumentConverter。GPU 自动检测。"""
    global _CONVERTER
    if _CONVERTER is not None:
        return _CONVERTER
    with _CONVERTER_LOCK:
        if _CONVERTER is not None:
            return _CONVERTER
        # 延迟 import，避免无 docling 环境下导入即崩
        import torch
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import (
            AcceleratorDevice,
            AcceleratorOptions,
            PdfPipelineOptions,
        )
        from docling.document_converter import DocumentConverter, PdfFormatOption

        # `EXPLORE_OS_DOCLING_FORMULA=0` disables CodeFormulaV2 enrichment
        # (~611MB model, runs once per equation and is the dominant cost on
        # CPU torch — a math-heavy paper takes 30+ minutes). Default on.
        import os as _os
        do_formula = _os.environ.get(
            "EXPLORE_OS_DOCLING_FORMULA", "1",
        ).strip().lower() not in ("0", "false", "no", "off")

        opts = PdfPipelineOptions()
        opts.images_scale = 2.0
        opts.generate_picture_images = True
        opts.do_formula_enrichment = do_formula
        opts.accelerator_options = AcceleratorOptions(
            num_threads=8,
            device=(
                AcceleratorDevice.CUDA
                if torch.cuda.is_available()
                else AcceleratorDevice.CPU
            ),
        )
        _CONVERTER = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=opts),
            }
        )
        log.info(
            "[docling] converter initialized device=%s",
            "CUDA" if torch.cuda.is_available() else "CPU",
        )
        return _CONVERTER


# ft-034 P0-4：禁止跨 app 调用 _convert（review-A H7）。
# 跨 app（apps.interpret / apps.llm.services / apps.papers）请走 public API
# `apps.extract.extractor.get_paper_markdown(paper_id)`。本函数仅 apps.extract
# 内部使用（DoclingExtractor.extract + extractor.get_paper_markdown）。
def _convert(arxiv_id: str, pdf_path: Path) -> Any:
    """paper-level 缓存的 docling convert。同 arxiv_id 多次调用只 convert 一次。"""
    if arxiv_id in _DOC_CACHE:
        return _DOC_CACHE[arxiv_id]
    log.info("[docling] convert start arxiv_id=%s pdf=%s", arxiv_id, pdf_path)
    result = _get_converter().convert(str(pdf_path))
    _DOC_CACHE[arxiv_id] = result.document
    log.info("[docling] convert done arxiv_id=%s", arxiv_id)
    return result.document


def _figures_dir(arxiv_id: str) -> Path:
    return _core_figures_dir(arxiv_id)


# ---------------- Mappers ----------------

_FIG_LABEL_RE = re.compile(r"\b(Figure|Fig\.?)\s*(\d+)", re.IGNORECASE)
_TBL_LABEL_RE = re.compile(r"\b(Table|Tab\.?)\s*(\d+)", re.IGNORECASE)
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
_FIRST_AUTHOR_RE = re.compile(r"^([A-Z][A-Za-z\-']+)")

# ---- 清洁层（ConvNeXt V2 双栏实测后加，2026-04-26）----
# Docling 在多栏 / figure-table 共存页面上有已知短板：偶发把 logo 当 picture、
# 表格碎片当 formula、algorithm 标题当 section_header。这里在 mapper 出口做最
# 小过滤，保住接口契约不变，下游消费者免去自行过滤。

# Figure：image 文件 < 此阈值且无 caption → 丢
_FIGURE_MIN_BYTES_NO_CAPTION = 5 * 1024  # 5KB

# Equation：LaTeX 长度 < 此阈值 或 含明显 OCR 渣 → 丢
_EQUATION_MIN_LEN = 20
_EQUATION_GARBAGE_RE = re.compile(r"\\V\s*\{|\\\s*[A-Z]\s*\{[^}]*\d+\s*\+\s*\w")

# Section：白名单（命中即保留 level=1；其他保留但降为 level=2 弱化）
_SECTION_NUMBERED_RE = re.compile(r"^\s*\d+(\.\d+)*\.?\s+\S")
_SECTION_WHITELIST = {
    "abstract", "introduction", "related work", "background", "method", "methods",
    "approach", "model", "framework", "experiments", "evaluation", "results",
    "discussion", "limitations", "conclusion", "conclusions", "references",
    "acknowledgements", "acknowledgments", "appendix", "future work",
}

# Table：无 caption 且 markdown 行数 ≤ 此阈值 → 丢
_TABLE_MIN_ROWS_NO_CAPTION = 2


def _label_of(item: Any) -> str:
    return str(getattr(item, "label", "") or "")


def _prov_page(item: Any) -> int:
    prov = getattr(item, "prov", None) or []
    if not prov:
        return 0
    return int(getattr(prov[0], "page_no", 0) or 0)


def _prov_bbox(item: Any) -> list[float] | None:
    prov = getattr(item, "prov", None) or []
    if not prov:
        return None
    bbox = getattr(prov[0], "bbox", None)
    if bbox is None:
        return None
    try:
        return [float(bbox.l), float(bbox.t), float(bbox.r), float(bbox.b)]
    except AttributeError:
        return None


def _resolve_caption(item: Any, doc: Any) -> str:
    captions = getattr(item, "captions", None) or []
    if not captions:
        return ""
    try:
        resolved = captions[0].resolve(doc)
        return getattr(resolved, "text", "") or ""
    except Exception as exc:  # noqa: BLE001
        log.debug("[docling] caption resolve failed: %r", exc)
        return ""


def _section_is_canonical(title: str) -> bool:
    """Whitelist 命中或带数字章节号则视为「正章节」，否则弱化到 level=2."""
    t = (title or "").strip().lower()
    if not t:
        return False
    if _SECTION_NUMBERED_RE.match(title):
        return True
    # 去掉前缀编号后再匹配 whitelist（"1. Introduction" → "introduction"）
    head = re.sub(r"^\s*\d+(\.\d+)*\.?\s+", "", t).strip()
    return head in _SECTION_WHITELIST or t in _SECTION_WHITELIST


# Labels that count as section body text (paragraphs, list items).
# Excludes captions (belong to figures/tables), formulas, footnotes —
# those are mapped separately or are not paper-body.
_SECTION_BODY_LABELS = {"text", "paragraph", "list_item"}


def _map_sections(doc: Any, arxiv_id: str) -> list[SectionMaterial]:
    """Walk doc.texts in order. Each `section_header` opens a section; any
    body-labeled item between this header and the next is appended to the
    section's `raw_text`. Without this, downstream consumers (markdown view,
    figure ↔ section similarity) only see headings and can't make decisions.
    """
    pending: list[dict] = []
    cur: dict | None = None
    for t in getattr(doc, "texts", []) or []:
        label = _label_of(t)
        text = (getattr(t, "text", "") or "").strip()
        if label == "section_header":
            cur = {
                "title": getattr(t, "text", "") or "",
                "level": int(getattr(t, "level", 1) or 1),
                "body": [],
            }
            pending.append(cur)
        elif label in _SECTION_BODY_LABELS and cur is not None and text:
            cur["body"].append(text)

    out: list[SectionMaterial] = []
    for i, p in enumerate(pending, start=1):
        title = p["title"]
        raw_level = p["level"]
        level = raw_level if _section_is_canonical(title) else max(raw_level, 2)
        out.append(SectionMaterial(
            material_id=make_material_id(arxiv_id, "section", i),
            paper_arxiv_id=arxiv_id,
            type="section",
            raw_payload={"parser": "docling", "canonical": _section_is_canonical(title)},
            path=title,
            level=level,
            char_offset_start=0,
            char_offset_end=0,
            raw_text="\n\n".join(p["body"]),
        ))
    return out


def _map_figures(doc: Any, arxiv_id: str) -> list[FigureMaterial]:
    out: list[FigureMaterial] = []
    seq = 0
    pictures = getattr(doc, "pictures", None) or []
    out_dir = _figures_dir(arxiv_id) if pictures else None
    for p in pictures:
        try:
            img = p.get_image(doc)
        except Exception as exc:  # noqa: BLE001
            log.debug("[docling] picture get_image failed: %r", exc)
            img = None
        if img is None:
            # 跳过：无 image 的 picture 不算 figure（dsp-003 规则）
            continue
        seq += 1
        material_id = make_material_id(arxiv_id, "figure", seq)
        image_path = ""
        if out_dir is not None:
            image_path = str(out_dir / f"{material_id.replace(':', '_')}.png")
            try:
                img.save(image_path)
            except Exception as exc:  # noqa: BLE001
                log.warning("[docling] picture save failed: %r", exc)
                image_path = ""
        caption = _resolve_caption(p, doc)
        # 清洁：无 caption 且 image 极小 → 出版社 logo / 装饰图，丢
        if not caption and image_path:
            try:
                if Path(image_path).stat().st_size < _FIGURE_MIN_BYTES_NO_CAPTION:
                    Path(image_path).unlink(missing_ok=True)
                    seq -= 1  # 回退序号
                    continue
            except OSError:
                pass
        m = _FIG_LABEL_RE.search(caption)
        fig_label = m.group(0) if m else ""
        out.append(FigureMaterial(
            material_id=material_id,
            paper_arxiv_id=arxiv_id,
            type="figure",
            raw_payload={"parser": "docling"},
            fig_label=fig_label,
            page=_prov_page(p),
            bbox=_prov_bbox(p),
            caption=caption,
            image_path=image_path,
        ))
    return out


def _table_to_markdown(t: Any, doc: Any) -> str:
    if not hasattr(t, "export_to_markdown"):
        return ""
    # 不同 docling 版本签名差异：旧版 export_to_markdown(doc) / 新版 export_to_markdown()
    try:
        return t.export_to_markdown(doc) or ""
    except TypeError:
        try:
            return t.export_to_markdown() or ""
        except Exception as exc:  # noqa: BLE001
            log.debug("[docling] table export_to_markdown failed: %r", exc)
            return ""
    except Exception as exc:  # noqa: BLE001
        log.debug("[docling] table export_to_markdown failed: %r", exc)
        return ""


def _map_tables(doc: Any, arxiv_id: str) -> list[TableMaterial]:
    out: list[TableMaterial] = []
    seq = 0
    for t in getattr(doc, "tables", None) or []:
        caption = _resolve_caption(t, doc)
        raw_md = _table_to_markdown(t, doc)
        # 清洁：无 caption 且 markdown 行数过少 → 多半是误识别的小布局碎片，丢
        if not caption:
            n_rows = raw_md.count("\n") if raw_md else 0
            if n_rows <= _TABLE_MIN_ROWS_NO_CAPTION:
                continue
        seq += 1
        m = _TBL_LABEL_RE.search(caption)
        tbl_label = m.group(0) if m else ""
        out.append(TableMaterial(
            material_id=make_material_id(arxiv_id, "table", seq),
            paper_arxiv_id=arxiv_id,
            type="table",
            raw_payload={"parser": "docling"},
            tbl_label=tbl_label,
            page=_prov_page(t),
            bbox=_prov_bbox(t),
            caption=caption,
            raw_text=raw_md,
        ))
    return out


def _map_equations(doc: Any, arxiv_id: str) -> list[EquationMaterial]:
    out: list[EquationMaterial] = []
    seq = 0
    for t in getattr(doc, "texts", None) or []:
        if _label_of(t) != "formula":
            continue
        latex = getattr(t, "text", "") or ""
        # 清洁：太短 / OCR 渣（含 \V {... 这类双栏表格碎片渗漏）→ 丢
        if len(latex.strip()) < _EQUATION_MIN_LEN:
            continue
        if _EQUATION_GARBAGE_RE.search(latex):
            continue
        seq += 1
        out.append(EquationMaterial(
            material_id=make_material_id(arxiv_id, "equation", seq),
            paper_arxiv_id=arxiv_id,
            type="equation",
            raw_payload={"parser": "docling"},
            eq_label=None,
            page=_prov_page(t),
            bbox=_prov_bbox(t),
            latex_or_text=getattr(t, "text", "") or "",
            inline_or_display="display",
        ))
    return out


def _map_citations(doc: Any, arxiv_id: str) -> list[CitationMaterial]:
    out: list[CitationMaterial] = []
    in_refs = False
    seq = 0
    for t in getattr(doc, "texts", None) or []:
        label = _label_of(t)
        text = getattr(t, "text", "") or ""
        if label == "section_header":
            if "reference" in text.lower():
                in_refs = True
                continue
            if in_refs:
                # 进入下一 section，引用区结束
                break
            continue
        if not in_refs:
            continue
        if label != "list_item":
            continue
        raw = text.strip()
        if not raw:
            continue
        seq += 1
        year_match = _YEAR_RE.search(raw)
        year = int(year_match.group(0)) if year_match else None
        author_match = _FIRST_AUTHOR_RE.match(raw)
        author = author_match.group(1).lower() if author_match else "ref"
        bibkey = f"{author}{year if year is not None else 'n.d.'}"
        out.append(CitationMaterial(
            material_id=make_material_id(arxiv_id, "citation", seq),
            paper_arxiv_id=arxiv_id,
            type="citation",
            raw_payload={"parser": "docling"},
            bibkey=bibkey,
            raw_text=raw[:1000],
            title="",
            year=year,
        ))
    return out


# ---------------- Extractor ----------------

class DoclingExtractor:
    """实现 ``apps.extract.base.Extractor`` Protocol。"""

    def extract(self, paper_pdf_path: Path, paper_arxiv_id: str) -> ExtractResult:
        doc = _convert(paper_arxiv_id, Path(paper_pdf_path))
        return ExtractResult(
            sections=_map_sections(doc, paper_arxiv_id),
            figures=_map_figures(doc, paper_arxiv_id),
            tables=_map_tables(doc, paper_arxiv_id),
            equations=_map_equations(doc, paper_arxiv_id),
            citations=_map_citations(doc, paper_arxiv_id),
        )
