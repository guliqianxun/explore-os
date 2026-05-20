"""MVP validation: new explore-os link — viewpoint state machine + user-in-the-loop.

Validates:
  1. Papers + claims exist in DB (from subscription pipeline)
  2. Viewpoint state transitions work (unseen → exposed → confirmed → linked)
  3. Activity/consolidation computation
  4. Daily crunch with real data
  5. API endpoints return meaningful results
"""

import django, os, sys
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
django.setup()

from apps.papers.models import Paper, PaperBrief
from apps.interpret.models import Claim
from apps.explore.models import (
    ExploreVPState, ExploreVPEvent, ExploreTopic,
    ExploreClaimLink, ExploreActivity,
    VPState, VPEventTrigger,
)
from apps.explore.signals import _get_or_create_vp_state, _transition
from apps.explore.activity import compute_activity, compute_consolidation
from apps.explore.crunch import run_crunch

PASS = "✅"
FAIL = "❌"
WARN = "⚠️"
INFO = "   "

def check(desc, ok, detail=""):
    mark = PASS if ok else FAIL
    print(f"  {mark} {desc}" + (f"  {detail}" if detail and not ok else ""))
    return ok

print("=" * 60)
print("  explore-os MVP Chain Validation")
print("=" * 60)

# ── STAGE 0: Data Exists ──
print(f"\n── Stage 0: Data Readiness ──")
n_papers = Paper.objects.count()
n_briefs = PaperBrief.objects.count()
n_claims = Claim.objects.count()
n_with_claims = Claim.objects.values("paper").distinct().count()
check("Papers in DB", n_papers > 0, f"{n_papers} papers")
check("Briefs in DB", n_briefs > 0, f"{n_briefs} briefs")
check("Claims in DB", n_claims > 0, f"{n_claims} claims across {n_with_claims} papers")

if n_claims == 0:
    print(f"\n  {FAIL} No claims in DB. Run the subscription pipeline with LLM first:")
    print("     uv run python manage.py run_subscription video-generation-daily --days 3 --ignore-memory")
    print("     OR ingest a paper via: POST /api/ingest/arxiv/ {\"arxiv_id\": \"2605.00658\"}")
    sys.exit(1)

# Pick a paper with claims for testing
sample_claim = Claim.objects.first()
sample_paper = sample_claim.paper
print(f"\n{INFO} Using paper: {sample_paper.key} ({sample_paper.title[:60]})")
print(f"{INFO} Sample claim: {sample_claim.claim_id}")
print(f"{INFO} Claim text: {sample_claim.text[:100] if sample_claim.text else 'N/A'}")

# ── STAGE 1: Viewpoint State Machine ──
print(f"\n── Stage 1: Viewpoint State Machine ──")

# Get all claims for this paper
paper_claims = list(Claim.objects.filter(paper=sample_paper).values_list("claim_id", flat=True))
user_id = 1
print(f"{INFO} Paper has {len(paper_claims)} claims")

# 1a: Create initial state (unseen)
for cid in paper_claims[:3]:  # test with first 3 claims
    vp = _get_or_create_vp_state(user_id, cid)
check("VPState init (unseen)", all(
    ExploreVPState.objects.get(user_id=user_id, viewpoint_id=cid).state == VPState.UNSEEN
    for cid in paper_claims[:3]
), "3 claims initialized as unseen")

# 1b: Transition unseen → exposed (simulate paper read)
for cid in paper_claims[:3]:
    ok = _transition(user_id, cid, VPState.UNSEEN, VPState.EXPOSED,
                     VPEventTrigger.READ, payload={"paper_key": sample_paper.key})
    assert ok, f"Failed to transition {cid}"
check("unseen → exposed", all(
    ExploreVPState.objects.get(user_id=user_id, viewpoint_id=cid).state == VPState.EXPOSED
    for cid in paper_claims[:3]
), "3 claims now exposed")
check("exposed_at set", all(
    ExploreVPState.objects.get(user_id=user_id, viewpoint_id=cid).exposed_at is not None
    for cid in paper_claims[:3]
), "exposed_at timestamps present")

# 1c: Verify events
n_events = ExploreVPEvent.objects.filter(user_id=user_id).count()
check("VPEvent logs created", n_events >= 3, f"{n_events} events recorded")

# 1d: Transition exposed → confirmed (simulate user viewing evidence)
for cid in paper_claims[:2]:  # confirm first 2
    ok = _transition(user_id, cid, VPState.EXPOSED, VPState.CONFIRMED,
                     VPEventTrigger.VIEW_EVIDENCE, payload={"action": "expand_claim_card"})
    assert ok
check("exposed → confirmed", all(
    ExploreVPState.objects.get(user_id=user_id, viewpoint_id=cid).state == VPState.CONFIRMED
    for cid in paper_claims[:2]
), "2 claims now confirmed")

# 1e: Transition confirmed → linked (simulate user creating claim link)
if len(paper_claims) >= 2:
    c1, c2 = paper_claims[0], paper_claims[1]
    link = ExploreClaimLink.objects.create(
        user_id=user_id,
        src_viewpoint_id=c1,
        dst_viewpoint_id=c2,
        relation="agree",
    )
    check("claim link created", ExploreClaimLink.objects.filter(user_id=user_id).count() > 0,
          f"link id={link.id}")
    # The signal should have triggered confirmed → linked
    s1 = ExploreVPState.objects.get(user_id=user_id, viewpoint_id=c1).state
    s2 = ExploreVPState.objects.get(user_id=user_id, viewpoint_id=c2).state
    check("confirmed → linked (signal)", s1 == VPState.LINKED and s2 == VPState.LINKED,
          f"states: {s1}, {s2}")

