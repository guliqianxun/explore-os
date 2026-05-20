from __future__ import annotations

from django.db import models


# ── Viewpoint State ──

class VPState(models.TextChoices):
    UNSEEN = "unseen"
    EXPOSED = "exposed"
    CONFIRMED = "confirmed"
    LINKED = "linked"
    INTERNALIZED = "internalized"


class VPEventTrigger(models.TextChoices):
    READ = "READ"
    VIEW_EVIDENCE = "VIEW_EVIDENCE"
    LINK = "LINK"
    UNLINK = "UNLINK"
    THREAD_WRITE = "THREAD_WRITE"


class ExploreVPState(models.Model):
    """Per (user, viewpoint) state: the core atom of explore-os.
    One row per user-viewpoint pair. State advances forward-only
    (except linked -> confirmed on UNLINK)."""

    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    viewpoint_id = models.CharField(max_length=128)  # claim_id from interpret_claims
    state = models.CharField(
        max_length=16,
        choices=VPState.choices,
        default=VPState.UNSEEN,
    )
    exposed_at = models.DateTimeField(null=True, blank=True)
    last_event_at = models.DateTimeField(null=True, blank=True)
    link_count = models.IntegerField(default=0)
    internalized_in = models.JSONField(default=list)  # [thread_id, ...]

    class Meta:
        db_table = "explore_vp_state"
        unique_together = [("user", "viewpoint_id")]
        indexes = [
            models.Index(fields=["user", "state"]),
            models.Index(fields=["last_event_at"]),
        ]


class ExploreVPEvent(models.Model):
    """Append-only event log. Each row = one state transition.
    Never UPDATE, never DELETE."""

    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    viewpoint_id = models.CharField(max_length=128)
    from_state = models.CharField(max_length=16, choices=VPState.choices)
    to_state = models.CharField(max_length=16, choices=VPState.choices)
    trigger = models.CharField(max_length=32, choices=VPEventTrigger.choices)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "explore_vp_event"
        indexes = [
            models.Index(fields=["user", "viewpoint_id"]),
            models.Index(fields=["created_at"]),
        ]


# ── Topic Taxonomy ──

class ExploreTopic(models.Model):
    """A topic in the knowledge space."""

    topic_id = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=128)
    aliases = models.JSONField(default=list)
    description = models.TextField(blank=True)
    source = models.CharField(max_length=16, default="keyword")  # keyword | llm | manual
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "explore_topic"


class TopicRelation(models.TextChoices):
    PREREQUISITE = "prereq"
    SUBTOPIC = "sub"
    APPLICATION = "app"
    RELATED = "rel"


class ExploreTopicEdge(models.Model):
    """Directed edge between topics."""

    src = models.ForeignKey(ExploreTopic, on_delete=models.CASCADE, related_name="out_edges")
    dst = models.ForeignKey(ExploreTopic, on_delete=models.CASCADE, related_name="in_edges")
    relation = models.CharField(max_length=16, choices=TopicRelation.choices)
    weight = models.FloatField(default=1.0)
    source = models.CharField(max_length=16, default="keyword")  # keyword | llm | manual

    class Meta:
        db_table = "explore_topic_edge"
        unique_together = [("src", "dst", "relation")]


# ── Activity Snapshot ──

class ExploreActivity(models.Model):
    """Daily snapshot of per-topic A (activity) and C (consolidation)."""

    snapshot_at = models.DateField(db_index=True)
    topic = models.ForeignKey(ExploreTopic, on_delete=models.CASCADE)
    activity = models.FloatField(default=0.0)  # A
    consolidation = models.FloatField(default=0.0)  # C
    viewpoint_total = models.IntegerField(default=0)
    viewpoint_confirmed = models.IntegerField(default=0)
    is_final = models.BooleanField(default=False)  # True = final for that day

    class Meta:
        db_table = "explore_activity"
        unique_together = [("snapshot_at", "topic")]


# ── Claim Cross-link ──

class ClaimLinkRelation(models.TextChoices):
    AGREES = "agree"
    CONFLICTS = "conflict"
    REFINES = "refine"


class ExploreClaimLink(models.Model):
    """User-established link between two viewpoints."""

    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    src_viewpoint_id = models.CharField(max_length=128)
    dst_viewpoint_id = models.CharField(max_length=128)
    relation = models.CharField(max_length=16, choices=ClaimLinkRelation.choices)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "explore_claim_link"
        unique_together = [("user", "src_viewpoint_id", "dst_viewpoint_id", "relation")]
        indexes = [
            models.Index(fields=["user", "src_viewpoint_id"]),
            models.Index(fields=["user", "dst_viewpoint_id"]),
        ]


# ── Echo: Threads ──

class ExploreThread(models.Model):
    """User-created cross-paper thought thread."""

    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    title = models.CharField(max_length=256)
    body = models.TextField(blank=True)
    viewpoint_ids = models.JSONField(default=list)  # referenced viewpoints
    paper_keys = models.JSONField(default=list)  # referenced papers
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "explore_thread"


class ExploreThreadNote(models.Model):
    """Append-only note within a thread. Chronological sequence."""

    thread = models.ForeignKey(ExploreThread, on_delete=models.CASCADE, related_name="notes")
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "explore_thread_note"
        ordering = ["created_at"]


# ── Echo: Open Questions ──

class ExploreOpenQuestion(models.Model):
    """User question the system should watch for answers to."""

    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    question = models.TextField()
    topic_id = models.CharField(max_length=64, blank=True)  # optional topic binding
    last_hit_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "explore_open_question"


# ── Dirty topics tracker (in-memory, not persisted) ──

_dirty_topics: set[str] = set()


def mark_topic_dirty(topic_id: str) -> None:
    _dirty_topics.add(topic_id)


def get_dirty_topics() -> set[str]:
    return set(_dirty_topics)


def clear_dirty_topics() -> None:
    _dirty_topics.clear()
