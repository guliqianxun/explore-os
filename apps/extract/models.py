"""ft-019 + ft-028: 五类 material 的 Django ORM 模型.

ft-019 引入；ft-028 在所有 5 类表上加 ``paper = ForeignKey(Paper)``，把
``paper_arxiv_id``（CharField）降级为 deprecated 兼容列（下个 ft 删）。
查询路径既可以走 ``paper_arxiv_id``（既有 view），也可以走 ``paper.arxiv_id``。
保持 SQLite 友好：jsonb 走 ``JSONField``，禁用 PG-only 字段。
"""
from __future__ import annotations

from django.db import models


class Section(models.Model):
    material_id = models.CharField(max_length=255, primary_key=True)
    # ft-028: deprecated, 留兼容到下个 ft；新代码请用 ``paper.arxiv_id``
    paper_arxiv_id = models.CharField(max_length=64, db_index=True)
    paper = models.ForeignKey(
        "papers.Paper", on_delete=models.CASCADE, related_name="sections",
    )
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
    paper = models.ForeignKey(
        "papers.Paper", on_delete=models.CASCADE, related_name="figures",
    )
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
    paper = models.ForeignKey(
        "papers.Paper", on_delete=models.CASCADE, related_name="tables",
    )
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
    paper = models.ForeignKey(
        "papers.Paper", on_delete=models.CASCADE, related_name="equations",
    )
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
    paper = models.ForeignKey(
        "papers.Paper", on_delete=models.CASCADE, related_name="citations",
    )
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
