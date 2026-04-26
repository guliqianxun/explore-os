"""ft-021: persist_artifact() 幂等性测试."""
from __future__ import annotations

import pytest

from apps.render.models import RenderArtifact
from apps.render.persist import persist_artifact

pytestmark = pytest.mark.django_db

ARXIV = "2401.99001"


def test_persist_creates_artifact(tmp_path):
    p = tmp_path / "graph.excalidraw"
    p.write_text("{}", encoding="utf-8")
    obj = persist_artifact(ARXIV, "excalidraw", p, payload_meta={"n_nodes": 5})

    assert obj.artifact_id == f"{ARXIV}:graph_excalidraw"
    assert obj.artifact_type == "graph_excalidraw"
    assert obj.paper_arxiv_id == ARXIV
    assert obj.payload_path == str(p)
    assert obj.payload_meta == {"n_nodes": 5}
    assert RenderArtifact.objects.count() == 1


def test_persist_idempotent_same_format(tmp_path):
    p = tmp_path / "graph.excalidraw"
    p.write_text("{}", encoding="utf-8")
    persist_artifact(ARXIV, "excalidraw", p)
    persist_artifact(ARXIV, "excalidraw", p)
    persist_artifact(ARXIV, "excalidraw", p)
    assert RenderArtifact.objects.count() == 1


def test_persist_two_formats_two_rows(tmp_path):
    p1 = tmp_path / "graph.excalidraw"
    p1.write_text("{}", encoding="utf-8")
    p2 = tmp_path / "graph.svg"
    p2.write_text("<svg/>", encoding="utf-8")
    persist_artifact(ARXIV, "excalidraw", p1)
    persist_artifact(ARXIV, "svg", p2)
    assert RenderArtifact.objects.count() == 2
    ids = sorted(RenderArtifact.objects.values_list("artifact_id", flat=True))
    assert ids == [f"{ARXIV}:graph_excalidraw", f"{ARXIV}:graph_svg"]


def test_persist_updates_payload_meta_on_rerun(tmp_path):
    p = tmp_path / "graph.excalidraw"
    p.write_text("{}", encoding="utf-8")
    persist_artifact(ARXIV, "excalidraw", p, payload_meta={"n_nodes": 5})
    persist_artifact(ARXIV, "excalidraw", p, payload_meta={"n_nodes": 7})
    obj = RenderArtifact.objects.get(artifact_id=f"{ARXIV}:graph_excalidraw")
    assert obj.payload_meta == {"n_nodes": 7}
