"""ft-022: tests for apps.core.scheduler."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _shutdown_scheduler_after():
    yield
    from apps.core import scheduler
    scheduler.shutdown_scheduler(wait=False)


def test_get_scheduler_singleton():
    from apps.core.scheduler import get_scheduler
    s1 = get_scheduler()
    s2 = get_scheduler()
    assert s1 is s2


def test_start_and_shutdown_idempotent():
    from apps.core.scheduler import get_scheduler, shutdown_scheduler, start_scheduler
    start_scheduler()
    start_scheduler()  # 二次调用不抛
    s = get_scheduler()
    assert s.running
    shutdown_scheduler()
    shutdown_scheduler()  # noop


def test_shutdown_when_never_started():
    from apps.core import scheduler
    scheduler.shutdown_scheduler()  # 不抛


def test_register_default_jobs_returns_none():
    from apps.core.scheduler import register_default_jobs
    assert register_default_jobs() is None
