"""ft-020: 解读器接口契约 + dataclass.

dataclass 走 LLM → ORM 之间的中间载体；落库前由 persist 层转 ORM 行。
``ClaimDraft.evidences`` 中的 ``material_id`` 必须为 full form
(``<arxiv_id>:<type>:<seq>``)，简写 → 全形的解析在 interpreter 层完成。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

ClaimType = Literal["proposal", "result", "ablation", "theoretical"]
EvidenceRelation = Literal["illustrates", "quantifies", "supports"]
SignalType = Literal["limitation", "ablation_drop", "failure_case", "prior_work_better"]


@dataclass
class ClaimEvidenceDraft:
    material_id: str  # full form: <arxiv_id>:<type>:<seq>
    relation: EvidenceRelation = "supports"


@dataclass
class ClaimDraft:
    text: str
    text_en: str = ""
    claim_type: ClaimType = "result"
    source_section_path: str = ""
    confidence: float = 0.0
    evidences: list[ClaimEvidenceDraft] = field(default_factory=list)


@dataclass
class CounterSignalDraft:
    text: str
    signal_type: SignalType
    evidence_material_id: str  # full form, must be in allowed
    claim_idx: int             # index into InterpretResult.claims


@dataclass
class InterpretResult:
    paper_arxiv_id: str
    claims: list[ClaimDraft]
    counter_signals: list[CounterSignalDraft]


class Interpreter(Protocol):
    def interpret(self, paper_arxiv_id: str, pdf_path: Path) -> InterpretResult: ...
