"""Explore API views: profile, activity, gaps, viewpoint state, events."""

from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.explore.activity import compute_activity, compute_consolidation
from apps.explore.models import (
    ExploreActivity,
    ExploreClaimLink,
    ExploreOpenQuestion,
    ExploreThread,
    ExploreThreadNote,
    ExploreTopic,
    ExploreVPState,
    VPState,
    VPEventTrigger,
)
from apps.explore.signals import _get_or_create_vp_state, _transition


@api_view(["GET"])
@permission_classes([AllowAny])
def profile_view(request):
    """GET /api/state/profile/ — user's explore summary."""
    user_id = request.user.id if request.user.is_authenticated else 1

    A = compute_activity(user_id)
    C = compute_consolidation(user_id)

    topics = []
    all_topic_ids = set(A.keys()) | set(C.keys())
    for tid in all_topic_ids:
        topic_obj = ExploreTopic.objects.filter(topic_id=tid).first()
        name = topic_obj.name if topic_obj else tid
        topics.append({
            "topic_id": tid,
            "name": name,
            "activity": round(A.get(tid, 0.0), 4),
            "consolidation": round(C.get(tid, 0.0), 4),
        })

    topics.sort(key=lambda t: -t["activity"])

    # Count viewpoint stats
    total_vps = ExploreVPState.objects.filter(user_id=user_id).exclude(
        state=VPState.UNSEEN).count()
    confirmed_vps = ExploreVPState.objects.filter(
        user_id=user_id,
        state__in=[VPState.CONFIRMED, VPState.LINKED, VPState.INTERNALIZED],
    ).count()
    linked_vps = ExploreVPState.objects.filter(
        user_id=user_id, state=VPState.LINKED,
    ).count()

    last_crunch = ExploreActivity.objects.filter(
        is_final=True,
    ).order_by("-snapshot_at").first()

    return Response({
        "user_id": user_id,
        "topics": topics[:20],
        "viewpoints": {
            "total": total_vps,
            "confirmed": confirmed_vps,
            "linked": linked_vps,
        },
        "last_crunch_at": last_crunch.snapshot_at.isoformat() if last_crunch else None,
    })


@api_view(["GET"])
@permission_classes([AllowAny])
def activity_timeline(request):
    """GET /api/state/activity/?topic=<id>&days=30"""
    topic_id = request.query_params.get("topic", "")
    days = int(request.query_params.get("days", 30))

    qs = ExploreActivity.objects.filter(is_final=True)
    if topic_id:
        qs = qs.filter(topic__topic_id=topic_id)
    rows = list(qs.order_by("-snapshot_at")[:days])

    data = []
    for row in reversed(rows):
        data.append({
            "date": row.snapshot_at.isoformat(),
            "topic_id": row.topic.topic_id,
            "activity": row.activity,
            "consolidation": row.consolidation,
        })

    return Response(data)


@api_view(["GET"])
@permission_classes([AllowAny])
def gaps_view(request):
    """GET /api/state/gaps/ — current knowledge gaps."""
    user_id = request.user.id if request.user.is_authenticated else 1
    from apps.explore.crunch import (
        A_ACTIVE_THRESHOLD, C_GAP_THRESHOLD, C_DECAY_THRESHOLD, DECAY_DAYS,
    )
    from apps.explore.models import ExploreTopicEdge, TopicRelation
    from datetime import UTC, datetime

    A = compute_activity(user_id)
    C = compute_consolidation(user_id)

    gaps = {"prereq": [], "decay": [], "canonical": []}

    # Prereq gaps
    edges = ExploreTopicEdge.objects.filter(relation=TopicRelation.PREREQUISITE)
    for edge in edges:
        tid = edge.dst.topic_id
        prereq_id = edge.src.topic_id
        if A.get(tid, 0.0) > A_ACTIVE_THRESHOLD:
            if C.get(prereq_id, 0.0) < C_GAP_THRESHOLD:
                gaps["prereq"].append({
                    "topic_id": tid,
                    "prerequisite_id": prereq_id,
                    "prerequisite_name": edge.src.name,
                    "prerequisite_consolidation": round(C.get(prereq_id, 0.0), 3),
                })

    # Decay gaps
    now = datetime.now(UTC)
    for tid, c_val in C.items():
        if c_val < C_DECAY_THRESHOLD:
            continue
        latest = ExploreActivity.objects.filter(
            topic__topic_id=tid,
        ).order_by("-snapshot_at").first()
        if latest and latest.snapshot_at:
            age = (now.date() - latest.snapshot_at).days
            if age > DECAY_DAYS:
                gaps["decay"].append({
                    "topic_id": tid,
                    "days_since_last": age,
                })

    return Response(gaps)


