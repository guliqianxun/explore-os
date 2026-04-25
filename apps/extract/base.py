"""ft-019: 抽取器接口契约 + 五类 Material dataclass.

抽取器只产确定性 material（不做语义、不做 claim 抽取、不做图分类）。
material_id 规则：``<paper_arxiv_id>:<type>:<seq>``，例如 ``2401.12345:figure:3``。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass
class BaseMaterial:
    material_id: str
    paper_arxiv_id: str
    type: str  # section | figure | table | equation | citation
    raw_payload: dict = field(default_factory=dict)


@dataclass
class SectionMaterial(BaseMaterial):
    path: str = ""  # "3.2 Method"
    level: int = 0
    char_offset_start: int = 0
    char_offset_end: int = 0
    raw_text: str = ""


@dataclass
class FigureMaterial(BaseMaterial):
    fig_label: str = ""
    page: int = 0
    bbox: list[float] | None = None
    caption: str = ""
    image_path: str = ""


@dataclass
class TableMaterial(BaseMaterial):
    tbl_label: str = ""
    page: int = 0
    bbox: list[float] | None = None
    caption: str = ""
    raw_text: str = ""


@dataclass
class EquationMaterial(BaseMaterial):
    eq_label: str | None = None
    page: int = 0
    bbox: list[float] | None = None
    latex_or_text: str = ""
    inline_or_display: str = "display"


@dataclass
class CitationMaterial(BaseMaterial):
    bibkey: str = ""
    raw_text: str = ""
    title: str = ""
    year: int | None = None


@dataclass
class ExtractResult:
    sections: list[SectionMaterial]
    figures: list[FigureMaterial]
    tables: list[TableMaterial]
    equations: list[EquationMaterial]
    citations: list[CitationMaterial]


class Extractor(Protocol):
    def extract(self, paper_pdf_path: Path, paper_arxiv_id: str) -> ExtractResult: ...


def make_material_id(paper_arxiv_id: str, type_: str, seq: int) -> str:
    """构造稳定的 material_id：``<paper>:<type>:<seq>``。seq 按 paper 内顺序稳定编号。"""
    return f"{paper_arxiv_id}:{type_}:{seq}"
