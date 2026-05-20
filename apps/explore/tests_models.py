from __future__ import annotations

import pytest

from apps.explore.models import ExploreTopic, ExploreVPEvent, ExploreVPState, VPState, VPEventTrigger


@pytest.mark.django_db
def test_vp_state_creation():
    vp = ExploreVPState.objects.create(user_id=1, viewpoint_id="test:claim:1", state=VPState.UNSEEN)
    assert vp.state == VPState.UNSEEN
    assert ExploreVPState.objects.count() == 1


@pytest.mark.django_db
def test_vp_state_unique():
    ExploreVPState.objects.create(user_id=1, viewpoint_id="dup:claim:1", state=VPState.UNSEEN)
    with pytest.raises(Exception):
        ExploreVPState.objects.create(user_id=1, viewpoint_id="dup:claim:1", state=VPState.EXPOSED)


@pytest.mark.django_db
def test_vp_event_creation():
    ExploreVPEvent.objects.create(
        user_id=1, viewpoint_id="test:claim:1",
        from_state=VPState.UNSEEN, to_state=VPState.EXPOSED,
        trigger=VPEventTrigger.READ,
    )
    assert ExploreVPEvent.objects.count() == 1


@pytest.mark.django_db
def test_topic_creation():
    t = ExploreTopic.objects.create(topic_id="test-topic", name="Test Topic")
    assert t.topic_id == "test-topic"
