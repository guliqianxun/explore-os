"""ft-028 endpoint tests: status / comment / tag / backlink + extended list/detail.

Mirrors the existing ``tests_views.py`` style (DRF ``APIClient`` + ORM
fixtures). Each new endpoint gets at least a happy-path + one edge case
(404 / illegal transition / hidden-only PATCH / duplicate tag / etc.).

These tests exercise BOTH ``paper_key`` and legacy ``arxiv_id`` paths so the
``resolve_paper`` regex doesn't drift.
"""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.extract.models import Section
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


@pytest.fixture
def paper(db):
    p = Paper.objects.create(arxiv_id="2401.10001", title="A paper about X")
    # Section gives the list view a non-zero count.
    Section.objects.create(
        material_id=f"{p.arxiv_id}:section:1",
        paper_arxiv_id=p.arxiv_id, seq=1, path="Introduction", level=1,
    )
    return p


@pytest.fixture
def other_paper(db):
    p = Paper.objects.create(arxiv_id="2401.10002", title="Other paper Y")
    Section.objects.create(
        material_id=f"{p.arxiv_id}:section:1",
        paper_arxiv_id=p.arxiv_id, seq=1, path="Methods", level=1,
    )
    return p


# ---------------- list with filters ----------------

def test_list_papers_returns_ft028_fields(client, paper):
    r = client.get("/api/papers/")
    assert r.status_code == 200
    items = r.json()
    found = next((it for it in items if it["arxiv_id"] == paper.arxiv_id), None)
    assert found is not None, items
    # Frozen contract per ft-028.md#dto-contracts.
    for k in (
        "arxiv_id", "paper_key", "title", "status", "tags", "n_comments",
        "n_sections", "n_figures", "n_tables", "n_claims",
    ):
        assert k in found, f"missing {k} in {found}"
    assert found["paper_key"] == paper.key
    assert found["title"] == paper.title
    assert found["status"] == "new"
    assert found["tags"] == []
    assert found["n_comments"] == 0
    assert found["n_sections"] == 1


def test_list_papers_filter_by_status(client, paper, other_paper):
    # Move `paper` to queued; default-list should still include both, but
    # ?status=new should ONLY include `other_paper`.
    UserPaperStatus.objects.filter(paper=paper).update(status="queued")
    r = client.get("/api/papers/?status=new")
    assert r.status_code == 200
    arxiv_ids = [it["arxiv_id"] for it in r.json()]
    assert other_paper.arxiv_id in arxiv_ids
    assert paper.arxiv_id not in arxiv_ids

    r = client.get("/api/papers/?status=queued")
    arxiv_ids = [it["arxiv_id"] for it in r.json()]
    assert paper.arxiv_id in arxiv_ids
    assert other_paper.arxiv_id not in arxiv_ids


def test_list_papers_filter_by_tag(client, paper, other_paper):
    UserTag.objects.create(paper=paper, tag="llm")
    r = client.get("/api/papers/?tag=llm")
    assert r.status_code == 200
    arxiv_ids = [it["arxiv_id"] for it in r.json()]
    assert arxiv_ids == [paper.arxiv_id]


def test_list_papers_q_searches_title_and_comments(client, paper, other_paper):
    UserComment.objects.create(paper=other_paper, text="needle keyword in body")
    # Title-side: "Other" matches `other_paper.title`.
    r = client.get("/api/papers/?q=Other")
    arxiv_ids = [it["arxiv_id"] for it in r.json()]
    assert other_paper.arxiv_id in arxiv_ids
    # Comment-side: "needle" matches via UserComment join.
    r = client.get("/api/papers/?q=needle")
    arxiv_ids = [it["arxiv_id"] for it in r.json()]
    assert other_paper.arxiv_id in arxiv_ids


def test_list_papers_invalid_status_returns_400(client, paper):
    r = client.get("/api/papers/?status=bogus")
    assert r.status_code == 400


# ---------------- detail with key vs arxiv_id ----------------

def test_paper_detail_via_key(client, paper):
    r = client.get(f"/api/papers/{paper.key}/")
    assert r.status_code == 200
    body = r.json()
    assert body["paper_key"] == paper.key
    assert body["title"] == paper.title
    assert body["status"] == "new"


def test_paper_detail_via_arxiv_id_includes_ft028_fields(client, paper):
    r = client.get(f"/api/papers/{paper.arxiv_id}/")
    assert r.status_code == 200
    body = r.json()
    assert body["paper_key"] == paper.key
    assert body["title"] == paper.title
    assert "tags" in body and "n_comments" in body and "status" in body


# ---------------- status endpoint ----------------

def test_status_legal_transition(client, paper):
    r = client.post(
        f"/api/papers/{paper.arxiv_id}/status/",
        {"status": "queued"}, format="json",
    )
    assert r.status_code == 200, r.json()
    assert r.json()["status"] == "queued"
    assert UserPaperStatus.objects.get(paper=paper).status == "queued"


def test_status_illegal_transition_returns_400(client, paper):
    # new → read_kept must skip "reading" first.
    r = client.post(
        f"/api/papers/{paper.arxiv_id}/status/",
        {"status": "read_kept"}, format="json",
    )
    assert r.status_code == 400, r.json()
    body = r.json()
    assert body.get("from") == "new"
    assert body.get("to") == "read_kept"


def test_status_invalid_value_returns_400(client, paper):
    r = client.post(
        f"/api/papers/{paper.arxiv_id}/status/",
        {"status": "made-up"}, format="json",
    )
    assert r.status_code == 400


def test_status_404_for_missing_paper(client, db):
    r = client.post(
        "/api/papers/0000.99999/status/", {"status": "queued"}, format="json",
    )
    assert r.status_code == 404


