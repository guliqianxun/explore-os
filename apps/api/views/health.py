"""Sidecar health endpoint (Electron 启动用)."""
from __future__ import annotations

from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core import paths


class HealthView(APIView):
    """sidecar 健康检查（Electron 启动用）。"""

    def get(self, request):
        from apps.core.scheduler import get_scheduler
        s = get_scheduler()
        return Response({
            "status": "ok",
            "scheduler_running": s.running,
            "data_dir": str(paths.data_dir()),
        })
