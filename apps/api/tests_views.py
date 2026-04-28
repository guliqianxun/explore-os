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
    # sample_paper's section has no raw_text → figure 1 falls into the
    # trailing ## Figures bucket and still renders.
    assert "## Figures" in body
    assert "figures/1.png" in body


def test_paper_markdown_interleaves_figures_by_caption_similarity(client, db):
    """Figures land under the section whose raw_text shares the most caption words."""
    arxiv_id = "2402.55555"
    Section.objects.create(
        material_id=f"{arxiv_id}:section:1",
        paper_arxiv_id=arxiv_id, seq=1, path="Methodology", level=1,
        raw_text=(
            "We propose a novel transformer architecture with sparse attention "
            "and rotary position embedding for efficient long context modeling."
        ),
    )
    Section.objects.create(
        material_id=f"{arxiv_id}:section:2",
        paper_arxiv_id=arxiv_id, seq=2, path="Experiments", level=1,
        raw_text=(
            "We evaluate on benchmark datasets reporting BLEU and accuracy "
            "across multiple seeds. Ablation removes rotary embedding."
        ),
    )
    # caption matches Methodology (transformer / sparse / attention)
    Figure.objects.create(
        material_id=f"{arxiv_id}:figure:1",
        paper_arxiv_id=arxiv_id, seq=1, fig_label="Figure 1",
        page=2, caption="Sparse transformer attention architecture overview",
        image_path="",
    )
    # caption matches Experiments (benchmark / accuracy / ablation)
    Figure.objects.create(
        material_id=f"{arxiv_id}:figure:2",
        paper_arxiv_id=arxiv_id, seq=2, fig_label="Figure 2",
        page=4, caption="Benchmark accuracy curves and ablation results",
        image_path="",
    )
    # caption shares no content words with either section → orphan
    Figure.objects.create(
        material_id=f"{arxiv_id}:figure:3",
        paper_arxiv_id=arxiv_id, seq=3, fig_label="Figure 3",
        page=6, caption="qualitative samples cherry picked outputs",
        image_path="",
    )

    r = client.get(f"/api/papers/{arxiv_id}/markdown/")
    assert r.status_code == 200
    body = r.content.decode("utf-8")

    # Figure 1 must appear after Methodology and before Experiments.
    methodology = body.index("Methodology")
    experiments = body.index("Experiments")
    fig1 = body.index("figures/1.png")
    fig2 = body.index("figures/2.png")
    assert methodology < fig1 < experiments, (
        "figure 1 should be interleaved into Methodology section"
    )
    # Figure 2 must appear after Experiments.
    assert experiments < fig2, "figure 2 should be interleaved into Experiments section"

    # Figure 3 falls into trailing ## Figures bucket.
    figures_bucket = body.index("## Figures")
    fig3 = body.index("figures/3.png")
    assert figures_bucket < fig3, "figure 3 with no overlap should fall into orphan bucket"

    # The orphan bucket must NOT contain figures 1 or 2 (they were interleaved).
    orphan_segment = body[figures_bucket:]
    assert "figures/1.png" not in orphan_segment
    assert "figures/2.png" not in orphan_segment


def test_paper_markdown_no_figures_bucket_when_all_matched(client, db):
    """When every figure matches, no orphan ## Figures section is emitted."""
    arxiv_id = "2403.66666"
    Section.objects.create(
        material_id=f"{arxiv_id}:section:1",
        paper_arxiv_id=arxiv_id, seq=1, path="Method", level=1,
        raw_text="We design a novel diffusion model for video generation tasks.",
    )
    Figure.objects.create(
        material_id=f"{arxiv_id}:figure:1",
        paper_arxiv_id=arxiv_id, seq=1, fig_label="Figure 1",
        page=1, caption="Diffusion model video generation pipeline",
        image_path="",
    )

    r = client.get(f"/api/papers/{arxiv_id}/markdown/")
    assert r.status_code == 200
    body = r.content.decode("utf-8")
    assert "figures/1.png" in body
    assert "## Figures" not in body


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


# =============================================================================
# ft-027: subscription CRUD + run + ingest endpoints
# =============================================================================

@pytest.fixture
def yaml_path(tmp_path, settings):
    """临时 subscriptions.yaml 路径，注入 settings 让 view 看到。"""
    p = tmp_path / "subscriptions.yaml"
    p.write_text("subscriptions: []\n", encoding="utf-8")
    settings.SUBSCRIPTIONS_YAML = str(p)
    return p


def _sample_sub(name: str = "demo") -> dict:
    return {
        "name": name,
        "enabled": True,
        "interests": ["video generation"],
        "exclude": [],
        "sources": [{"key": "arxiv", "params": {"since_days": 1}}],
        "deliveries": [{"channel": "email", "to": "x@y.z",
                        "depth": "tldr", "schedule": "0 8 * * *",
                        "max_items": 15}],
        "perspective": {"preset": "researcher", "custom": ""},
    }


def test_subscription_list_empty(client, yaml_path):
    r = client.get("/api/subscriptions/")
    assert r.status_code == 200
    assert r.json() == []


def test_subscription_create_then_list(client, yaml_path):
    r = client.post("/api/subscriptions/", _sample_sub("demo"), format="json")
    assert r.status_code == 201, r.json()
    body = r.json()
    assert body["name"] == "demo"
    assert body["interests"] == ["video generation"]

    r = client.get("/api/subscriptions/")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1 and items[0]["name"] == "demo"


