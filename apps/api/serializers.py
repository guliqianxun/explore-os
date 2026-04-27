"""ft-022: DRF serializers — 只读视图，反规范化已 extract / interpret 的产物。"""
from __future__ import annotations

from rest_framework import serializers

from apps.extract.models import Citation, Equation, Figure, Section, Table
from apps.interpret.models import Claim, ClaimEvidence, CounterSignal


class SectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Section
        fields = (
            "material_id", "paper_arxiv_id", "seq", "path", "level",
            "char_offset_start", "char_offset_end", "raw_text",
        )


class FigureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Figure
        fields = (
            "material_id", "paper_arxiv_id", "seq", "fig_label", "page",
            "bbox", "caption", "image_path",
        )


class TableSerializer(serializers.ModelSerializer):
    class Meta:
        model = Table
        fields = (
            "material_id", "paper_arxiv_id", "seq", "tbl_label", "page",
            "bbox", "caption", "raw_text",
        )


class EquationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Equation
        fields = (
            "material_id", "paper_arxiv_id", "seq", "eq_label", "page",
            "bbox", "latex_or_text", "inline_or_display",
        )


class CitationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Citation
        fields = (
            "material_id", "paper_arxiv_id", "seq", "bibkey",
            "raw_text", "title", "year",
        )


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


class PaperListItemSerializer(serializers.Serializer):
    arxiv_id = serializers.CharField()
    n_sections = serializers.IntegerField()
    n_figures = serializers.IntegerField()
    n_tables = serializers.IntegerField()
    n_claims = serializers.IntegerField()


# ---------------- ft-027: Subscription ----------------

class _SourceSerializer(serializers.Serializer):
    key = serializers.CharField()
    params = serializers.DictField(required=False, default=dict)


class _DeliverySerializer(serializers.Serializer):
    channel = serializers.CharField(default="email")
    to = serializers.CharField(required=False, allow_blank=True, default="")
    depth = serializers.CharField(required=False, allow_blank=True, default="tldr")
    schedule = serializers.CharField(required=False, allow_blank=True, default="")
    max_items = serializers.IntegerField(required=False, default=15)


class _PerspectiveSerializer(serializers.Serializer):
    preset = serializers.CharField(required=False, allow_blank=True, default="")
    custom = serializers.CharField(required=False, allow_blank=True, default="")


class SubscriptionSerializer(serializers.Serializer):
    """订阅 dict 序列化（loader 维度，不绑 dataclass / DB）。"""
    name = serializers.CharField()
    enabled = serializers.BooleanField(required=False, default=True)
    interests = serializers.ListField(
        child=serializers.CharField(allow_blank=False), required=False, default=list,
    )
    exclude = serializers.ListField(
        child=serializers.CharField(allow_blank=False), required=False, default=list,
    )
    sources = _SourceSerializer(many=True, required=False, default=list)
    deliveries = _DeliverySerializer(many=True, required=False, default=list)
    perspective = _PerspectiveSerializer(required=False, default=dict)


class JobSerializer(serializers.Serializer):
    job_id = serializers.CharField()
    name = serializers.CharField()
    status = serializers.CharField()
    created_at = serializers.CharField()
    started_at = serializers.CharField(allow_blank=True)
    finished_at = serializers.CharField(allow_blank=True)
    result = serializers.JSONField(required=False, allow_null=True)
    error = serializers.CharField(allow_blank=True)