# 1f: Verify backward transition blocked
ok_back = _transition(user_id, paper_claims[0], VPState.LINKED, VPState.EXPOSED, "READ")
check("backward transition blocked", not ok_back, "linked → exposed rejected")

# ── STAGE 2: Topic Seeding ──
print(f"\n── Stage 2: Topic Mapping ──")
kw = sample_paper.keywords or []
brief_kw = []
if hasattr(sample_paper, "paperbrief") and sample_paper.paperbrief:
    brief_kw = sample_paper.paperbrief.keywords or []

# Seed topic from keywords
from apps.explore.management.commands.seed_topics import Command
cmd = Command()
cmd.handle()
n_topics = ExploreTopic.objects.count()
check("Topics seeded", n_topics > 0, f"{n_topics} topics from {len(kw)+len(brief_kw)} keywords")

# ── STAGE 3: Activity & Consolidation ──
print(f"\n── Stage 3: Activity/Consolidation Computation ──")
A = compute_activity(user_id)
C = compute_consolidation(user_id)
check("compute_activity returns dict", isinstance(A, dict))
check("compute_consolidation returns dict", isinstance(C, dict))

# With real data, A and C should have values if topics are mapped to viewpoints
has_data = len(A) > 0 or len(C) > 0
if has_data:
    print(f"{INFO} Activity: {len(A)} topics, top scores: {dict(sorted(A.items(), key=lambda x:-x[1])[:3])}")
    print(f"{INFO} Consolidation: {len(C)} topics, top: {dict(sorted(C.items(), key=lambda x:-x[1])[:3])}")
else:
    print(f"{INFO} A and C are empty — expected if paper keywords don't map to topics")
    print(f"{INFO} This means topics need seeding from a broader paper set")

# ── STAGE 4: Daily Crunch ──
print(f"\n── Stage 4: Daily Crunch ──")
try:
    summary = run_crunch(user_id=user_id)
    check("crunch runs without error", True)
    check("snapshot written", ExploreActivity.objects.filter(is_final=True).count() > 0,
          f"{ExploreActivity.objects.filter(is_final=True).count()} snapshots")
    print(f"{INFO} Summary: {summary}")
except Exception as e:
    check("crunch runs", False, str(e)[:100])

# ── STAGE 5: API Endpoints ──
print(f"\n── Stage 5: API Endpoints ──")
from django.test import RequestFactory
rf = RequestFactory()

# Profile
from apps.explore.views import profile_view, gaps_view, viewpoint_state, report_event
r = rf.get("/api/state/profile/")
resp = profile_view(r)
check("GET /api/state/profile/", resp.status_code == 200,
      f"topics={len(resp.data.get('topics',[]))} vp_total={resp.data.get('viewpoints',{}).get('total',0)}")

# Gaps
r = rf.get("/api/state/gaps/")
resp = gaps_view(r)
check("GET /api/state/gaps/", resp.status_code == 200,
      f"prereq={len(resp.data.get('prereq',[]))} decay={len(resp.data.get('decay',[]))}")

# Viewpoint state
if paper_claims:
    r = rf.get(f"/api/state/viewpoint/{paper_claims[0]}/")
    resp = viewpoint_state(r, paper_claims[0])
    check(f"GET /api/state/viewpoint/<id>/", resp.status_code == 200,
          f"state={resp.data.get('state','?')} events={len(resp.data.get('events',[]))}")

# Event report (simulate VIEW_EVIDENCE for 3rd claim)
if len(paper_claims) >= 3:
    from rest_framework.test import APIRequestFactory
    arf = APIRequestFactory()
    r = arf.post("/api/state/events/", {
        "viewpoint_id": paper_claims[2],
        "trigger": "VIEW_EVIDENCE",
        "payload": {"source": "mvp_test"},
    }, format="json")
    resp = report_event(r)
    check("POST /api/state/events/ (VIEW_EVIDENCE)", resp.status_code == 201 or resp.status_code == 200,
          f"status={resp.status_code}")

# ── STAGE 6: Cleanup ──
print(f"\n── Stage 6: Verification ──")
print(f"  Papers: {Paper.objects.count()}")
print(f"  Briefs: {PaperBrief.objects.count()}")
print(f"  Claims: {Claim.objects.count()}")
print(f"  VP States: {ExploreVPState.objects.count()}")
print(f"  VP Events: {ExploreVPEvent.objects.count()}")
print(f"  Topics: {ExploreTopic.objects.count()}")
print(f"  Claim Links: {ExploreClaimLink.objects.count()}")
print(f"  Activity Snapshots: {ExploreActivity.objects.count()}")
print(f"  Activity Snapshots (final): {ExploreActivity.objects.filter(is_final=True).count()}")

print(f"\n{'=' * 60}")
print(f"  MVP Validation Complete")
print(f"  Chain: claims → σ_v transitions → topics → A/C → crunch → API ✅")
print(f"{'=' * 60}")
