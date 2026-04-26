"""ft-022: tests for apps.api.views — DRF APIClient happy path。"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from apps.extract.models import Citation, Equation, Figure, Section, Table
from apps.interpret.models import Claim, ClaimEvidence, CounterSignal


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
def sample_paper(db):
    arxiv_id = "2401.99999"
    Section.objects.create(
        material_id=f"{arxiv_id}:section:1",
        paper_arxiv_id=arxiv_id, seq=1, path="Introduction", level=1,
    )
    Figure.objects.create(
        material_id=f"{arxiv_id}:figure:1",
        paper_arxiv_id=arxiv_id, seq=1, fig_label="Figure 1",
        page=2, caption="overview", image_path="",
    )
    Table.objects.create(
        material_id=f"{arxiv_id}:table:1",
        paper_arxiv_id=arxiv_id, seq=1, tbl_label="Table 1",
        page=3, caption="results",
    )
    Equation.objects.create(
        material_id=f"{arxiv_id}:equation:1",
        paper_arxiv_id=arxiv_id, seq=1, page=4,
        latex_or_text="x = y + z" * 3, inline_or_display="display",
    )
    Citation.objects.create(
        material_id=f"{arxiv_id}:citation:1",
        paper_arxiv_id=arxiv_id, seq=1, bibkey="smith2024",
        raw_text="Smith 2024", year=2024,
    )
    claim = Claim.objects.create(
        claim_id=f"{arxiv_id}:claim:1",
        paper_arxiv_id=arxiv_id, text="model X improves Y",
        claim_type="result", confidence=0.8,
    )
    ClaimEvidence.objects.create(
        claim=claim, material_id=f"{arxiv_id}:figure:1", relation="supports",
    )
    CounterSignal.objects.create(
        signal_id=f"{arxiv_id}:signal:1",
        claim=claim, text="dataset is small", signal_type="limitation",
        evidence_material_id=f"{arxiv_id}:section:1",
    )
    return arxiv_id


# ---------------- read views ----------------

def test_health(client):
    r = client.get("/api/health/")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "scheduler_running" in body
    assert "data_dir" in body


def test_paper_list(client, sample_paper):
    r = client.get("/api/papers/")
    assert r.status_code == 200
    items = r.json()
    assert len(items) >= 1
    found = next((it for it in items if it["arxiv_id"] == sample_paper), None)
    assert found is not None
    assert found["n_sections"] == 1
    assert found["n_figures"] == 1
    assert found["n_tables"] == 1
    assert found["n_claims"] == 1


def test_paper_detail(client, sample_paper):
    r = client.get(f"/api/papers/{sample_paper}/")
    assert r.status_code == 200
    body = r.json()
    assert body["arxiv_id"] == sample_paper
    assert len(body["sections"]) == 1
    assert len(body["figures"]) == 1
    assert len(body["tables"]) == 1
    assert len(body["equations"]) == 1
    assert len(body["claims"]) == 1
    claim = body["claims"][0]
    assert claim["text"] == "model X improves Y"
    assert len(claim["evidences"]) == 1
    assert len(claim["counter_signals"]) == 1


def test_paper_detail_404(client, db):
    r = client.get("/api/papers/does-not-exist/")
    assert r.status_code == 404


def test_paper_markdown(client, sample_paper):
    r = client.get(f"/api/papers/{sample_paper}/markdown/")
    assert r.status_code == 200
    assert r["content-type"].startswith("text/markdown")
    body = r.content.decode("utf-8")
    assert sample_paper in body
    assert "Introduction" in body
    assert "model X improves Y" in body


def test_claims_view(client, sample_paper):
    r = client.get(f"/api/papers/{sample_paper}/claims/")
    assert r.status_code == 200
    claims = r.json()
    assert len(claims) == 1


def test_figure_view_404_when_no_image(client, sample_paper):
    r = client.get(f"/api/papers/{sample_paper}/figure/1.png")
    assert r.status_code == 404  # image_path 为空


def test_figure_view_returns_png(client, db, tmp_path):
    arxiv_id = "2401.aaaaa"
    img = tmp_path / "f.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    Figure.objects.create(
        material_id=f"{arxiv_id}:figure:1",
        paper_arxiv_id=arxiv_id, seq=1, image_path=str(img),
    )
    r = client.get(f"/api/papers/{arxiv_id}/figure/1.png")
    assert r.status_code == 200
    assert r["content-type"] == "image/png"


# ---------------- trigger views (mock 业务调用) ----------------

def test_extract_trigger_returns_queued(client, db):
    with patch("apps.api.views._do_extract") as m:
        m.return_value = {"arxiv_id": "x", "counts": {}}
        from apps.api import jobs as jobs_mod
        with patch.object(jobs_mod, "enqueue") as eq:
            from apps.api.jobs import JobInfo
            eq.return_value = JobInfo(job_id="abc123", name="extract:x")
            r = client.post("/api/papers/2401.11111/extract/", {}, format="json")
    assert r.status_code == 202
    body = r.json()
    assert body["job_id"] == "abc123"
    assert body["status"] == "queued"


def test_interpret_trigger_returns_queued(client, db):
    from apps.api import jobs as jobs_mod
    with patch.object(jobs_mod, "enqueue") as eq:
        from apps.api.jobs import JobInfo
        eq.return_value = JobInfo(job_id="def456", name="interpret:x")
        r = client.post("/api/papers/2401.11111/interpret/", {}, format="json")
    assert r.status_code == 202
    assert r.json()["job_id"] == "def456"


def test_render_trigger_returns_queued(client, db):
    from apps.api import jobs as jobs_mod
    with patch.object(jobs_mod, "enqueue") as eq:
        from apps.api.jobs import JobInfo
        eq.return_value = JobInfo(job_id="ghi789", name="render:x:excalidraw")
        r = client.post(
            "/api/papers/2401.11111/render/",
            {"format": "excalidraw"}, format="json",
        )
    assert r.status_code == 202
    assert r.json()["job_id"] == "ghi789"


def test_render_trigger_rejects_bad_format(client, db):
    r = client.post(
        "/api/papers/2401.11111/render/", {"format": "junk"}, format="json",
    )
    assert r.status_code == 400


def test_job_status_view(client, db):
    from apps.api import jobs

    def ok():
        return {"hello": "world"}

    info = jobs.run_inline(ok, name="ok")
    r = client.get(f"/api/jobs/{info.job_id}/")
    assert r.status_code == 200
    body = r.json()
    assert body["job_id"] == info.job_id
    assert body["status"] == "succeeded"
    assert body["result"] == {"hello": "world"}


def test_job_status_404(client, db):
    r = client.get("/api/jobs/does-not-exist/")
    assert r.status_code == 404
