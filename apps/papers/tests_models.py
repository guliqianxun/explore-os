"""ft-028 model-level tests: ``Paper.gen_key()`` + ``is_legal_transition()``.

Lives in ``apps.papers`` (not ``apps.api``) so it tests the model contract in
isolation: no DRF / no requests, just ORM + the state-machine helper. Covers
the gen_key alphabet, length, retry behaviour, and a representative slice of
the STATUS_TRANSITIONS table.
"""
from __future__ import annotations

import re

import pytest

from apps.papers.models import (
    PAPER_KEY_ALPHABET,
    PAPER_KEY_LEN,
    Paper,
    PaperStatus,
    UserPaperStatus,
    is_legal_transition,
)


_KEY_RE = re.compile(rf"^[{re.escape(PAPER_KEY_ALPHABET)}]{{{PAPER_KEY_LEN}}}$")


# ---------------- gen_key ----------------

def test_gen_key_charset_and_length():
    """gen_key emits 8 chars from the 32-char ``[A-Z2-9]`` alphabet."""
    for _ in range(50):
        k = Paper.gen_key()
        assert len(k) == PAPER_KEY_LEN == 8
        assert _KEY_RE.match(k), f"key {k!r} contains chars outside alphabet"
        # Visual-ambiguity chars MUST NOT appear.
        assert "0" not in k and "1" not in k
        assert "I" not in k and "O" not in k


def test_save_assigns_key_when_blank(db):
    """Paper without explicit key → save() generates one and persists."""
    p = Paper.objects.create(arxiv_id="2401.00001", title="t1")
    assert p.key, "save() should populate key"
    assert _KEY_RE.match(p.key)


def test_save_keeps_caller_provided_key(db):
    """Caller-supplied key wins over auto-gen."""
    p = Paper.objects.create(key="ABCDEF23", arxiv_id="2401.00002", title="t2")
    p.refresh_from_db()
    assert p.key == "ABCDEF23"


def test_gen_key_retries_then_raises_on_persistent_collision(db, monkeypatch):
    """If gen_key keeps colliding, the 3rd IntegrityError must bubble up.

    We force ``Paper.gen_key`` to return a fixed key already taken — every save
    will collide. After 3 retries, ``IntegrityError`` propagates instead of
    silently looping forever.
    """
    Paper.objects.create(key="ZZZZZZZZ", arxiv_id="2401.00003", title="taken")
    monkeypatch.setattr(Paper, "gen_key", classmethod(lambda cls: "ZZZZZZZZ"))
    with pytest.raises(Exception):  # noqa: BLE001 — IntegrityError or wrap
        Paper.objects.create(arxiv_id="2401.00004", title="will-collide")


# ---------------- is_legal_transition ----------------

def test_self_transition_is_idempotent():
    """Same → same is treated legal (idempotent UI clicks)."""
    for s in PaperStatus:
        assert is_legal_transition(s.value, s.value) is True


def test_legal_transitions_matrix():
    """Spot-check the ft-028 STATUS_TRANSITIONS table."""
    # Fresh row → can queue, start reading, or hard-drop / archive.
    assert is_legal_transition("new", "queued")
    assert is_legal_transition("new", "reading")
    assert is_legal_transition("new", "read_dropped")
    assert is_legal_transition("new", "archived")
    # queued → reading is the typical "Read now" path.
    assert is_legal_transition("queued", "reading")
    # While reading you can finalize either way.
    assert is_legal_transition("reading", "read_kept")
    assert is_legal_transition("reading", "read_dropped")
    # read_* states can flip (changed mind).
    assert is_legal_transition("read_kept", "read_dropped")
    assert is_legal_transition("read_dropped", "read_kept")
    # Anything → archived.
    for s in ["new", "queued", "reading", "read_kept", "read_dropped"]:
        assert is_legal_transition(s, "archived")
    # Anything → new (undo / revive).
    for s in ["queued", "reading", "read_kept", "read_dropped", "archived"]:
        assert is_legal_transition(s, "new")


def test_illegal_transitions():
    """Direct new → read_kept skips reading; archived → read_kept skipped."""
    assert is_legal_transition("new", "read_kept") is False
    assert is_legal_transition("queued", "read_kept") is False
    assert is_legal_transition("archived", "read_kept") is False
    assert is_legal_transition("archived", "read_dropped") is False
    # Junk states should be rejected, not raise.
    assert is_legal_transition("new", "made-up") is False
    assert is_legal_transition("made-up", "new") is False


def test_default_status_signal_creates_user_status(db):
    """post_save signal must auto-create UserPaperStatus(new) on Paper insert."""
    p = Paper.objects.create(arxiv_id="2401.SIG001", title="signal test")
    row = UserPaperStatus.objects.get(paper=p)
    assert row.status == PaperStatus.NEW.value
