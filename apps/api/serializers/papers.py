"""Paper-list item + user_* layer (Comment / Backlink) DTOs."""
from __future__ import annotations

from rest_framework import serializers


class PaperListItemSerializer(serializers.Serializer):
    """ft-028 PaperListItem DTO（contracts 已 lock，frontend agent 依赖）.

    arxiv_id 兼容保留；新增 paper_key / title / status / tags / n_comments。
    ft-033 加 brief 短字段（list 视图避 N+1）。
    """
    arxiv_id = serializers.CharField(allow_null=True, required=False)
    paper_key = serializers.CharField()
    title = serializers.CharField(allow_blank=True)
    status = serializers.CharField()
    tags = serializers.ListField(child=serializers.CharField())
    n_comments = serializers.IntegerField()
    n_sections = serializers.IntegerField()
    n_figures = serializers.IntegerField()
    n_tables = serializers.IntegerField()
    n_claims = serializers.IntegerField()
    # ft-033: brief 短字段（list 视图用 — 不展开完整 PaperBrief，避 N+1）
    tldr_zh = serializers.CharField(allow_blank=True, default="")
    abstract_zh = serializers.CharField(allow_blank=True, default="")
    # 语义：作者 keywords（paper.keywords），不是 brief.keywords (LLM 抽)。
    # brief.keywords 仍可由 detail 页 brief 子对象访问。
    keywords = serializers.ListField(
        child=serializers.CharField(), default=list,
    )
    # LLM 抽的综述 keywords（chip 主源，paper.keywords 空时 fallback）
    brief_keywords = serializers.ListField(
        child=serializers.CharField(), default=list,
    )
    # AI summary 卡用：brief.key_innovation 前 2 条
    key_innovation = serializers.ListField(
        child=serializers.CharField(), default=list,
    )
    has_brief = serializers.BooleanField(default=False)
    abstract_en = serializers.CharField(allow_blank=True, default="")


class CommentSerializer(serializers.Serializer):
    """append-only comment DTO."""
    id = serializers.IntegerField()
    text = serializers.CharField()
    created_at = serializers.DateTimeField()
    hidden = serializers.BooleanField()


class _BacklinkOutSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    dst_key = serializers.CharField()
    dst_title = serializers.CharField(allow_blank=True)
    relation = serializers.CharField(allow_blank=True)
    note = serializers.CharField(allow_blank=True)
    created_at = serializers.DateTimeField()


class _BacklinkInSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    src_key = serializers.CharField()
    src_title = serializers.CharField(allow_blank=True)
    relation = serializers.CharField(allow_blank=True)
    note = serializers.CharField(allow_blank=True)
    created_at = serializers.DateTimeField()


class BacklinkSerializer(serializers.Serializer):
    """ft-028 Backlink 双向 DTO（contracts locked）."""
    outgoing = _BacklinkOutSerializer(many=True)
    incoming = _BacklinkInSerializer(many=True)
