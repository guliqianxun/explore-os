"""ft-020: persist 测试 —— 幂等性 + 关联表正确写入."""
from __future__ import annotations

import pytest

from apps.interpret.base import (
    ClaimDraft,
    ClaimEvidenceDraft,
    CounterSignalDraft,
    InterpretResult,
)
from apps.interpret.models import Claim, ClaimEvidence, CounterSignal
from apps.interpret.persist import persist_result


pytestmark = pytest.mark.django_db


ARXIV_ID = "2401.77001"


def _make_result(*, n_claims: int = 2, n_signals: int = 1) -> InterpretResult:
    claims = []
    for i in range(n_claims):
        claims.append(ClaimDraft(
            text=f"claim {i}",
            claim_type="result",
            confidence=0.8,
            evidences=[ClaimEvidenceDraft(
                material_id=f"{ARXIV_ID}:figure:{i + 1}", relation="illustrates",
            )],
        ))
    signals = [
        CounterSignalDraft(
            text=f"signal {i}",
            signal_type="limitation",
            evidence_material_id=f"{ARXIV_ID}:section:5",
            claim_idx=0,
        )
        for i in range(n_signals)
    ]
    return InterpretResult(paper_arxiv_id=ARXIV_ID, claims=claims, counter_signals=signals)


def test_persist_writes_all_rows():
    result = _make_result(n_claims=2, n_signals=1)
    counts = persist_result(result)

    assert counts == {"claims": 2, "evidence": 2, "signals": 1}
    assert Claim.objects.filter(paper_arxiv_id=ARXIV_ID).count() == 2
    assert ClaimEvidence.objects.count() == 2
    assert CounterSignal.objects.count() == 1


def test_persist_idempotent_same_input():
    """连续 persist 同一 result，行数不变。"""
    result = _make_result(n_claims=3, n_signals=2)
    persist_result(result)
    persist_result(result)
    persist_result(result)

    assert Claim.objects.filter(paper_arxiv_id=ARXIV_ID).count() == 3
    assert ClaimEvidence.objects.count() == 3 * 1  # 每 claim 1 evidence
    assert CounterSignal.objects.count() == 2


def test_persist_claim_id_pattern():
    persist_result(_make_result(n_claims=2, n_signals=0))
    ids = sorted(Claim.objects.values_list("claim_id", flat=True))
    assert ids == [f"{ARXIV_ID}:claim:1", f"{ARXIV_ID}:claim:2"]


def test_persist_signal_id_pattern_and_link():
    persist_result(_make_result(n_claims=1, n_signals=2))
    sigs = list(CounterSignal.objects.order_by("signal_id"))
    assert [s.signal_id for s in sigs] == [
        f"{ARXIV_ID}:signal:1", f"{ARXIV_ID}:signal:2",
    ]
    assert all(s.claim_id == f"{ARXIV_ID}:claim:1" for s in sigs)


def test_persist_drops_orphan_claims_on_rerun():
    """第二次跑 claim 数变少，旧 claim 被清掉。"""
    persist_result(_make_result(n_claims=4, n_signals=0))
    assert Claim.objects.filter(paper_arxiv_id=ARXIV_ID).count() == 4

    persist_result(_make_result(n_claims=2, n_signals=0))
    assert Claim.objects.filter(paper_arxiv_id=ARXIV_ID).count() == 2


def test_persist_skips_signal_with_bad_claim_idx():
    """interpreter 层正常已过滤；persist 双保险."""
    result = _make_result(n_claims=1, n_signals=0)
    result.counter_signals.append(CounterSignalDraft(
        text="bad", signal_type="limitation",
        evidence_material_id=f"{ARXIV_ID}:section:5", claim_idx=99,
    ))
    counts = persist_result(result)
    assert counts["signals"] == 0
    assert CounterSignal.objects.count() == 0


def test_persist_evidence_unique_constraint():
    """同 claim 同 material_id 不能重复写入（unique_together）。
    update_or_create 应当替换 relation 而非新增。"""
    result = _make_result(n_claims=1, n_signals=0)
    persist_result(result)
    # 同一 evidence 但 relation 不同
    result.claims[0].evidences[0].relation = "quantifies"
    persist_result(result)

    assert ClaimEvidence.objects.count() == 1
    assert ClaimEvidence.objects.first().relation == "quantifies"
