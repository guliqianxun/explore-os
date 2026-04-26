"""ft-022: tests for apps.api.jobs."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _shutdown_scheduler_after():
    yield
    from apps.api import jobs
    from apps.core import scheduler
    # 先 wait=True 等 background 线程把 in-flight job 跑完再 reset，
    # 避免 _process_jobs 与 reset 抢 remove_job 触发 JobLookupError warning。
    scheduler.shutdown_scheduler(wait=True)
    jobs.reset_for_tests()


def test_run_inline_succeeds():
    from apps.api import jobs

    def add(a, b):
        return a + b

    info = jobs.run_inline(add, 2, 3, name="add")
    assert info.status == "succeeded"
    assert info.result == 5
    assert info.error == ""
    assert jobs.get_job(info.job_id) is info


def test_run_inline_failed_captures_error():
    from apps.api import jobs

    def boom():
        raise RuntimeError("nope")

    info = jobs.run_inline(boom, name="boom")
    assert info.status == "failed"
    assert "RuntimeError" in info.error
    assert "nope" in info.error


def test_get_job_unknown_returns_none():
    from apps.api import jobs
    assert jobs.get_job("does-not-exist") is None


def test_enqueue_returns_queued_immediately():
    from apps.api import jobs

    def slow():
        return 42

    info = jobs.enqueue(slow, name="slow")
    assert info.status in ("queued", "running", "succeeded")
    # 同 job_id 可查
    assert jobs.get_job(info.job_id) is info
