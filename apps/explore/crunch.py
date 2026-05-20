"""Daily crunch orchestrator: compute A, C, snapshot, detect gaps.

Run via: python manage.py crunch
Scheduled via APScheduler (daily at 03:00).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from django.db import transaction

from apps.explore.activity import compute_activity, compute_consolidation
from apps.explore.models import (
    ExploreActivity,
    ExploreTopic,
    ExploreTopicEdge,
    TopicRelation,
    clear_dirty_topics,
    get_dirty_topics,
)

log = logging.getLogger(__name__)

# Gap thresholds
A_ACTIVE_THRESHOLD = 0.3
C_GAP_THRESHOLD = 0.3
C_DECAY_THRESHOLD = 0.5
DECAY_DAYS = 90


@transaction.atomic
def run_crunch(user_id: int = 1) -> dict:
    """Run a full crunch cycle: compute A, C, write snapshot, detect gaps
    for the given user. Returns summary dict."""
    now = datetime.now(UTC)
    today = now.date()

    dirty = get_dirty_topics()

    # If no dirty topics, still snapshot active topics
    A = compute_activity(user_id, now)
    C = compute_consolidation(user_id)

    all_topics = set(A.keys()) | set(C.keys()) | {t for t in dirty if t}
    summary = {"topics": 0, "gaps_prereq": 0, "gaps_decay": 0, "gaps_canonical": 0, "ts": now.isoformat()}

    for topic_id in all_topics:
        if not topic_id:
            continue

        a_val = A.get(topic_id, 0.0)
        c_val = C.get(topic_id, 0.0)

        topic_obj, _created = ExploreTopic.objects.get_or_create(
            topic_id=topic_id,
            defaults={"name": topic_id},
        )

        # Count viewpoints
        from apps.explore.models import ExploreVPState, VPState
        vp_total = ExploreVPState.objects.filter(
            user_id=user_id,
        ).exclude(state=VPState.UNSEEN).count()

        claim_topic = 0
        confirmed_count = int(c_val * max(vp_total, 1))

        ExploreActivity.objects.update_or_create(
            snapshot_at=today,
            topic=topic_obj,
            defaults={
                "activity": round(a_val, 4),
                "consolidation": round(c_val, 4),
                "viewpoint_total": claim_topic or vp_total,
                "viewpoint_confirmed": confirmed_count,
                "is_final": False,
            },
        )
        summary["topics"] += 1

    # Mark all today's snapshots as final
    ExploreActivity.objects.filter(snapshot_at=today).update(is_final=True)

    # Compute gaps
    summary["gaps_prereq"] = _detect_prereq_gaps(user_id, A, C)
    summary["gaps_decay"] = _detect_decay_gaps(user_id, C, now)
    summary["gaps_canonical"] = _detect_canonical_gaps(user_id, A)

    clear_dirty_topics()

    log.info("[explore crunch] %s topics, A max=%.3f, C mean=%.3f, gaps: prereq=%d decay=%d",
             summary["topics"], max(A.values()) if A else 0.0,
             sum(C.values()) / len(C) if C else 0.0,
             summary["gaps_prereq"], summary["gaps_decay"])

    return summary


def _detect_prereq_gaps(user_id: int, A: dict[str, float], C: dict[str, float]) -> int:
    """Detect topics where user is active but prerequisite mastery is low."""
    count = 0
    for topic_id, a_val in A.items():
        if a_val < A_ACTIVE_THRESHOLD:
            continue
        # Find prerequisites for this topic
        edges = ExploreTopicEdge.objects.filter(
            relation=TopicRelation.PREREQUISITE,
        )
        # We need topic objects to match by topic_id
        # For now: simple topic_id string match
        for edge in edges:
            if edge.dst.topic_id == topic_id:
                prereq_id = edge.src.topic_id
                if C.get(prereq_id, 0.0) < C_GAP_THRESHOLD:
                    log.debug("[explore gap] topic=%s needs prereq=%s (C=%.2f)",
                              topic_id, prereq_id, C.get(prereq_id, 0.0))
                    count += 1
    return count


def _detect_decay_gaps(user_id: int, C: dict[str, float], now: datetime) -> int:
    """Detect topics with high consolidation but no recent activity."""
    count = 0
    for topic_id, c_val in C.items():
        if c_val < C_DECAY_THRESHOLD:
            continue
        latest = ExploreActivity.objects.filter(
            topic__topic_id=topic_id,
        ).order_by("-snapshot_at").first()
        if latest and latest.snapshot_at:
            age_days = (now.date() - latest.snapshot_at).days
            if age_days > DECAY_DAYS:
                log.debug("[explore gap] topic=%s decayed (%.0f days since last activity)",
                          topic_id, age_days)
                count += 1
    return count


def _detect_canonical_gaps(user_id: int, A: dict[str, float]) -> int:
    """Detect active topics where canonical papers haven't been read.
    Placeholder — requires external citation data (Semantic Scholar API)."""
    return 0
