"""ft-020: DefaultInterpreter 单测 —— mock LLM + mock docling."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from apps.extract.models import Figure, Section, Table
from apps.interpret import interpreter as interp_mod
from apps.interpret.interpreter import DefaultInterpreter, _parse_l1_claims, _parse_l2_signals


pytestmark = pytest.mark.django_db


ARXIV_ID = "2401.55555"


@pytest.fixture
def seeded_paper():
    Section.objects.create(
        material_id=f"{ARXIV_ID}:section:1",
        paper_arxiv_id=ARXIV_ID, seq=1, path="Abstract", level=1,
    )
    Section.objects.create(
        material_id=f"{ARXIV_ID}:section:5",
        paper_arxiv_id=ARXIV_ID, seq=5, path="Limitations", level=1,
    )
    Figure.objects.create(
        material_id=f"{ARXIV_ID}:figure:1",
        paper_arxiv_id=ARXIV_ID, seq=1, page=2, caption="Figure 1: arch.",
    )
    Table.objects.create(
        material_id=f"{ARXIV_ID}:table:1",
        paper_arxiv_id=ARXIV_ID, seq=1, page=5, caption="Table 1: ablation.",
    )
    return ARXIV_ID


@pytest.fixture
def fake_doc(tmp_path):
    pdf = tmp_path / "fake.pdf"
    pdf.write_bytes(b"")
    doc = SimpleNamespace(export_to_markdown=lambda: "## Abstract\nWe propose X.")
    return pdf, doc


# ---------------- _parse_l1_claims ----------------

def test_l1_keeps_claim_with_valid_cite():
    arxiv = ARXIV_ID
    allowed = {f"{arxiv}:figure:1"}
    raw = {"claims": [{
        "text": "我们提出 X。",
        "claim_type": "proposal",
        "confidence": 0.9,
        "evidences": [{"material_id": "[fig:1]", "relation": "illustrates"}],
    }]}
    out = _parse_l1_claims(raw, arxiv, allowed)
    assert len(out) == 1
    assert out[0].evidences[0].material_id == f"{arxiv}:figure:1"
    assert out[0].evidences[0].relation == "illustrates"
    assert out[0].claim_type == "proposal"


def test_l1_drops_claim_with_invalid_cite():
    arxiv = ARXIV_ID
    allowed = {f"{arxiv}:figure:1"}
    raw = {"claims": [{
        "text": "我们提出 X。",
        "confidence": 0.9,
        "evidences": [{"material_id": "[fig:99]"}],  # 不在 allowed
    }]}
    assert _parse_l1_claims(raw, arxiv, allowed) == []


def test_l1_drops_claim_low_confidence():
    arxiv = ARXIV_ID
    allowed = {f"{arxiv}:figure:1"}
    raw = {"claims": [{
        "text": "X 也许有效。",
        "confidence": 0.3,
        "evidences": [{"material_id": "[fig:1]"}],
    }]}
    assert _parse_l1_claims(raw, arxiv, allowed) == []


def test_l1_drops_claim_no_evidence():
    arxiv = ARXIV_ID
    allowed = {f"{arxiv}:figure:1"}
    raw = {"claims": [{"text": "无 cite 的 claim。", "confidence": 0.9, "evidences": []}]}
    assert _parse_l1_claims(raw, arxiv, allowed) == []


def test_l1_invalid_claim_type_falls_back_to_result():
    arxiv = ARXIV_ID
    allowed = {f"{arxiv}:figure:1"}
    raw = {"claims": [{
        "text": "X.",
        "claim_type": "weird_type",
        "confidence": 0.7,
        "evidences": [{"material_id": "[fig:1]"}],
    }]}
    out = _parse_l1_claims(raw, arxiv, allowed)
    assert out[0].claim_type == "result"


def test_l1_handles_garbage_payload():
    assert _parse_l1_claims({}, ARXIV_ID, set()) == []
    assert _parse_l1_claims({"claims": "not_a_list"}, ARXIV_ID, set()) == []
    assert _parse_l1_claims({"claims": [None, "garbage", {}]}, ARXIV_ID, set()) == []


# ---------------- _parse_l2_signals ----------------

def test_l2_keeps_valid_signal():
    arxiv = ARXIV_ID
    allowed = {f"{arxiv}:section:5"}
    raw = {"counter_signals": [{
        "text": "限制：仅在 ImageNet 上验证。",
        "signal_type": "limitation",
        "evidence_material_id": "[§:5]",
        "claim_idx": 0,
    }]}
    out = _parse_l2_signals(raw, arxiv, allowed, n_claims=1)
    assert len(out) == 1
    assert out[0].evidence_material_id == f"{arxiv}:section:5"
    assert out[0].claim_idx == 0


def test_l2_drops_signal_claim_idx_out_of_range():
    arxiv = ARXIV_ID
    allowed = {f"{arxiv}:section:5"}
    raw = {"counter_signals": [{
        "text": "x", "signal_type": "limitation",
        "evidence_material_id": "[§:5]", "claim_idx": 5,
    }]}
    assert _parse_l2_signals(raw, arxiv, allowed, n_claims=1) == []


def test_l2_drops_signal_negative_claim_idx():
    arxiv = ARXIV_ID
    allowed = {f"{arxiv}:section:5"}
    raw = {"counter_signals": [{
        "text": "x", "signal_type": "limitation",
        "evidence_material_id": "[§:5]", "claim_idx": -1,
    }]}
    assert _parse_l2_signals(raw, arxiv, allowed, n_claims=2) == []


def test_l2_drops_signal_evidence_not_in_allowed():
    arxiv = ARXIV_ID
    allowed = {f"{arxiv}:section:5"}
    raw = {"counter_signals": [{
        "text": "x", "signal_type": "limitation",
        "evidence_material_id": "[§:99]", "claim_idx": 0,
    }]}
    assert _parse_l2_signals(raw, arxiv, allowed, n_claims=1) == []


def test_l2_drops_signal_bad_signal_type():
    arxiv = ARXIV_ID
    allowed = {f"{arxiv}:section:5"}
    raw = {"counter_signals": [{
        "text": "x", "signal_type": "weird",
        "evidence_material_id": "[§:5]", "claim_idx": 0,
    }]}
    assert _parse_l2_signals(raw, arxiv, allowed, n_claims=1) == []


def test_l2_drops_signal_non_int_idx():
    arxiv = ARXIV_ID
    allowed = {f"{arxiv}:section:5"}
    raw = {"counter_signals": [{
        "text": "x", "signal_type": "limitation",
        "evidence_material_id": "[§:5]", "claim_idx": "zero",
    }]}
    assert _parse_l2_signals(raw, arxiv, allowed, n_claims=1) == []


# ---------------- end-to-end DefaultInterpreter ----------------

def test_interpret_end_to_end(seeded_paper, fake_doc):
    pdf, doc = fake_doc

    l1_payload = {"claims": [{
        "text": "我们提出 X，效果优于 baseline。",
        "claim_type": "result",
        "source_section_path": "Abstract",
        "confidence": 0.85,
        "evidences": [{"material_id": "[fig:1]", "relation": "illustrates"}],
    }]}
    l2_payload = {"counter_signals": [{
        "text": "限制：未在 video 上验证。",
        "signal_type": "limitation",
        "evidence_material_id": "[§:5]",
        "claim_idx": 0,
    }]}

    call_log = []

    def fake_chat_json(*, system, user, **kw):
        call_log.append(system[:10])
        if "论文逻辑还原" in system:
            return l1_payload
        return l2_payload

    with patch.object(interp_mod, "chat_json", side_effect=fake_chat_json), \
         patch("apps.extract.extractors.docling_ext._convert", return_value=doc):
        result = DefaultInterpreter().interpret(seeded_paper, Path(pdf))

    assert result.paper_arxiv_id == seeded_paper
    assert len(result.claims) == 1
    assert result.claims[0].evidences[0].material_id == f"{seeded_paper}:figure:1"
    assert len(result.counter_signals) == 1
    assert result.counter_signals[0].claim_idx == 0
    assert result.counter_signals[0].evidence_material_id == f"{seeded_paper}:section:5"
    # Both LLM calls were made
    assert len(call_log) == 2


def test_interpret_skips_l2_when_no_claims(seeded_paper, fake_doc):
    pdf, doc = fake_doc
    n_calls = {"n": 0}

    def fake_chat_json(*, system, user, **kw):
        n_calls["n"] += 1
        # L1 returns nothing usable
        return {"claims": []}

    with patch.object(interp_mod, "chat_json", side_effect=fake_chat_json), \
         patch("apps.extract.extractors.docling_ext._convert", return_value=doc):
        result = DefaultInterpreter().interpret(seeded_paper, Path(pdf))

    assert result.claims == []
    assert result.counter_signals == []
    assert n_calls["n"] == 1  # L2 skipped


def test_interpret_l1_llm_error_returns_empty(seeded_paper, fake_doc):
    from interpret.llm import LLMError
    pdf, doc = fake_doc

    with patch.object(interp_mod, "chat_json", side_effect=LLMError("boom")), \
         patch("apps.extract.extractors.docling_ext._convert", return_value=doc):
        result = DefaultInterpreter().interpret(seeded_paper, Path(pdf))
    assert result.claims == []
    assert result.counter_signals == []


def test_interpret_truncates_long_markdown(seeded_paper, tmp_path):
    pdf = tmp_path / "fake.pdf"
    pdf.write_bytes(b"")
    huge = "x" * 50_000
    doc = SimpleNamespace(export_to_markdown=lambda: huge)

    captured_user = {"text": ""}

    def fake_chat_json(*, system, user, **kw):
        captured_user["text"] = user
        return {"claims": []}

    with patch.object(interp_mod, "chat_json", side_effect=fake_chat_json), \
         patch("apps.extract.extractors.docling_ext._convert", return_value=doc):
        DefaultInterpreter().interpret(seeded_paper, Path(pdf))

    # markdown 应被截到 30K
    assert "x" * 30_000 in captured_user["text"]
    assert "x" * 30_001 not in captured_user["text"]
