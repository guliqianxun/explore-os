"""ft-028 cross-cutting tests: signal auto-wiring + user_* invariants.

These probe the *system* contract rather than individual endpoints:

- Paper.save → post_save signal → UserPaperStatus(new) lands automatically
- Section / Figure / Table / Equation / Citation / Claim falling back to
  ``paper_arxiv_id`` get their ``paper`` FK auto-wired by ``pre_save`` when
  legacy persist code only sets the string column
- UserComment is append-only at the API layer (PUT not allowed; DELETE not
  exposed; PATCH only ``hidden``)
- UserTag uniqueness enforced by ``unique_together(paper, tag)``
- UserBacklink supports bidirectional querying through related managers
"""
from __future__ import annotations

from urllib.parse import urlencode  # noqa: F401  (kept for future use)

import pytest
from rest_framework.test import APIClient

from apps.extract.models import Figure, Section
from apps.interpret.models import Claim
from apps.papers.models import (
    Paper,
    PaperStatus,
    UserBacklink,
    UserComment,
    UserPaperStatus,
    UserTag,
)


@pytest.fixture(autouse=True)
def _shutdown_scheduler_after():
    yield
    from apps.api import jobs
    from apps.core import scheduler
    scheduler.shutdown_scheduler(wait=True)
    jobs.reset_for_tests()


@pytest.fixture
def client():
    return APIClient()


# ---------------- post_save signal: default UserPaperStatus ----------------

def test_paper_creation_creates_default_status(db):
    p = Paper.objects.create(arxiv_id="2401.SIG100", title="auto-status")
    row = UserPaperStatus.objects.get(paper=p)
    assert row.status == PaperStatus.NEW.value


def test_paper_default_status_idempotent_on_resave(db):
    """post_save fires on update too — we use ``created`` flag to guard."""
    p = Paper.objects.create(arxiv_id="2401.SIG101", title="t")
    p.title = "renamed"
    p.save()
    # Still exactly one status row.
    assert UserPaperStatus.objects.filter(paper=p).count() == 1


# ---------------- pre_save signal: paper FK auto-wire ----------------

def test_section_auto_wires_paper_fk_from_arxiv_id(db):
    """Legacy persist sets paper_arxiv_id only; signal must populate paper FK."""
    p = Paper.objects.create(arxiv_id="2401.SIG200", title="autofk")
    s = Section.objects.create(
        material_id="2401.SIG200:section:1",
        paper_arxiv_id="2401.SIG200", seq=1, path="Intro", level=1,
    )
    assert s.paper_id == p.id


def test_section_auto_creates_paper_if_missing(db):
    """If no Paper exists, signal `get_or_create`s one off ``arxiv_id``."""
    Section.objects.create(
        material_id="2401.SIG201:section:1",
        paper_arxiv_id="2401.SIG201", seq=1, path="X", level=1,
    )
    p = Paper.objects.get(arxiv_id="2401.SIG201")
    assert p.title == "arxiv:2401.SIG201"


def test_figure_signal_wires_paper(db):
    Paper.objects.create(arxiv_id="2401.SIG202", title="figpaper")
    f = Figure.objects.create(
        material_id="2401.SIG202:figure:1",
        paper_arxiv_id="2401.SIG202", seq=1, fig_label="Figure 1",
    )
    assert f.paper.arxiv_id == "2401.SIG202"


def test_claim_signal_wires_paper(db):
    Paper.objects.create(arxiv_id="2401.SIG203", title="claimpaper")
    c = Claim.objects.create(
        claim_id="2401.SIG203:claim:1",
        paper_arxiv_id="2401.SIG203", text="t", claim_type="result",
    )
    assert c.paper.arxiv_id == "2401.SIG203"


# ---------------- UserComment append-only ----------------

def test_comment_endpoint_no_put_no_delete(db):
    """API layer must NOT expose mutate-text or delete operations."""
    p = Paper.objects.create(arxiv_id="2401.APO100", title="t")
    c = UserComment.objects.create(paper=p, text="original")
    client = APIClient()

    r = client.put(
        f"/api/papers/{p.arxiv_id}/comments/{c.id}/",
        {"text": "new"}, format="json",
    )
    # No PUT handler → DRF emits 405.
    assert r.status_code == 405

    r = client.delete(f"/api/papers/{p.arxiv_id}/comments/{c.id}/")
    assert r.status_code == 405


def test_comment_patch_text_is_400_not_silently_dropped(db):
    p = Paper.objects.create(arxiv_id="2401.APO101", title="t")
    c = UserComment.objects.create(paper=p, text="original")
    client = APIClient()
    r = client.patch(
        f"/api/papers/{p.arxiv_id}/comments/{c.id}/",
        {"text": "edited", "hidden": True}, format="json",
    )
    assert r.status_code == 400  # mixed-key payload is rejected outright
    c.refresh_from_db()
    assert c.text == "original"
    assert c.hidden is False  # the failed PATCH must NOT have applied 'hidden'


# ---------------- UserTag uniqueness ----------------

def test_tag_unique_together_at_orm_level(db):
    p = Paper.objects.create(arxiv_id="2401.TAG100", title="t")
    UserTag.objects.create(paper=p, tag="llm")
    from django.db import IntegrityError
    with pytest.raises(IntegrityError):
        UserTag.objects.create(paper=p, tag="llm")


def test_tag_same_label_different_papers_allowed(db):
    a = Paper.objects.create(arxiv_id="2401.TAG101", title="a")
    b = Paper.objects.create(arxiv_id="2401.TAG102", title="b")
    UserTag.objects.create(paper=a, tag="diffusion")
    UserTag.objects.create(paper=b, tag="diffusion")  # OK
    assert UserTag.objects.filter(tag="diffusion").count() == 2


# ---------------- UserBacklink bidirectional ----------------

def test_backlink_bidirectional_related_managers(db):
    a = Paper.objects.create(arxiv_id="2401.BL100", title="A")
    b = Paper.objects.create(arxiv_id="2401.BL101", title="B")
    UserBacklink.objects.create(src=a, dst=b, relation="supports")
    assert a.backlinks_out.count() == 1
    assert a.backlinks_in.count() == 0
    assert b.backlinks_out.count() == 0
    assert b.backlinks_in.count() == 1


def test_backlink_unique_per_relation(db):
    """Same (src,dst,relation) triple is unique; different relations OK."""
    a = Paper.objects.create(arxiv_id="2401.BL110", title="A")
    b = Paper.objects.create(arxiv_id="2401.BL111", title="B")
    UserBacklink.objects.create(src=a, dst=b, relation="supports")
    from django.db import IntegrityError
    with pytest.raises(IntegrityError):
        UserBacklink.objects.create(src=a, dst=b, relation="supports")


def test_backlink_distinct_relation_allowed(db):
    a = Paper.objects.create(arxiv_id="2401.BL120", title="A")
    b = Paper.objects.create(arxiv_id="2401.BL121", title="B")
    UserBacklink.objects.create(src=a, dst=b, relation="supports")
    UserBacklink.objects.create(src=a, dst=b, relation="contradicts")
    assert UserBacklink.objects.filter(src=a, dst=b).count() == 2
