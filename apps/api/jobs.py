"""ft-022: 极简 in-memory job queue（基于 APScheduler one-shot job）。

设计
----

每个 ``enqueue(func, *args, **kwargs)`` 返回 ``job_id``，立即在 background
scheduler 上注册一个 ``run_date=now`` 的 one-shot job。状态保存在进程内
``_JOBS`` dict（DRF 单进程下足够；后续真集群再考虑 broker）。

状态机：``queued → running → succeeded | failed``。
"""
from __future__ import annotations

import logging
import threading
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from apps.core.scheduler import get_scheduler, start_scheduler

log = logging.getLogger(__name__)


@dataclass
class JobInfo:
    job_id: str
    name: str
    status: str = "queued"  # queued | running | succeeded | failed
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: str = ""
    finished_at: str = ""
    result: Any = None
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "name": self.name,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "result": self.result,
            "error": self.error,
        }


_JOBS: dict[str, JobInfo] = {}
_LOCK = threading.Lock()


def get_job(job_id: str) -> JobInfo | None:
    with _LOCK:
        return _JOBS.get(job_id)


def list_jobs() -> list[JobInfo]:
    with _LOCK:
        return list(_JOBS.values())


def _set_status(job_id: str, **fields) -> None:
    with _LOCK:
        info = _JOBS.get(job_id)
        if info is None:
            return
        for k, v in fields.items():
            setattr(info, k, v)


def _wrap(job_id: str, func: Callable, args: tuple, kwargs: dict) -> None:
    _set_status(
        job_id,
        status="running",
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    try:
        result = func(*args, **kwargs)
        _set_status(
            job_id,
            status="succeeded",
            finished_at=datetime.now(timezone.utc).isoformat(),
            result=result if _json_safe(result) else str(result),
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("[jobs] %s raised", job_id)
        _set_status(
            job_id,
            status="failed",
            finished_at=datetime.now(timezone.utc).isoformat(),
            error=f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}",
        )


def _json_safe(v: Any) -> bool:
    import json
    try:
        json.dumps(v)
        return True
    except Exception:  # noqa: BLE001
        return False


def enqueue(func: Callable, *args, name: str = "", **kwargs) -> JobInfo:
    """提交任务到 background scheduler，立即返回 JobInfo。"""
    job_id = uuid.uuid4().hex[:16]
    info = JobInfo(job_id=job_id, name=name or getattr(func, "__name__", "job"))
    with _LOCK:
        _JOBS[job_id] = info
    start_scheduler()
    sched = get_scheduler()
    sched.add_job(
        _wrap,
        args=(job_id, func, args, kwargs),
        id=f"job-{job_id}",
        misfire_grace_time=60,
    )
    log.info("[jobs] enqueued %s name=%s", job_id, info.name)
    return info


def run_inline(func: Callable, *args, name: str = "", **kwargs) -> JobInfo:
    """同步执行（测试 / mock 模式用），状态机仍走完。"""
    job_id = uuid.uuid4().hex[:16]
    info = JobInfo(job_id=job_id, name=name or getattr(func, "__name__", "job"))
    with _LOCK:
        _JOBS[job_id] = info
    _wrap(job_id, func, args, kwargs)
    return _JOBS[job_id]


def reset_for_tests() -> None:
    with _LOCK:
        _JOBS.clear()
