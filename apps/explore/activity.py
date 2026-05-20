"""Activity computation: A(u, t, τ).

A_u(t) = sum over viewpoints in topic t of:
  w(state) * exp(-(now - last_event) / λ_A)

Normalized by the max topic value (not sum-to-1).
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

from apps.explore.models import ExploreVPState, VPState

# State → activity weight
W: dict[str, float] = {
    VPState.UNSEEN: 0.00,
    VPState.EXPOSED: 0.05,
    VPState.CONFIRMED: 0.15,
    VPState.LINKED: 0.30,
    VPState.INTERNALIZED: 0.50,
}

# Activity half-life in days
LAMBDA_A = 14.0


def _topic_of_viewpoint(viewpoint_id: str) -> str | None:
    """Derive topic from viewpoint's source paper keywords."""
    from apps.interpret.models import Claim
    claim = Claim.objects.filter(claim_id=viewpoint_id).first()
    if not claim or not claim.paper_id:
        return None
    paper = claim.paper
    kw = paper.keywords or []
    if kw:
        return kw[0]  # simplest: primary keyword
    brief = getattr(paper, "paperbrief", None)
    if brief and brief.keywords:
        return brief.keywords[0] if brief.keywords else None
    return None


def compute_activity(user_id: int, now: datetime | None = None) -> dict[str, float]:
    """Compute A_u(t) for all topics this user touches.

    Returns {topic_id: activity} normalized by max value.
    """
    if now is None:
        now = datetime.now(UTC)

    topic_scores: dict[str, float] = {}
    topic_last_event: dict[str, float] = {}

    # Load all VP states for this user that aren't UNSEEN
    vp_states = ExploreVPState.objects.filter(
        user_id=user_id,
    ).exclude(state=VPState.UNSEEN).only(
        "viewpoint_id", "state", "last_event_at",
    )

    # Batch-load claim→paper→topic mapping
    viewpoint_ids = [vp.viewpoint_id for vp in vp_states]
    topic_map = _batch_viewpoint_to_topic(viewpoint_ids)

    for vp in vp_states:
        topic_id = topic_map.get(vp.viewpoint_id)
        if not topic_id:
            continue

        weight = W.get(vp.state, 0.0)
        if weight == 0.0:
            continue

        if vp.last_event_at is None:
            continue

        age_days = (now - vp.last_event_at).total_seconds() / 86400.0
        decay = math.exp(-age_days / LAMBDA_A)
        score = weight * decay

        topic_scores[topic_id] = topic_scores.get(topic_id, 0.0) + score
        topic_last_event[topic_id] = max(
            topic_last_event.get(topic_id, 0.0), age_days,
        )

    if not topic_scores:
        return {}

    # Normalize by max value
    max_score = max(topic_scores.values())
    if max_score > 0:
        for tid in topic_scores:
            topic_scores[tid] /= max_score

    return topic_scores


def compute_consolidation(user_id: int) -> dict[str, float]:
    """Compute C_u(t) = |{v: σ_v ≥ confirmed}| / (|{v: σ_v ≥ exposed}| + 1)."""
    vp_states = ExploreVPState.objects.filter(
        user_id=user_id,
    ).exclude(state=VPState.UNSEEN).only(
        "viewpoint_id", "state",
    )

    viewpoint_ids = [vp.viewpoint_id for vp in vp_states]
    topic_map = _batch_viewpoint_to_topic(viewpoint_ids)

    from collections import defaultdict
    confirmed: dict[str, int] = defaultdict(int)
    exposed: dict[str, int] = defaultdict(int)
    CONFIRMED_STATES = {VPState.CONFIRMED, VPState.LINKED, VPState.INTERNALIZED}

    for vp in vp_states:
        topic_id = topic_map.get(vp.viewpoint_id)
        if not topic_id:
            continue

        if vp.state in CONFIRMED_STATES:
            confirmed[topic_id] += 1
        exposed[topic_id] += 1

    result: dict[str, float] = {}
    all_topics = set(confirmed.keys()) | set(exposed.keys())
    for tid in all_topics:
        result[tid] = confirmed.get(tid, 0) / (exposed.get(tid, 0) + 1)

    return result


# ── Viewpoint → Topic mapping (cached) ──

_topic_cache: dict[str, str | None] = {}


def _batch_viewpoint_to_topic(viewpoint_ids: list[str]) -> dict[str, str]:
    """Map a batch of viewpoint_ids to topic_ids via paper keywords."""
    result: dict[str, str] = {}
    uncached = []

    for vid in viewpoint_ids:
        if vid in _topic_cache:
            val = _topic_cache[vid]
            if val is not None:
                result[vid] = val
        else:
            uncached.append(vid)

    if uncached:
        from apps.interpret.models import Claim
        claims = Claim.objects.filter(
            claim_id__in=uncached,
        ).select_related("paper").only("claim_id", "paper__keywords", "paper_id")

        paper_cache: dict[int, str | None] = {}
        for claim in claims:
            paper_id = claim.paper_id
            if paper_id not in paper_cache:
                paper = claim.paper
                kw = paper.keywords or []
                if kw:
                    paper_cache[paper_id] = kw[0]
                else:
                    brief = getattr(paper, "paperbrief", None)
                    if brief and brief.keywords:
                        paper_cache[paper_id] = brief.keywords[0]
                    else:
                        paper_cache[paper_id] = None

            topic = paper_cache.get(paper_id)
            if topic:
                topic = topic.lower().strip().replace(" ", "-").replace("_", "-")
            _topic_cache[claim.claim_id] = topic
            if topic:
                result[claim.claim_id] = topic

    return result


def invalidate_topic_cache() -> None:
    _topic_cache.clear()