def test_subscription_create_conflict(client, yaml_path):
    client.post("/api/subscriptions/", _sample_sub("demo"), format="json")
    r = client.post("/api/subscriptions/", _sample_sub("demo"), format="json")
    assert r.status_code == 409


def test_subscription_detail_and_404(client, yaml_path):
    client.post("/api/subscriptions/", _sample_sub("demo"), format="json")
    r = client.get("/api/subscriptions/demo/")
    assert r.status_code == 200
    assert r.json()["name"] == "demo"

    r = client.get("/api/subscriptions/missing/")
    assert r.status_code == 404


def test_subscription_update(client, yaml_path):
    client.post("/api/subscriptions/", _sample_sub("demo"), format="json")
    edited = _sample_sub("demo")
    edited["interests"] = ["multimodal", "agents"]
    r = client.put("/api/subscriptions/demo/", edited, format="json")
    assert r.status_code == 200
    assert r.json()["interests"] == ["multimodal", "agents"]


def test_subscription_delete(client, yaml_path):
    client.post("/api/subscriptions/", _sample_sub("demo"), format="json")
    r = client.delete("/api/subscriptions/demo/")
    assert r.status_code == 204
    r = client.get("/api/subscriptions/demo/")
    assert r.status_code == 404


def test_subscription_run_returns_queued(client, yaml_path):
    client.post("/api/subscriptions/", _sample_sub("demo"), format="json")
    from apps.api import jobs as jobs_mod
    with patch.object(jobs_mod, "enqueue") as eq:
        from apps.api.jobs import JobInfo
        eq.return_value = JobInfo(job_id="run123", name="run-sub:demo")
        r = client.post("/api/subscriptions/demo/run/", {}, format="json")
    assert r.status_code == 202
    assert r.json()["job_id"] == "run123"


def test_subscription_run_404(client, yaml_path):
    r = client.post("/api/subscriptions/missing/run/", {}, format="json")
    assert r.status_code == 404


# ---------------- ingest ----------------

PDF_BYTES = b"%PDF-1.4\n%fake test pdf\n"


def test_ingest_upload_happy(client, db):
    import apps.api.ingest_views as iv
    from django.core.files.uploadedfile import SimpleUploadedFile
    with patch.object(iv, "chain_extract_interpret_render") as ch:
        from apps.api.jobs import JobInfo
        ch.return_value = JobInfo(job_id="up123", name="ingest:abc")
        f = SimpleUploadedFile("paper.pdf", PDF_BYTES, content_type="application/pdf")
        r = client.post("/api/ingest/upload/",
                        {"file": f, "paper_id": "test-paper"},
                        format="multipart")
    assert r.status_code == 202, r.content
    body = r.json()
    assert body["job_id"] == "up123"
    assert body["paper_id"] == "test-paper"


def test_ingest_upload_rejects_non_pdf(client, db):
    from django.core.files.uploadedfile import SimpleUploadedFile
    f = SimpleUploadedFile("notes.txt", b"hello", content_type="text/plain")
    r = client.post("/api/ingest/upload/", {"file": f}, format="multipart")
    assert r.status_code == 400


def test_ingest_arxiv_happy(client, db, tmp_path):
    import apps.api.ingest_views as iv
    from sources import pdf_fetcher as pf
    # patch _download to skip network — pretend file already cached
    pdf_path = pf.local_pdf_path("2401.12345")
    pdf_path.write_bytes(PDF_BYTES)
    try:
        with patch.object(iv, "chain_extract_interpret_render") as ch:
            from apps.api.jobs import JobInfo
            ch.return_value = JobInfo(job_id="ax123", name="ingest:2401.12345")
            r = client.post("/api/ingest/arxiv/",
                            {"arxiv_id": "2401.12345"}, format="json")
        assert r.status_code == 202, r.content
        assert r.json()["job_id"] == "ax123"
    finally:
        pdf_path.unlink(missing_ok=True)


def test_ingest_arxiv_rejects_bad_id(client, db):
    r = client.post("/api/ingest/arxiv/", {"arxiv_id": "junk"}, format="json")
    assert r.status_code == 400


def test_ingest_url_happy(client, db):
    """mock httpx.stream + chain。"""
    from contextlib import contextmanager
    from unittest.mock import MagicMock
    import apps.api.ingest_views as iv

    @contextmanager
    def fake_stream(method, url, **kw):
        resp = MagicMock()
        resp.headers = {"content-type": "application/pdf"}
        resp.raise_for_status = lambda: None
        resp.iter_bytes = lambda chunk_size=64*1024: iter([PDF_BYTES])
        yield resp

    with patch.object(iv.httpx, "stream", side_effect=fake_stream), \
         patch.object(iv, "chain_extract_interpret_render") as ch:
        from apps.api.jobs import JobInfo
        ch.return_value = JobInfo(job_id="u123", name="ingest:abc")
        r = client.post(
            "/api/ingest/url/",
            {"url": "https://arxiv.org/pdf/2401.12345.pdf",
             "paper_id": "from-url"},
            format="json",
        )
    assert r.status_code == 202, r.content
    body = r.json()
    assert body["job_id"] == "u123"
    assert body["paper_id"] == "from-url"


def test_ingest_url_rejects_non_http(client, db):
    r = client.post("/api/ingest/url/", {"url": "ftp://x.com/y.pdf"},
                    format="json")
    assert r.status_code == 400
