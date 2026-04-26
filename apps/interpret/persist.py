"""ft-020: InterpretResult → DB 落库.

幂等：``update_or_create`` by primary key。同 paper 多次 persist 行数不变。
claim_id 规则：``<arxiv_id>:claim:<seq>``（seq 从 1 开始，按 result.claims 顺序）
signal_id 规则：``<arxiv_id>:signal:<seq>``
"""
from __future__ import annotations

import logging
from dataclasses import asdict

from django.db import transaction

from apps.interpret.base import InterpretResult
from apps.interpret.models import Claim, ClaimEvidence, CounterSignal

log = logging.getLogger(__name__)


@transaction.atomic
def persist_result(result: InterpretResult) -> dict[str, int]:
    """落库 InterpretResult。返回各表 upsert 计数。"""
    arxiv_id = result.paper_arxiv_id

    # 删除该 paper 旧 evidence/signal 行（保留 Claim 主行做 update_or_create）
    # 这是为了避免「上一次跑出 5 条 evidence，本次只剩 3 条」时残留旧行。
    # Claim 主键稳定（按 seq），孤儿 claim 也清掉。
    existing_claim_ids = list(
        Claim.objects.filter(paper_arxiv_id=arxiv_id).values_list("claim_id", flat=True)
    )
    if existing_claim_ids:
        ClaimEvidence.objects.filter(claim_id__in=existing_claim_ids).delete()
        CounterSignal.objects.filter(claim_id__in=existing_claim_ids).delete()

    new_claim_ids: list[str] = []
    n_claims = 0
    n_evidence = 0
    for seq, c in enumerate(result.claims, start=1):
        claim_id = f"{arxiv_id}:claim:{seq}"
        new_claim_ids.append(claim_id)
        Claim.objects.update_or_create(
            claim_id=claim_id,
            defaults={
                "paper_arxiv_id": arxiv_id,
                "text": c.text,
                "text_en": c.text_en,
                "claim_type": c.claim_type,
                "source_section_path": c.source_section_path,
                "confidence": c.confidence,
                "raw_payload": {"evidences": [asdict(e) for e in c.evidences]},
            },
        )
        n_claims += 1
        for ev in c.evidences:
            ClaimEvidence.objects.update_or_create(
                claim_id=claim_id,
                material_id=ev.material_id,
                defaults={"relation": ev.relation},
            )
            n_evidence += 1

    # 清理孤儿 claim（之前存在但本次不再产出）
    stale = set(existing_claim_ids) - set(new_claim_ids)
    if stale:
        Claim.objects.filter(claim_id__in=stale).delete()

    n_signals = 0
    for seq, s in enumerate(result.counter_signals, start=1):
        # claim_idx 在 interpreter 层已校验在 [0, len(claims))
        if s.claim_idx < 0 or s.claim_idx >= len(new_claim_ids):
            log.warning("[persist] skip signal w/ bad claim_idx: %d", s.claim_idx)
            continue
        signal_id = f"{arxiv_id}:signal:{seq}"
        CounterSignal.objects.update_or_create(
            signal_id=signal_id,
            defaults={
                "claim_id": new_claim_ids[s.claim_idx],
                "text": s.text,
                "signal_type": s.signal_type,
                "evidence_material_id": s.evidence_material_id,
                "raw_payload": {},
            },
        )
        n_signals += 1

    log.info(
        "[persist] arxiv_id=%s claims=%d evidence=%d signals=%d",
        arxiv_id, n_claims, n_evidence, n_signals,
    )
    return {"claims": n_claims, "evidence": n_evidence, "signals": n_signals}
