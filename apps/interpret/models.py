"""ft-020: 解读层三表 ORM.

同库不同前缀：``interpret_*``。全 jsonb 走 ``JSONField``，无 PG-only 字段。
"""
from __future__ import annotations

from django.db import models


class Claim(models.Model):
    claim_id = models.CharField(max_length=128, primary_key=True)  # <arxiv_id>:claim:<seq>
    paper_arxiv_id = models.CharField(max_length=64, db_index=True)
    text = models.TextField()
    text_en = models.TextField(blank=True, default="")
    claim_type = models.CharField(max_length=32)
    source_section_path = models.CharField(max_length=512, blank=True, default="")
    confidence = models.FloatField(default=0.0)
    raw_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "interpret_claims"


class ClaimEvidence(models.Model):
    claim = models.ForeignKey(Claim, on_delete=models.CASCADE, related_name="evidences")
    material_id = models.CharField(max_length=128, db_index=True)
    relation = models.CharField(max_length=32, default="supports")

    class Meta:
        db_table = "interpret_claim_evidence"
        unique_together = [("claim", "material_id")]


class CounterSignal(models.Model):
    signal_id = models.CharField(max_length=128, primary_key=True)  # <arxiv_id>:signal:<seq>
    claim = models.ForeignKey(Claim, on_delete=models.CASCADE, related_name="counter_signals")
    text = models.TextField()
    signal_type = models.CharField(max_length=32)
    evidence_material_id = models.CharField(max_length=128, db_index=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "interpret_counter_signals"
