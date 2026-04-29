"""Claim + ClaimEvidence + CounterSignal DTOs."""
from __future__ import annotations

from rest_framework import serializers

from apps.interpret.models import Claim, ClaimEvidence, CounterSignal


class ClaimEvidenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClaimEvidence
        fields = ("material_id", "relation")


class CounterSignalSerializer(serializers.ModelSerializer):
    class Meta:
        model = CounterSignal
        fields = (
            "signal_id", "text", "signal_type", "evidence_material_id",
        )


class ClaimSerializer(serializers.ModelSerializer):
    evidences = ClaimEvidenceSerializer(many=True, read_only=True)
    counter_signals = CounterSignalSerializer(many=True, read_only=True)

    class Meta:
        model = Claim
        fields = (
            "claim_id", "paper_arxiv_id", "text", "text_en", "claim_type",
            "source_section_path", "confidence",
            "evidences", "counter_signals",
        )