@api_view(["GET"])
@permission_classes([AllowAny])
def viewpoint_state(request, viewpoint_id: str):
    """GET /api/state/viewpoint/<id>/ — state of a single viewpoint."""
    user_id = request.user.id if request.user.is_authenticated else 1

    vp = ExploreVPState.objects.filter(
        user_id=user_id, viewpoint_id=viewpoint_id,
    ).first()

    if not vp:
        return Response({"state": "unseen", "viewpoint_id": viewpoint_id})

    from apps.explore.models import ExploreVPEvent
    events = ExploreVPEvent.objects.filter(
        user_id=user_id, viewpoint_id=viewpoint_id,
    ).order_by("created_at").values(
        "from_state", "to_state", "trigger", "created_at",
    )

    return Response({
        "viewpoint_id": viewpoint_id,
        "state": vp.state,
        "exposed_at": vp.exposed_at.isoformat() if vp.exposed_at else None,
        "last_event_at": vp.last_event_at.isoformat() if vp.last_event_at else None,
        "link_count": vp.link_count,
        "events": list(events),
    })


@api_view(["POST"])
@permission_classes([AllowAny])
def report_event(request):
    """POST /api/state/events/ — frontend reports a user action.

    Body: {"viewpoint_id": "...", "trigger": "VIEW_EVIDENCE", "payload": {...}}
    Allowed triggers: VIEW_EVIDENCE, THREAD_WRITE
    """
    user_id = request.user.id if request.user.is_authenticated else 1
    viewpoint_id = request.data.get("viewpoint_id")
    trigger = request.data.get("trigger")
    payload = request.data.get("payload", {})

    if not viewpoint_id or not trigger:
        return Response({"error": "viewpoint_id and trigger required"},
                        status=status.HTTP_400_BAD_REQUEST)

    if trigger == VPEventTrigger.VIEW_EVIDENCE:
        ok = _transition(user_id, viewpoint_id, VPState.EXPOSED,
                         VPState.CONFIRMED, trigger, payload)
    elif trigger == VPEventTrigger.THREAD_WRITE:
        # thread write can come from confirmed or linked
        vp = _get_or_create_vp_state(user_id, viewpoint_id)
        if vp.state in (VPState.CONFIRMED, VPState.LINKED):
            ok = _transition(user_id, viewpoint_id, vp.state,
                             VPState.INTERNALIZED, trigger, payload)
        else:
            ok = False
    else:
        return Response({"error": f"unsupported trigger: {trigger}"},
                        status=status.HTTP_400_BAD_REQUEST)

    if ok:
        from apps.explore.activity import invalidate_topic_cache
        invalidate_topic_cache()
        return Response({"status": "ok", "viewpoint_id": viewpoint_id})
    return Response({"status": "skipped", "reason": "no transition needed"})


# ── Claim Links ──

@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def claim_links(request):
    """GET /api/state/links/?viewpoint=<id> — list links for a viewpoint.
    POST /api/state/links/ — create a link."""
    user_id = request.user.id if request.user.is_authenticated else 1

    if request.method == "GET":
        vp_id = request.query_params.get("viewpoint", "")
        qs = ExploreClaimLink.objects.filter(user_id=user_id)
        if vp_id:
            from django.db.models import Q
            qs = qs.filter(Q(src_viewpoint_id=vp_id) | Q(dst_viewpoint_id=vp_id))
        data = []
        for link in qs[:50]:
            data.append({
                "id": link.id,
                "src_viewpoint_id": link.src_viewpoint_id,
                "dst_viewpoint_id": link.dst_viewpoint_id,
                "relation": link.relation,
                "note": link.note,
                "created_at": link.created_at.isoformat(),
            })
        return Response(data)

    # POST
    src = request.data.get("src_viewpoint_id")
    dst = request.data.get("dst_viewpoint_id")
    relation = request.data.get("relation", "agree")
    note = request.data.get("note", "")

    if not src or not dst:
        return Response({"error": "src_viewpoint_id and dst_viewpoint_id required"},
                        status=status.HTTP_400_BAD_REQUEST)

    link = ExploreClaimLink.objects.create(
        user_id=user_id,
        src_viewpoint_id=src,
        dst_viewpoint_id=dst,
        relation=relation,
        note=note,
    )
    return Response({
        "id": link.id,
        "src_viewpoint_id": link.src_viewpoint_id,
        "dst_viewpoint_id": link.dst_viewpoint_id,
        "relation": link.relation,
    }, status=status.HTTP_201_CREATED)


