"""ft-027: Subscription CRUD + Run-now endpoints。

设计
----
- 存储仍是 ``subscriptions.yaml``（不切 DB）。
- 用 ``subscriptions.loader.load_subscriptions / save_subscriptions``
  做 dict 级 round-trip（保留注释 / key 顺序）。
- ``name`` 字段是唯一 key。
- ``POST /run/`` 异步触发现有 ``run_subscription`` management command —— 用
  ``call_command`` 包装到 jobs queue 即可，业务逻辑零侵入。
"""
from __future__ import annotations

import logging
from pathlib import Path

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api import jobs
from apps.api.serializers import SubscriptionSerializer
from subscriptions.loader import load_subscriptions, save_subscriptions

log = logging.getLogger(__name__)


def _yaml_path() -> Path:
    """订阅 YAML 路径（项目根 / subscriptions.yaml）。

    可被 ``settings.SUBSCRIPTIONS_YAML`` 覆盖（test fixture 用）。
    """
    p = getattr(settings, "SUBSCRIPTIONS_YAML", None)
    return Path(p) if p else Path(settings.BASE_DIR) / "subscriptions.yaml"


def _read_subs() -> list[dict]:
    return load_subscriptions(_yaml_path())


def _write_subs(subs: list[dict]) -> None:
    save_subscriptions(_yaml_path(), subs)


def _find(subs: list[dict], name: str) -> int:
    for i, s in enumerate(subs):
        if s.get("name") == name:
            return i
    return -1


# ---------------- list / create ----------------

class SubscriptionListView(APIView):
    """GET → 列表；POST → 新建（name 唯一）。"""

    def get(self, request):
        subs = _read_subs()
        return Response(SubscriptionSerializer(subs, many=True).data)

    def post(self, request):
        ser = SubscriptionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        new = dict(ser.validated_data)
        subs = _read_subs()
        if _find(subs, new["name"]) >= 0:
            return Response(
                {"detail": f"subscription '{new['name']}' already exists"},
                status=status.HTTP_409_CONFLICT,
            )
        subs.append(new)
        _write_subs(subs)
        return Response(SubscriptionSerializer(new).data,
                        status=status.HTTP_201_CREATED)


# ---------------- detail / update / delete ----------------

class SubscriptionDetailView(APIView):
    def get(self, request, name: str):
        subs = _read_subs()
        idx = _find(subs, name)
        if idx < 0:
            return Response(
                {"detail": f"subscription '{name}' not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(SubscriptionSerializer(subs[idx]).data)

    def put(self, request, name: str):
        subs = _read_subs()
        idx = _find(subs, name)
        if idx < 0:
            return Response(
                {"detail": f"subscription '{name}' not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        ser = SubscriptionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        new = dict(ser.validated_data)
        # name 改名时检查冲突
        if new["name"] != name and _find(subs, new["name"]) >= 0:
            return Response(
                {"detail": f"name '{new['name']}' already used"},
                status=status.HTTP_409_CONFLICT,
            )
        subs[idx] = new
        _write_subs(subs)
        return Response(SubscriptionSerializer(new).data)

    def delete(self, request, name: str):
        subs = _read_subs()
        idx = _find(subs, name)
        if idx < 0:
            return Response(
                {"detail": f"subscription '{name}' not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        subs.pop(idx)
        _write_subs(subs)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------- run ----------------

def _do_run_subscription(name: str, yaml_path: str) -> dict:
    """job worker：调 management command run_subscription。"""
    from io import StringIO

    from django.core.management import call_command
    out = StringIO()
    err = StringIO()
    call_command(
        "run_subscription", name,
        yaml=yaml_path, stdout=out, stderr=err,
    )
    return {
        "name": name,
        "stdout_tail": out.getvalue()[-2000:],
        "stderr_tail": err.getvalue()[-2000:],
    }


class SubscriptionRunView(APIView):
    """POST → 立即跑这一条订阅（异步）。"""

    def post(self, request, name: str):
        subs = _read_subs()
        idx = _find(subs, name)
        if idx < 0:
            return Response(
                {"detail": f"subscription '{name}' not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        info = jobs.enqueue(
            _do_run_subscription, name, str(_yaml_path()),
            name=f"run-sub:{name}",
        )
        return Response(
            {"job_id": info.job_id, "status": info.status},
            status=status.HTTP_202_ACCEPTED,
        )
