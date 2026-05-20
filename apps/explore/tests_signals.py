from __future__ import annotations

import pytest

from apps.explore.models import ExploreVPEvent, ExploreVPState, VPState
from apps.explore.signals import _get_or_create_vp_state, _transition


@pytest.mark.django_db
def test_get_or_create():
    vp = _get_or_create_vp_state(1, "sig:claim:1")
    assert vp.state == VPState.UNSEEN


@pytest.mark.django_db
def test_transition_unseen_to_exposed():
    ok = _transition(1, "sig:claim:2", VPState.UNSEEN, VPState.EXPOSED, "READ")
    assert ok
    vp = ExploreVPState.objects.get(user_id=1, viewpoint_id="sig:claim:2")
    assert vp.state == VPState.EXPOSED
    assert ExploreVPEvent.objects.filter(viewpoint_id="sig:claim:2").count() == 1


@pytest.mark.django_db
def test_transition_backwards_blocked():
    _transition(1, "sig:claim:3", VPState.UNSEEN, VPState.EXPOSED, "READ")
    # DB state is now EXPOSED. Attempting a transition from UNSEEN to UNSEEN
    # should be blocked because current_idx(EXPOSED=1) >= target_idx(UNSEEN=0)
    ok = _transition(1, "sig:claim:3", VPState.UNSEEN, VPState.UNSEEN, "READ")
    assert not ok