# ---------------- comments ----------------

def test_comment_post_then_list(client, paper):
    r = client.post(
        f"/api/papers/{paper.arxiv_id}/comments/",
        {"text": "first thought"}, format="json",
    )
    assert r.status_code == 201, r.json()
    cid = r.json()["id"]

    r = client.get(f"/api/papers/{paper.arxiv_id}/comments/")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["id"] == cid
    assert items[0]["text"] == "first thought"
    assert items[0]["hidden"] is False


def test_comment_blank_text_rejected(client, paper):
    r = client.post(
        f"/api/papers/{paper.arxiv_id}/comments/",
        {"text": "   "}, format="json",
    )
    assert r.status_code == 400


def test_comment_patch_only_hidden_allowed(client, paper):
    c = UserComment.objects.create(paper=paper, text="original")
    # Disallowed: text edit
    r = client.patch(
        f"/api/papers/{paper.arxiv_id}/comments/{c.id}/",
        {"text": "edited"}, format="json",
    )
    assert r.status_code == 400, r.json()

    # Allowed: hidden toggle
    r = client.patch(
        f"/api/papers/{paper.arxiv_id}/comments/{c.id}/",
        {"hidden": True}, format="json",
    )
    assert r.status_code == 200, r.json()
    c.refresh_from_db()
    assert c.hidden is True
    # text MUST be untouched (append-only invariant).
    assert c.text == "original"


def test_comment_list_excludes_hidden_by_default(client, paper):
    UserComment.objects.create(paper=paper, text="visible")
    UserComment.objects.create(paper=paper, text="hidden", hidden=True)
    r = client.get(f"/api/papers/{paper.arxiv_id}/comments/")
    texts = [c["text"] for c in r.json()]
    assert "visible" in texts and "hidden" not in texts

    r = client.get(f"/api/papers/{paper.arxiv_id}/comments/?hidden=true")
    texts = [c["text"] for c in r.json()]
    assert "visible" in texts and "hidden" in texts


# ---------------- tags ----------------

def test_tag_add_list_remove(client, paper):
    r = client.post(
        f"/api/papers/{paper.arxiv_id}/tags/", {"tag": "llm"}, format="json",
    )
    assert r.status_code == 201, r.json()
    r = client.get(f"/api/papers/{paper.arxiv_id}/tags/")
    assert r.status_code == 200
    assert r.json() == ["llm"]
    r = client.delete(f"/api/papers/{paper.arxiv_id}/tags/llm/")
    assert r.status_code == 204
    r = client.get(f"/api/papers/{paper.arxiv_id}/tags/")
    assert r.json() == []


def test_tag_duplicate_is_idempotent(client, paper):
    r1 = client.post(
        f"/api/papers/{paper.arxiv_id}/tags/", {"tag": "diffusion"}, format="json",
    )
    assert r1.status_code == 201
    r2 = client.post(
        f"/api/papers/{paper.arxiv_id}/tags/", {"tag": "diffusion"}, format="json",
    )
    assert r2.status_code == 200
    assert r2.json().get("duplicate") is True
    # Still only one row.
    assert UserTag.objects.filter(paper=paper, tag="diffusion").count() == 1


def test_tag_delete_404_when_missing(client, paper):
    r = client.delete(f"/api/papers/{paper.arxiv_id}/tags/no-such/")
    assert r.status_code == 404


def test_tag_blank_rejected(client, paper):
    r = client.post(
        f"/api/papers/{paper.arxiv_id}/tags/", {"tag": "   "}, format="json",
    )
    assert r.status_code == 400


# ---------------- backlinks ----------------

def test_backlink_create_then_bidirectional_get(client, paper, other_paper):
    r = client.post(
        f"/api/papers/{paper.arxiv_id}/backlinks/",
        {"dst": other_paper.key, "relation": "supports", "note": "see fig 3"},
        format="json",
    )
    assert r.status_code == 201, r.json()
    bid = r.json()["id"]

    # Outgoing on src side
    r = client.get(f"/api/papers/{paper.arxiv_id}/backlinks/")
    body = r.json()
    assert len(body["outgoing"]) == 1
    assert body["outgoing"][0]["dst_key"] == other_paper.key
    assert body["outgoing"][0]["relation"] == "supports"
    assert body["incoming"] == []

    # Incoming on dst side (same edge, opposite direction)
    r = client.get(f"/api/papers/{other_paper.arxiv_id}/backlinks/")
    body = r.json()
    assert len(body["incoming"]) == 1
    assert body["incoming"][0]["src_key"] == paper.key
    assert body["incoming"][0]["relation"] == "supports"

    # Delete via either side
    r = client.delete(f"/api/papers/{paper.arxiv_id}/backlinks/{bid}/")
    assert r.status_code == 204


def test_backlink_dst_key_alias_works(client, paper, other_paper):
    """frontend api/papers.ts uses ``dst`` but spec also mentions ``dst_key``."""
    r = client.post(
        f"/api/papers/{paper.arxiv_id}/backlinks/",
        {"dst_key": other_paper.key}, format="json",
    )
    assert r.status_code == 201, r.json()
    assert UserBacklink.objects.filter(src=paper, dst=other_paper).count() == 1


def test_backlink_self_link_rejected(client, paper):
    r = client.post(
        f"/api/papers/{paper.arxiv_id}/backlinks/",
        {"dst": paper.key}, format="json",
    )
    assert r.status_code == 400


def test_backlink_unknown_dst_returns_404(client, paper):
    # 8-char regex matches but no Paper.key=ZZZZZZZZ exists.
    r = client.post(
        f"/api/papers/{paper.arxiv_id}/backlinks/",
        {"dst": "ZZZZZZZZ"}, format="json",
    )
    assert r.status_code == 404
