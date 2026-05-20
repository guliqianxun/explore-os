from __future__ import annotations

import pytest
from django.test import Client


@pytest.mark.django_db
def test_profile_returns_200():
    c = Client()
    r = c.get("/api/state/profile/")
    assert r.status_code == 200
    data = r.json()
    assert data["user_id"] == 1
    assert "topics" in data
    assert "viewpoints" in data
    assert data["viewpoints"]["total"] == 0


@pytest.mark.django_db
def test_gaps_returns_200():
    c = Client()
    r = c.get("/api/state/gaps/")
    assert r.status_code == 200
    data = r.json()
    assert "prereq" in data
    assert "decay" in data


@pytest.mark.django_db
def test_viewpoint_state_unseen():
    c = Client()
    r = c.get("/api/state/viewpoint/nonexistent/")
    assert r.status_code == 200
    data = r.json()
    assert data["state"] == "unseen"


@pytest.mark.django_db
def test_report_event_bad_request():
    c = Client()
    r = c.post("/api/state/events/", {}, content_type="application/json")
    assert r.status_code == 400


@pytest.mark.django_db
def test_questions_get_empty():
    c = Client()
    r = c.get("/api/state/questions/")
    assert r.status_code == 200
    assert r.json() == []
