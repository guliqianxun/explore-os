"""ft-034 P0-7: tests for ``apps.api.views.jobs`` sub-module.

Old single-file ``apps/api/views.py`` was carved up; these are smoke tests
on the moved trigger / status views to ensure the package import surface +
URL routing still resolve correctly.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def _shutdown_scheduler_after():
    yield
    from apps.api import jobs
    from apps.core import scheduler
    scheduler.shutdown_scheduler(wait=True)
    jobs.reset_for_tests()


@pytest.fixture
def client():
    return APIClient()


def test_jobs_submodule_exposes_internals_for_test_patching():
    """tests_views.test_extract_trigger_returns_queued patches
    ``apps.api.views._do_extract`` — the package re-export must keep that name
    visible at the old top-level path. Otherwise mocking breaks silently.
    """
    from apps.api.views import _do_extract, _do_interpret, _do_render

    assert callable(_do_extract)
    assert callable(_do_interpret)
    assert callable(_do_render)


def test_extract_trigger_through_views_package(client, db):
    """End-to-end: route → views.jobs.ExtractTriggerView → enqueue + 202."""
    from apps.api import jobs as jobs_mod
    from apps.api.jobs import JobInfo

    with patch("apps.api.views.jobs._do_extract"):
        with patch.object(jobs_mod, "enqueue") as eq:
            eq.return_value = JobInfo(job_id="testjob01", name="extract:y")
            r = client.post("/api/papers/2401.22222/extract/", {}, format="json")
    assert r.status_code == 202
    assert r.json()["job_id"] == "testjob01"


def test_job_status_404_through_package(client, db):
    """Unknown job id → 404 routed through ``views.jobs.JobStatusView``."""
    r = client.get("/api/jobs/no-such-job-id/")
    assert r.status_code == 404
