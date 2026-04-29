"""ft-034 P0-6 + review-B D5: JobSerializer with canonical 5-value status enum.

Old in-memory job status was 4 values (``queued | running | succeeded |
failed``). Spec lock 把 enum 收敛到 5 值（``pending | running | done | failed
| cancelled``）— 沿用 industry-standard naming + 给 P1+ async cancel 留位。

Backend mapping（DTO 边界）:
    queued    → pending   (老 dataclass 仍写 queued，DTO 翻译)
    succeeded → done

老值在 1 sprint 过渡期内仍接受，再删（v1.3 iter-020）。前端
``normalizeJobStatus`` 同步做反向兜底。
"""
from __future__ import annotations

import logging

from rest_framework import serializers

log = logging.getLogger(__name__)

JOB_STATUS_CHOICES = ("pending", "running", "done", "failed", "cancelled")

# 老 → 新 字面量映射（serialize 出口处做）
_LEGACY_MAP = {
    "queued": "pending",
    "succeeded": "done",
}


def normalize_job_status(raw: str) -> str:
    """老值 → 新 5 值 enum；未识别值原样返回（让 ChoiceField 报错）。"""
    if raw in _LEGACY_MAP:
        log.debug("[jobs] mapping legacy status %r → %r", raw, _LEGACY_MAP[raw])
        return _LEGACY_MAP[raw]
    return raw


class JobSerializer(serializers.Serializer):
    """In-memory job DTO. ``Job`` 当前是 dataclass（``apps.api.jobs.JobInfo``)，
    不是 ORM model — 所以这里走 ``Serializer`` + 字段平铺，不是 ModelSerializer。
    """
    job_id = serializers.CharField()
    name = serializers.CharField()
    status = serializers.ChoiceField(choices=JOB_STATUS_CHOICES)
    created_at = serializers.CharField()
    started_at = serializers.CharField(allow_blank=True)
    finished_at = serializers.CharField(allow_blank=True)
    result = serializers.JSONField(required=False, allow_null=True)
    error = serializers.CharField(allow_blank=True)

    def to_internal_value(self, data):
        # serialize 入口翻译老字面量，让 ChoiceField 不会因为老 dict 直接报错
        if isinstance(data, dict) and "status" in data:
            data = dict(data)
            data["status"] = normalize_job_status(data.get("status") or "")
        return super().to_internal_value(data)

    def to_representation(self, instance):
        # 兜底：如果 instance 来自 dataclass.__dict__ / 外部 dict，包含老值
        if isinstance(instance, dict) and "status" in instance:
            instance = dict(instance)
            instance["status"] = normalize_job_status(instance.get("status") or "")
        return super().to_representation(instance)
