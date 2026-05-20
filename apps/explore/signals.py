"""Explore signals: bridges papers_user_* actions → viewpoint state transitions.

Each signal handles one user action. The core invariant:
  unseen → exposed  (on paper read)
  exposed → confirmed (on VIEW_EVIDENCE — API endpoint)
  confirmed → linked (on claim link creation)
  linked → confirmed (on claim link deletion)
  linked/confirmed → internalized (on thread write)

All transitions are recorded as ExploreVPEvent rows.
Dirty topic tracking marks topics for next crunch.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from django.db.models import Q
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.explore.models import (
    ExploreClaimLink,
    ExploreThreadNote,
    ExploreVPEvent,
    ExploreVPState,
    VPState,
    VPEventTrigger,
    mark_topic_dirty,
)
from apps.papers.models import PaperStatus, UserPaperStatus

log = logging.getLogger(__name__)


def _get_or_create_vp_state(user_id: int | None, viewpoint_id: str) -> ExploreVPState:
    """Get or create a VPState row for a (user, viewpoint) pair."""
    if user_id is None:
        user_id = 1  # single-user desktop mode
    obj, _created = ExploreVPState.objects.get_or_create(
        user_id=user_id,
        viewpoint_id=viewpoint_id,
        defaults={
            "state": VPState.UNSEEN,
            "exposed_at": None,
            "last_event_at": None,
        },
    )
    return obj


def _transition(user_id: int | None, viewpoint_id: str, from_state: str,
                to_state: str, trigger: str, payload: dict | None = None) -> bool:
    """Attempt a state transition. Returns True if successful, False if invalid."""
    vp = _get_or_create_vp_state(user_id, viewpoint_id)

    valid_order = [VPState.UNSEEN, VPState.EXPOSED, VPState.CONFIRMED,
                   VPState.LINKED, VPState.INTERNALIZED]
    from_idx = valid_order.index(from_state) if from_state in valid_order else -1
    to_idx = valid_order.index(to_state) if to_state in valid_order else -1
    current_idx = valid_order.index(vp.state) if vp.state in valid_order else -1

    # Guard 1: backward transitions blocked (except UNLINK)
    if to_idx < from_idx and trigger != VPEventTrigger.UNLINK:
        return False

    # Guard 2: UNLINK only valid from LINKED
    if trigger == VPEventTrigger.UNLINK and vp.state != VPState.LINKED:
        return False

    # Guard 3: idempotency — if already at or beyond target, skip
    if current_idx >= to_idx and trigger != VPEventTrigger.UNLINK:
        return False

    vp.state = to_state
    vp.last_event_at = datetime.now(UTC)
    if to_state == VPState.EXPOSED and vp.exposed_at is None:
        vp.exposed_at = vp.last_event_at
    vp.save(update_fields=["state", "last_event_at", "exposed_at"])

    ExploreVPEvent.objects.create(
        user_id=vp.user_id,
        viewpoint_id=viewpoint_id,
        from_state=from_state,
        to_state=to_state,
        trigger=trigger,
        payload=payload or {},
    )
    return True


def _viewpoints_of_paper(paper) -> list[str]:
    """Get all viewpoint_ids for a given paper."""
    from apps.interpret.models import Claim
    return list(Claim.objects.filter(paper=paper).values_list("claim_id", flat=True))


# ── Signal handlers ──

@receiver(post_save, sender=UserPaperStatus)
def on_paper_status_change(sender, instance, created, **kwargs):  # noqa: ANN001
    """When user reads/keeps a paper → all its viewpoints: unseen → exposed."""
    if instance.status not in (PaperStatus.READING, PaperStatus.READ_KEPT):
        return

    paper = instance.paper
    viewpoint_ids = _viewpoints_of_paper(paper)
    if not viewpoint_ids:
        log.debug("[explore] no viewpoints for paper %s", paper.key)
        return

    user_id = 1
    for vid in viewpoint_ids:
        ok = _transition(user_id, vid, VPState.UNSEEN,
                         VPState.EXPOSED, VPEventTrigger.READ,
                         payload={"paper_key": paper.key})
        if ok:
            log.debug("[explore] %s: unseen -> exposed (paper %s)", vid, paper.key)

    # Mark affected topics dirty (derive from paper keywords)
    kw = paper.keywords or []
    if kw:
        for kw_item in kw:
            tid = kw_item.lower().strip().replace(" ", "-").replace("_", "-")
            mark_topic_dirty(tid)


@receiver(post_save, sender=ExploreClaimLink)
def on_claim_link_created(sender, instance, created, **kwargs):  # noqa: ANN001
    """When user creates a claim link → both viewpoints: confirmed → linked."""
    if not created:
        return

    user_id = instance.user_id
    for vid in (instance.src_viewpoint_id, instance.dst_viewpoint_id):
        ok = _transition(user_id, vid, VPState.CONFIRMED,
                         VPState.LINKED, VPEventTrigger.LINK,
                         payload={"linked_to": instance.dst_viewpoint_id
                                  if vid == instance.src_viewpoint_id
                                  else instance.src_viewpoint_id})
        if ok:
            # Update link_count
            vp = ExploreVPState.objects.get(user_id=user_id, viewpoint_id=vid)
            vp.link_count = ExploreClaimLink.objects.filter(
                user_id=user_id,
            ).filter(
                Q(src_viewpoint_id=vid) | Q(dst_viewpoint_id=vid),
            ).count()
            vp.save(update_fields=["link_count"])

    # Dirty topic marks (derive from paper keywords of linked viewpoints)
    from apps.interpret.models import Claim
    for vid in (instance.src_viewpoint_id, instance.dst_viewpoint_id):
        claim = Claim.objects.filter(claim_id=vid).select_related("paper").first()
        if claim and claim.paper:
            kw = claim.paper.keywords or []
            for kw_item in kw:
                tid = kw_item.lower().strip().replace(" ", "-").replace("_", "-")
                mark_topic_dirty(tid)


@receiver(post_delete, sender=ExploreClaimLink)
def on_claim_link_deleted(sender, instance, **kwargs):  # noqa: ANN001
    """When user deletes a claim link → both viewpoints: linked → confirmed."""
    user_id = instance.user_id
    for vid in (instance.src_viewpoint_id, instance.dst_viewpoint_id):
        remaining = ExploreClaimLink.objects.filter(
            user_id=user_id,
        ).filter(
            Q(src_viewpoint_id=vid) | Q(dst_viewpoint_id=vid),
        ).count()

        if remaining == 0:
            _transition(user_id, vid, VPState.LINKED,
                        VPState.CONFIRMED, VPEventTrigger.UNLINK,
                        payload={"unlinked_from": instance.dst_viewpoint_id
                                 if vid == instance.src_viewpoint_id
                                 else instance.src_viewpoint_id})

            vp = ExploreVPState.objects.get(user_id=user_id, viewpoint_id=vid)
            vp.link_count = 0
            vp.save(update_fields=["link_count"])
