"""Material DTOs (Section / Figure / Table / Citation).

Equation lives in ``equations.py`` (split out for ft-034 P0-6 — review-D D1
补字段时该文件单独迭代)。
"""
from __future__ import annotations

from rest_framework import serializers

from apps.extract.models import Citation, Figure, Section, Table


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


class CitationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Citation
        fields = (
            "material_id", "paper_arxiv_id", "seq", "bibkey",
            "raw_text", "title", "year",
        )
