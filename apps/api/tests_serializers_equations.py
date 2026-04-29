"""ft-034 P0-6 + review-D D1: EquationSerializer field completeness."""
from __future__ import annotations

import pytest

from apps.api.serializers.equations import EquationSerializer
from apps.extract.models import Equation
from apps.papers.models import Paper


@pytest.fixture(autouse=True)
def _shutdown_scheduler_after():
    yield
    from apps.api import jobs
    from apps.core import scheduler
    scheduler.shutdown_scheduler(wait=True)
    jobs.reset_for_tests()


def test_equation_serializer_emits_all_8_fields(db):
    """Per ft-034 P0-6: paper_arxiv_id / eq_label / bbox 必须出现在 DTO."""
    paper = Paper.objects.create(arxiv_id="2401.66666", key="EQSER001")
    eq = Equation.objects.create(
        material_id="2401.66666::eq1",
        paper=paper,
        paper_arxiv_id="2401.66666",
        seq=0,
        eq_label="(2)",
        page=5,
        bbox=[1.0, 2.0, 3.0, 4.0],
        latex_or_text=r"\sum_i x_i",
        inline_or_display="display",
    )
    data = EquationSerializer(eq).data
    expected = {
        "material_id", "paper_arxiv_id", "seq", "eq_label", "page",
        "bbox", "latex_or_text", "inline_or_display",
    }
    assert set(data.keys()) == expected
    assert data["paper_arxiv_id"] == "2401.66666"
    assert data["eq_label"] == "(2)"
    assert data["bbox"] == [1.0, 2.0, 3.0, 4.0]


def test_equation_serializer_handles_null_bbox_and_eq_label(db):
    paper = Paper.objects.create(arxiv_id="2401.55555", key="EQSER002")
    eq = Equation.objects.create(
        material_id="2401.55555::eq1",
        paper=paper,
        paper_arxiv_id="2401.55555",
        seq=0,
        eq_label=None,
        page=0,
        bbox=None,
        latex_or_text="x",
        inline_or_display="inline",
    )
    data = EquationSerializer(eq).data
    assert data["bbox"] is None
    assert data["eq_label"] is None


def test_equation_serializer_many_preserves_order(db):
    """``many=True`` 输出按 queryset 顺序（PaperDetailView 走 ``order_by("seq")``）."""
    paper = Paper.objects.create(arxiv_id="2401.44444", key="EQSER003")
    for i in range(3):
        Equation.objects.create(
            material_id=f"2401.44444::eq{i}",
            paper=paper,
            paper_arxiv_id="2401.44444",
            seq=i,
            latex_or_text=f"eq{i}",
            inline_or_display="display",
        )
    qs = Equation.objects.filter(paper=paper).order_by("seq")
    data = EquationSerializer(qs, many=True).data
    assert [d["seq"] for d in data] == [0, 1, 2]
    assert [d["latex_or_text"] for d in data] == ["eq0", "eq1", "eq2"]
