"""ft-034 P0-7 + P0-6: tests for views package + EquationSerializer integration.

Verifies:
- ``apps.api.views`` package re-export keeps ``from apps.api.views import X``
  imports working (URL routing depends on this).
- ``PaperDetailView.equations`` now exposes ``paper_arxiv_id`` / ``eq_label``
  / ``bbox`` (review-D D1 hotspot fix).
- ``resolve_paper`` 8-char key short-circuit still works through the package.
"""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.extract.models import Equation, Section
from apps.papers.models import Paper


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


def test_views_package_reexports_all_classes():
    """ft-034 P0-7: ``urls.py`` 不变要求 — 老 import 必须仍可用。"""
    from apps.api.views import (  # noqa: F401
        ClaimsView,
        ExtractTriggerView,
        FigureView,
        HealthView,
        InterpretTriggerView,
        JobStatusView,
        PaperBacklinkDetailView,
        PaperBacklinkView,
        PaperBriefRegenerateView,
        PaperBriefView,
        PaperCommentDetailView,
        PaperCommentListView,
        PaperDetailView,
        PaperListView,
        PaperMarkdownView,
        PaperPdfView,
        PaperStatusView,
        PaperTagDetailView,
        PaperTagListView,
        RenderTriggerView,
        resolve_paper,
    )


def test_paper_detail_equations_includes_paper_arxiv_id_eq_label_bbox(client, db):
    """review-D D1: EquationDTO 缺字段 → 用 EquationSerializer 全字段输出."""
    paper = Paper.objects.create(arxiv_id="2401.99999", key="EQDTOTST", title="t")
    Section.objects.create(
        material_id="2401.99999::sec1",
        paper=paper,
        paper_arxiv_id=paper.arxiv_id,
        seq=0,
        path="Intro",
        raw_text="hi",
    )
    Equation.objects.create(
        material_id="2401.99999::eq1",
        paper=paper,
        paper_arxiv_id=paper.arxiv_id,
        seq=0,
        eq_label="(1)",
        page=3,
        bbox=[10.0, 20.0, 100.0, 50.0],
        latex_or_text=r"E = mc^2",
        inline_or_display="display",
    )
    r = client.get(f"/api/papers/{paper.arxiv_id}/")
    assert r.status_code == 200
    eqs = r.json()["equations"]
    assert len(eqs) == 1
    e = eqs[0]
    # Old in-line dict was missing these three; review-D D1 fix:
    assert e["paper_arxiv_id"] == "2401.99999"
    assert e["eq_label"] == "(1)"
    assert e["bbox"] == [10.0, 20.0, 100.0, 50.0]
    # Existing fields preserved
    assert e["material_id"] == "2401.99999::eq1"
    assert e["latex_or_text"] == r"E = mc^2"
    assert e["inline_or_display"] == "display"


def test_paper_detail_equations_null_bbox_eq_label_serializes_as_none(client, db):
    """eq_label / bbox 都允许 null（不是所有抽取器都给）."""
    paper = Paper.objects.create(arxiv_id="2401.88888", key="NULLEQTS", title="t")
    Section.objects.create(
        material_id="2401.88888::sec1",
        paper=paper,
        paper_arxiv_id=paper.arxiv_id,
        seq=0,
        path="Intro",
    )
    Equation.objects.create(
        material_id="2401.88888::eq1",
        paper=paper,
        paper_arxiv_id=paper.arxiv_id,
        seq=0,
        eq_label=None,
        page=0,
        bbox=None,
        latex_or_text="x",
        inline_or_display="inline",
    )
    r = client.get(f"/api/papers/{paper.arxiv_id}/")
    assert r.status_code == 200
    e = r.json()["equations"][0]
    assert e["eq_label"] is None
    assert e["bbox"] is None


def test_resolve_paper_via_package_export_handles_8char_key(db):
    """package re-export 后 resolve_paper 仍按 ``[A-Z2-9]{8}`` 走 key 列。"""
    from apps.api.views import resolve_paper

    paper = Paper.objects.create(arxiv_id="2401.77777", key="K2L4M5N6", title="x")
    found = resolve_paper("K2L4M5N6")
    assert found.id == paper.id
    found_via_arxiv = resolve_paper("2401.77777")
    assert found_via_arxiv.id == paper.id
