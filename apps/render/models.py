"""ft-021: 渲染产物 ORM.

同库不同前缀：``render_*``。全 jsonb 走 ``JSONField``，无 PG-only 字段。
artifact_id 规则：``<arxiv_id>:graph_<format>``（例：``leworldmodel:graph_excalidraw``）。
"""
from __future__ import annotations

from django.db import models


class RenderArtifact(models.Model):
    artifact_id = models.CharField(max_length=128, primary_key=True)
    paper_arxiv_id = models.CharField(max_length=64, db_index=True)
    artifact_type = models.CharField(max_length=32)  # graph_excalidraw / graph_svg
    payload_path = models.CharField(max_length=512)
    payload_meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "render_artifacts"
