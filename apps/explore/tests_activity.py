from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from apps.explore.activity import compute_activity, compute_consolidation
from apps.explore.models import ExploreVPState, VPState


@pytest.mark.django_db
def test_empty_activity():
    A = compute_activity(1)
    assert A == {}


@pytest.mark.django_db
def test_activity_basic():
    now = datetime.now(UTC)
    vp1 = ExploreVPState.objects.create(
        user_id=1, viewpoint_id="act:1",
        state=VPState.CONFIRMED, last_event_at=now,
    )
    vp2 = ExploreVPState.objects.create(
        user_id=1, viewpoint_id="act:2",
        state=VPState.EXPOSED, last_event_at=now - timedelta(days=30),
    )
    A = compute_activity(1, now)
    # Will be empty if no topics are mapped (need paper keywords)
    # At minimum, verify it doesn't crash
    C = compute_consolidation(1)
    assert isinstance(C, dict)
