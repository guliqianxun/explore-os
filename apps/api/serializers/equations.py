"""ft-034 P0-6 + review-D D1: EquationSerializer.

Old PaperDetailView 在内联 dict 里手写 equations，缺 ``paper_arxiv_id`` /
``eq_label`` / ``bbox`` 字段（review-D D1 hotspot）；这里复用 ModelSerializer
+ 全字段，让前端 EquationDTO 与后端真正一致。
"""
from __future__ import annotations

from rest_framework import serializers

from apps.extract.models import Equation


class EquationSerializer(serializers.ModelSerializer):
    """Full equation DTO — includes paper_arxiv_id / eq_label / bbox.

    bbox 在 model 上是 ``JSONField(null=True)``，前端按 ``[x0,y0,x1,y1] | null``
    消费。eq_label 也允许 null（不是所有抽取器都给 label）。
    """

    class Meta:
        model = Equation
        fields = (
            "material_id",
            "paper_arxiv_id",
            "seq",
            "eq_label",
            "page",
            "bbox",
            "latex_or_text",
            "inline_or_display",
        )
