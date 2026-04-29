"""ft-034 P0-6 + review-B D5: JobSerializer 5-value status enum + legacy mapping."""
from __future__ import annotations

from apps.api.serializers.jobs import (
    JOB_STATUS_CHOICES,
    JobSerializer,
    normalize_job_status,
)


def test_job_status_choices_are_canonical_5_values():
    """5 canonical values lock — review-B D5 / spec ft-034 P0-6."""
    assert set(JOB_STATUS_CHOICES) == {
        "pending", "running", "done", "failed", "cancelled",
    }


def test_normalize_job_status_maps_legacy_values():
    """Backwards-compat mapping at the DTO boundary (1-sprint deprecation)."""
    assert normalize_job_status("queued") == "pending"
    assert normalize_job_status("succeeded") == "done"
    # Already-canonical values pass through untouched
    assert normalize_job_status("running") == "running"
    assert normalize_job_status("done") == "done"
    assert normalize_job_status("cancelled") == "cancelled"


def test_job_serializer_to_representation_translates_legacy_status():
    """Serializing a JobInfo dict with legacy ``succeeded`` outputs ``done``."""
    payload = {
        "job_id": "abc",
        "name": "extract:x",
        "status": "succeeded",
        "created_at": "2026-04-29T00:00:00+00:00",
        "started_at": "",
        "finished_at": "",
        "result": None,
        "error": "",
    }
    out = JobSerializer(payload).data
    assert out["status"] == "done"


def test_job_serializer_to_representation_translates_queued_to_pending():
    payload = {
        "job_id": "abc",
        "name": "extract:x",
        "status": "queued",
        "created_at": "2026-04-29T00:00:00+00:00",
        "started_at": "",
        "finished_at": "",
        "result": None,
        "error": "",
    }
    out = JobSerializer(payload).data
    assert out["status"] == "pending"
