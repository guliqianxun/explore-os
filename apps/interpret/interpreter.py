"""ft-020: DefaultInterpreter — L1+L2 编排.

工具/LLM 边界：
  - catalog 构造、cite 简写→full 解析、confidence/allowed 过滤、claim_idx 校验 → 工具
  - claim 抽取本身、反向信号识别 → LLM
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from apps.llm.errors import LLMError  # ft-034 P0-1

from apps.interpret.base import (
    ClaimDraft,
    ClaimEvidenceDraft,
    CounterSignalDraft,
    InterpretResult,
)
from apps.interpret.catalog import build_catalog, resolve_short_to_full
from apps.interpret.llm_client import chat_json
from apps.interpret.prompts import (
    L1_SYSTEM,
    L1_USER_TEMPLATE,
    L2_SYSTEM,
    L2_USER_TEMPLATE,
    render_claims_brief,
)

log = logging.getLogger(__name__)

# 长论文截断：leworldmodel / convnextv2 都在阈值内
MARKDOWN_CHAR_BUDGET = 30_000

_VALID_RELATIONS = {"illustrates", "quantifies", "supports"}
_VALID_CLAIM_TYPES = {"proposal", "result", "ablation", "theoretical"}
_VALID_SIGNAL_TYPES = {"limitation", "ablation_drop", "failure_case", "prior_work_better"}

CONFIDENCE_FLOOR = 0.5


def get_paper_markdown(arxiv_id: str, pdf_path: Path) -> str:
    """复用 docling paper-level 缓存，导出 markdown。超 budget 截断。

    ft-034 P0-4：不再直接调 ``_convert`` 私有；走 ``apps.extract.extractor`` 的
    public API。截断阈值仍由 ``MARKDOWN_CHAR_BUDGET`` 控制（与 ``apps.llm.budgets``
    数值一致）。
    """
    from apps.extract.extractor import get_paper_markdown_by_arxiv

    return get_paper_markdown_by_arxiv(arxiv_id, Path(pdf_path))


def _coerce_claim_type(v: Any) -> str:
    s = str(v or "").strip().lower()
    return s if s in _VALID_CLAIM_TYPES else "result"


def _coerce_relation(v: Any) -> str:
    s = str(v or "").strip().lower()
    return s if s in _VALID_RELATIONS else "supports"


def _coerce_signal_type(v: Any) -> str | None:
    s = str(v or "").strip().lower()
    return s if s in _VALID_SIGNAL_TYPES else None


def _parse_l1_claims(
    raw: dict[str, Any], arxiv_id: str, allowed: set[str]
) -> list[ClaimDraft]:
    """L1 后处理：cite 解析 + 校验 + confidence 过滤."""
    out: list[ClaimDraft] = []
    items = raw.get("claims") or []
    if not isinstance(items, list):
        log.warning("[interpret] L1 'claims' not a list: %r", type(items).__name__)
        return out

    for c in items:
        if not isinstance(c, dict):
            continue
        text = str(c.get("text") or "").strip()
        if not text:
            continue

        # confidence
        try:
            conf = float(c.get("confidence", 0.0))
        except (TypeError, ValueError):
            conf = 0.0
        if conf < CONFIDENCE_FLOOR:
            log.info("[interpret] dropped claim (low confidence=%.2f): %s", conf, text[:80])
            continue

        # evidences
        evs_raw = c.get("evidences") or []
        if not isinstance(evs_raw, list):
            evs_raw = []
        evidences: list[ClaimEvidenceDraft] = []
        for e in evs_raw:
            if not isinstance(e, dict):
                continue
            short = e.get("material_id")
            full = resolve_short_to_full(str(short or ""), arxiv_id)
            if not full or full not in allowed:
                log.info("[interpret] dropped evidence (not in allowed): %r", short)
                continue
            evidences.append(
                ClaimEvidenceDraft(material_id=full, relation=_coerce_relation(e.get("relation")))
            )
        if not evidences:
            log.warning("[interpret] dropped claim w/o valid cite: %s", text[:80])
            continue

        out.append(
            ClaimDraft(
                text=text,
                text_en=str(c.get("text_en") or ""),
                claim_type=_coerce_claim_type(c.get("claim_type")),
                source_section_path=str(c.get("source_section_path") or ""),
                confidence=conf,
                evidences=evidences,
            )
        )
    return out


def _parse_l2_signals(
    raw: dict[str, Any], arxiv_id: str, allowed: set[str], n_claims: int
) -> list[CounterSignalDraft]:
    """L2 后处理：claim_idx 校验 + cite 校验 + signal_type 校验."""
    out: list[CounterSignalDraft] = []
    items = raw.get("counter_signals") or []
    if not isinstance(items, list):
        log.warning("[interpret] L2 'counter_signals' not a list")
        return out

    for s in items:
        if not isinstance(s, dict):
            continue
        text = str(s.get("text") or "").strip()
        if not text:
            continue
        sig_type = _coerce_signal_type(s.get("signal_type"))
        if sig_type is None:
            log.info("[interpret] dropped signal (bad signal_type): %r", s.get("signal_type"))
            continue
        # claim_idx
        try:
            idx = int(s.get("claim_idx"))
        except (TypeError, ValueError):
            log.info("[interpret] dropped signal (claim_idx not int): %r", s.get("claim_idx"))
            continue
        if idx < 0 or idx >= n_claims:
            log.info("[interpret] dropped signal (claim_idx out of range): %d / %d", idx, n_claims)
            continue
        # cite
        full = resolve_short_to_full(str(s.get("evidence_material_id") or ""), arxiv_id)
        if not full or full not in allowed:
            log.info(
                "[interpret] dropped signal (cite not in allowed): %r",
                s.get("evidence_material_id"),
            )
            continue
        out.append(
            CounterSignalDraft(
                text=text,
                signal_type=sig_type,  # type: ignore[arg-type]
                evidence_material_id=full,
                claim_idx=idx,
            )
        )
    return out


def _claims_to_brief_dicts(claims: list[ClaimDraft]) -> list[dict[str, Any]]:
    """L2 prompt 用的简表：每条 claim 的 text + cite 简写."""
    out = []
    for c in claims:
        # 把 full material_id 反向缩为简写
        evs = []
        for ev in c.evidences:
            short = _full_to_short(ev.material_id)
            evs.append({"material_id": short or ev.material_id})
        out.append({"text": c.text, "evidences": evs})
    return out


def _full_to_short(material_id: str) -> str | None:
    """``2401.xxx:figure:3`` → ``[fig:3]``. 反向辅助 L2 prompt 渲染。"""
    from apps.interpret.catalog import _MID_RE, _TYPE_TO_SHORT

    m = _MID_RE.match(material_id)
    if not m:
        return None
    short = _TYPE_TO_SHORT.get(m.group("type"))
    if short is None:
        return None
    return f"[{short}:{m.group('seq')}]"


class DefaultInterpreter:
    """实现 ``apps.interpret.base.Interpreter`` Protocol."""

    def interpret(self, paper_arxiv_id: str, pdf_path: Path) -> InterpretResult:
        catalog, allowed = build_catalog(paper_arxiv_id)
        markdown = get_paper_markdown(paper_arxiv_id, Path(pdf_path))

        # ---- L1 ----
        try:
            raw_l1 = chat_json(
                system=L1_SYSTEM,
                user=L1_USER_TEMPLATE.format(catalog=catalog, markdown=markdown),
            )
        except LLMError as exc:
            log.error("[interpret] L1 LLM failed arxiv_id=%s: %r", paper_arxiv_id, exc)
            return InterpretResult(paper_arxiv_id=paper_arxiv_id, claims=[], counter_signals=[])

        claims = _parse_l1_claims(raw_l1, paper_arxiv_id, allowed)
        log.info(
            "[interpret] L1 done arxiv_id=%s claims_kept=%d",
            paper_arxiv_id, len(claims),
        )

        # ---- L2 ----
        signals: list[CounterSignalDraft] = []
        if claims:
            try:
                raw_l2 = chat_json(
                    system=L2_SYSTEM,
                    user=L2_USER_TEMPLATE.format(
                        catalog=catalog,
                        markdown=markdown,
                        claims_brief=render_claims_brief(_claims_to_brief_dicts(claims)),
                    ),
                )
                signals = _parse_l2_signals(raw_l2, paper_arxiv_id, allowed, len(claims))
            except LLMError as exc:
                log.warning("[interpret] L2 LLM failed arxiv_id=%s: %r", paper_arxiv_id, exc)

        log.info(
            "[interpret] L2 done arxiv_id=%s signals_kept=%d", paper_arxiv_id, len(signals),
        )
        return InterpretResult(
            paper_arxiv_id=paper_arxiv_id, claims=claims, counter_signals=signals,
        )
