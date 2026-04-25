"""ft-019: 五类 material 的 Django ORM 模型.

同库不同前缀：``extract_*`` 表前缀（不用 PG schema），兼容未来 SQLite 切换。
所有 jsonb 走 ``JSONField``，禁用 PG-only 字段（ArrayField / tsvector）。
"""
from __future__ import annotations

from django.db import models


class Section(models.Model):
    material_id = models.CharField(max_length=255, primary_key=True)
    paper_arxiv_id = models.CharField(max_length=64, db_index=True)
    seq = models.IntegerField()
    path = models.CharField(max_length=255, blank=True, default="")
    level = models.IntegerField(default=0)
    char_offset_start = models.IntegerField(default=0)
    char_offset_end = models.IntegerField(default=0)
    raw_text = models.TextField(blank=True, default="")
    raw_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "extract_sections"
        indexes = [models.Index(fields=["paper_arxiv_id", "seq"])]


class Figure(models.Model):
    material_id = models.CharField(max_length=255, primary_key=True)
    paper_arxiv_id = models.CharField(max_length=64, db_index=True)
    seq = models.IntegerField()
    fig_label = models.CharField(max_length=64, blank=True, default="")
    page = models.IntegerField(default=0)
    bbox = models.JSONField(null=True, blank=True)  # list[float] or null
    caption = models.TextField(blank=True, default="")
    image_path = models.CharField(max_length=512, blank=True, default="")
    raw_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "extract_figures"
        indexes = [models.Index(fields=["paper_arxiv_id", "seq"])]


class Table(models.Model):
    material_id = models.CharField(max_length=255, primary_key=True)
    paper_arxiv_id = models.CharField(max_length=64, db_index=True)
    seq = models.IntegerField()
    tbl_label = models.CharField(max_length=64, blank=True, default="")
    page = models.IntegerField(default=0)
    bbox = models.JSONField(null=True, blank=True)
    caption = models.TextField(blank=True, default="")
    raw_text = models.TextField(blank=True, default="")
    raw_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "extract_tables"
        indexes = [models.Index(fields=["paper_arxiv_id", "seq"])]


class Equation(models.Model):
    material_id = models.CharField(max_length=255, primary_key=True)
    paper_arxiv_id = models.CharField(max_length=64, db_index=True)
    seq = models.IntegerField()
    eq_label = models.CharField(max_length=64, null=True, blank=True)
    page = models.IntegerField(default=0)
    bbox = models.JSONField(null=True, blank=True)
    latex_or_text = models.TextField(blank=True, default="")
    inline_or_display = models.CharField(max_length=16, default="display")
    raw_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "extract_equations"
        indexes = [models.Index(fields=["paper_arxiv_id", "seq"])]


class Citation(models.Model):
    material_id = models.CharField(max_length=255, primary_key=True)
    paper_arxiv_id = models.CharField(max_length=64, db_index=True)
    seq = models.IntegerField()
    bibkey = models.CharField(max_length=128, blank=True, default="")
    raw_text = models.TextField(blank=True, default="")
    title = models.CharField(max_length=512, blank=True, default="")
    year = models.IntegerField(null=True, blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "extract_citations"
        indexes = [models.Index(fields=["paper_arxiv_id", "seq"])]
