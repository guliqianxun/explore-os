"""ft-027 Subscription serializers — loader-shape (not bound to ORM)."""
from __future__ import annotations

from rest_framework import serializers


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
