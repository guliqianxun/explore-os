"""ft-022: in-process APScheduler 单例。

为 Electron sidecar 提供调度能力，无需依赖系统 cron / 外部 broker。
任务函数内部需自行用 ``transaction.atomic()``（Django ORM thread safety）。

API
---
* ``get_scheduler()`` — lazy 单例
* ``start_scheduler()`` — 启动（idempotent）
* ``shutdown_scheduler()`` — 关闭（idempotent）
* ``register_default_jobs()`` — 注册默认 jobs（占位；具体 job 由调用方追加）
"""
from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # 仅为类型注解，运行时不强制依赖 apscheduler
    from apscheduler.schedulers.background import BackgroundScheduler

log = logging.getLogger(__name__)

_SCHEDULER: "BackgroundScheduler | None" = None
_LOCK = threading.Lock()


def get_scheduler() -> "BackgroundScheduler":
    """返回 in-process 单例 BackgroundScheduler。Lazy 构造。"""
    global _SCHEDULER
    if _SCHEDULER is not None:
        return _SCHEDULER
    with _LOCK:
        if _SCHEDULER is not None:
            return _SCHEDULER
        from apscheduler.schedulers.background import BackgroundScheduler
        _SCHEDULER = BackgroundScheduler(timezone="Asia/Shanghai")
        log.info("[scheduler] BackgroundScheduler created")
        return _SCHEDULER


def start_scheduler() -> None:
    """启动 scheduler；已运行则 noop。"""
    s = get_scheduler()
    if not s.running:
        s.start()
        log.info("[scheduler] started")


def shutdown_scheduler(wait: bool = False) -> None:
    """关闭 scheduler；未运行则 noop。"""
    global _SCHEDULER
    s = _SCHEDULER
    if s is None:
        return
    if s.running:
        try:
            s.shutdown(wait=wait)
            log.info("[scheduler] shutdown")
        except Exception as exc:  # noqa: BLE001
            log.warning("[scheduler] shutdown raised: %r", exc)
    _SCHEDULER = None


def register_default_jobs() -> None:
    """注册默认 jobs。

    MVP 阶段不强制注册任何定时任务（外部 cron 仍可触发 CLI）。
    这里留出钩子，后续 ft-023 sidecar 启动时可往里加 ``run_subscription`` cron。
    """
    return None