@api_view(["DELETE"])
@permission_classes([AllowAny])
def claim_link_delete(request, link_id: int):
    """DELETE /api/state/links/<id>/"""
    user_id = request.user.id if request.user.is_authenticated else 1
    link = ExploreClaimLink.objects.filter(id=link_id, user_id=user_id).first()
    if not link:
        return Response({"error": "not found"}, status=status.HTTP_404_NOT_FOUND)
    link.delete()
    return Response({"status": "deleted"})


# ── Threads ──

@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def threads(request):
    """GET /api/state/threads/ — list threads.
    POST /api/state/threads/ — create thread."""
    user_id = request.user.id if request.user.is_authenticated else 1

    if request.method == "GET":
        qs = ExploreThread.objects.filter(user_id=user_id).order_by("-updated_at")
        data = []
        for t in qs[:20]:
            notes = t.notes.values("id", "body", "created_at")
            data.append({
                "id": t.id,
                "title": t.title,
                "body": t.body,
                "viewpoint_ids": t.viewpoint_ids,
                "paper_keys": t.paper_keys,
                "notes": list(notes),
                "created_at": t.created_at.isoformat(),
                "updated_at": t.updated_at.isoformat(),
            })
        return Response(data)

    # POST
    title = request.data.get("title", "")
    body = request.data.get("body", "")
    viewpoint_ids = request.data.get("viewpoint_ids", [])
    paper_keys = request.data.get("paper_keys", [])

    thread = ExploreThread.objects.create(
        user_id=user_id,
        title=title,
        body=body,
        viewpoint_ids=viewpoint_ids,
        paper_keys=paper_keys,
    )
    return Response({"id": thread.id, "title": thread.title},
                    status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([AllowAny])
def thread_add_note(request, thread_id: int):
    """POST /api/state/threads/<id>/notes/ — add note to thread."""
    user_id = request.user.id if request.user.is_authenticated else 1

    thread = ExploreThread.objects.filter(id=thread_id, user_id=user_id).first()
    if not thread:
        return Response({"error": "not found"}, status=status.HTTP_404_NOT_FOUND)

    body = request.data.get("body", "")
    note = ExploreThreadNote.objects.create(thread=thread, body=body)

    # If the note references viewpoints, trigger internalized transition
    for vid in request.data.get("viewpoint_ids", []):
        vp = ExploreVPState.objects.filter(
            user_id=user_id, viewpoint_id=vid,
        ).first()
        if vp and vp.state in (VPState.CONFIRMED, VPState.LINKED):
            _transition(user_id, vid, vp.state,
                        VPState.INTERNALIZED, VPEventTrigger.THREAD_WRITE,
                        payload={"thread_id": thread.id})

            # Update internalized_in
            if thread.id not in vp.internalized_in:
                vp.internalized_in.append(thread.id)
                vp.save(update_fields=["internalized_in"])

    thread.save()  # bump updated_at
    return Response({"id": note.id, "created_at": note.created_at.isoformat()})


# ── Open Questions ──

@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def questions(request):
    """GET /api/state/questions/ — list open questions.
    POST /api/state/questions/ — create question."""
    user_id = request.user.id if request.user.is_authenticated else 1

    if request.method == "GET":
        qs = ExploreOpenQuestion.objects.filter(user_id=user_id).order_by("-created_at")
        data = [{
            "id": q.id, "question": q.question, "topic_id": q.topic_id,
            "last_hit_at": q.last_hit_at.isoformat() if q.last_hit_at else None,
            "created_at": q.created_at.isoformat(),
        } for q in qs]
        return Response(data)

    question = request.data.get("question", "")
    topic_id = request.data.get("topic_id", "")
    q = ExploreOpenQuestion.objects.create(
        user_id=user_id, question=question, topic_id=topic_id,
    )
    return Response({"id": q.id, "question": q.question},
                    status=status.HTTP_201_CREATED)


@api_view(["DELETE"])
@permission_classes([AllowAny])
def question_delete(request, question_id: int):
    user_id = request.user.id if request.user.is_authenticated else 1
    q = ExploreOpenQuestion.objects.filter(id=question_id, user_id=user_id).first()
    if not q:
        return Response({"error": "not found"}, status=status.HTTP_404_NOT_FOUND)
    q.delete()
    return Response({"status": "deleted"})
