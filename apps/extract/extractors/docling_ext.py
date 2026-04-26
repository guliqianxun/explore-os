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

from django.conf import settings

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

        opts = PdfPipelineOptions()
        opts.images_scale = 2.0
        opts.generate_picture_images = True
        opts.do_formula_enrichment = True
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
    base = Path(getattr(settings, "BASE_DIR", Path.cwd())) / "media" / "figures" / arxiv_id
    base.mkdir(parents=True, exist_ok=True)
    return base


# ---------------- Mappers ----------------

_FIG_LABEL_RE = re.compile(r"\b(Figure|Fig\.?)\s*(\d+)", re.IGNORECASE)
_TBL_LABEL_RE = re.compile(r"\b(Table|Tab\.?)\s*(\d+)", re.IGNORECASE)
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
_FIRST_AUTHOR_RE = re.compile(r"^([A-Z][A-Za-z\-']+)")


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


def _map_sections(doc: Any, arxiv_id: str) -> list[SectionMaterial]:
    out: list[SectionMaterial] = []
    seq = 0
    for t in getattr(doc, "texts", []) or []:
        if _label_of(t) != "section_header":
            continue
        seq += 1
        title = getattr(t, "text", "") or ""
        out.append(SectionMaterial(
            material_id=make_material_id(arxiv_id, "section", seq),
            paper_arxiv_id=arxiv_id,
            type="section",
            raw_payload={"parser": "docling"},
            path=title,
            level=int(getattr(t, "level", 1) or 1),
            char_offset_start=0,
            char_offset_end=0,
            raw_text="",
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
        seq += 1
        caption = _resolve_caption(t, doc)
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
            raw_text=_table_to_markdown(t, doc),
        ))
    return out


def _map_equations(doc: Any, arxiv_id: str) -> list[EquationMaterial]:
    out: list[EquationMaterial] = []
    seq = 0
    for t in getattr(doc, "texts", None) or []:
        if _label_of(t) != "formula":
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
