"""ft-021: build_graph() 结构化测试 —— Cluster Cards 模型（2026-04-26 重写）.

cluster 模式下：
- 节点 = claim + 全局 citation chip（去重）；figure / table / section 不作独立节点
- edges 始终为空（关系内嵌进 claim attrs）
- claim attrs 包含 evidences / section_evidences / counter_signals / citations
"""
from __future__ import annotations

import pytest

from apps.extract.models import Citation, Equation, Figure, Section, Table
from apps.interpret.models import Claim, ClaimEvidence, CounterSignal
from apps.render.graph import build_graph

pytestmark = pytest.mark.django_db

ARXIV = "2401.99001"


def _seed():
    Figure.objects.create(
        material_id=f"{ARXIV}:figure:1", paper_arxiv_id=ARXIV, seq=1,
        caption="Figure 1: pipeline overview", image_path="", page=2,
    )
    Figure.objects.create(
        material_id=f"{ARXIV}:figure:2", paper_arxiv_id=ARXIV, seq=2,
        caption="Figure 2: ablation curve", image_path="", page=5,
    )
    Table.objects.create(
        material_id=f"{ARXIV}:table:1", paper_arxiv_id=ARXIV, seq=1,
        caption="Table 1: SOTA comparison", page=4,
    )
    Citation.objects.create(
        material_id=f"{ARXIV}:citation:1", paper_arxiv_id=ARXIV, seq=1,
        bibkey="vaswani2017", year=2017, raw_text="Attention is all you need.",
    )
    Equation.objects.create(
        material_id=f"{ARXIV}:equation:1", paper_arxiv_id=ARXIV, seq=1,
        latex_or_text="E=mc^2",
    )
    Section.objects.create(
        material_id=f"{ARXIV}:section:1", paper_arxiv_id=ARXIV, seq=1,
        path="Intro", level=1,
    )

    c1 = Claim.objects.create(
        claim_id=f"{ARXIV}:claim:1", paper_arxiv_id=ARXIV,
        text="Our method outperforms SOTA by 3.2%.",
        claim_type="result", confidence=0.9,
    )
    c2 = Claim.objects.create(
        claim_id=f"{ARXIV}:claim:2", paper_arxiv_id=ARXIV,
        text="A novel masked-image pretraining objective is proposed for ConvNets.",
        claim_type="proposal", confidence=0.85,
    )

    ClaimEvidence.objects.create(claim=c1, material_id=f"{ARXIV}:table:1",    relation="supports")
    ClaimEvidence.objects.create(claim=c1, material_id=f"{ARXIV}:figure:1",   relation="illustrates")
    ClaimEvidence.objects.create(claim=c1, material_id=f"{ARXIV}:citation:1", relation="supports")
    ClaimEvidence.objects.create(claim=c2, material_id=f"{ARXIV}:equation:1", relation="quantifies")
    ClaimEvidence.objects.create(claim=c2, material_id=f"{ARXIV}:section:1",  relation="supports")

    CounterSignal.objects.create(
        signal_id=f"{ARXIV}:signal:1", claim=c1,
        text="Ablation drop on small data.",
        signal_type="ablation_drop",
        evidence_material_id=f"{ARXIV}:figure:2",
    )
    return c1, c2


def test_cluster_node_kinds_only_claim_and_citation():
    _seed()
    g = build_graph(ARXIV)
    kinds = {n.kind for n in g.nodes}
    # cluster 模式：figure/table/section 不作独立节点；只剩 claim + citation chip
    assert kinds == {"claim", "citation"}


def test_cluster_node_counts():
    _seed()
    g = build_graph(ARXIV)
    by_kind = {k: 0 for k in ("claim", "citation")}
    for n in g.nodes:
        by_kind[n.kind] += 1
    assert by_kind == {"claim": 2, "citation": 1}


def test_cluster_edges_always_empty():
    _seed()
    g = build_graph(ARXIV)
    assert g.edges == []


def test_claim_attrs_evidences_filter_kinds():
    _seed()
    g = build_graph(ARXIV)
    c1 = next(n for n in g.nodes if n.node_id == "claim:1")
    ev_kinds = [e["kind"] for e in c1.attrs["evidences"]]
    # claim 1 evidence: table + figure（citation 走 attrs.citations，不在 evidences）
    assert "table" in ev_kinds
    assert "figure" in ev_kinds
    # equation 已被过滤
    assert "equation" not in ev_kinds


def test_claim_attrs_citations_separated():
    _seed()
    g = build_graph(ARXIV)
    c1 = next(n for n in g.nodes if n.node_id == "claim:1")
    cit_keys = [c["bibkey"] for c in c1.attrs["citations"]]
    assert cit_keys == ["vaswani2017"]


def test_claim_attrs_section_evidences():
    _seed()
    g = build_graph(ARXIV)
    c2 = next(n for n in g.nodes if n.node_id == "claim:2")
    se = c2.attrs["section_evidences"]
    assert len(se) == 1
    assert se[0]["ref_id"] == "section:1"


def test_claim_attrs_counter_signals_full_text():
    _seed()
    g = build_graph(ARXIV)
    c1 = next(n for n in g.nodes if n.node_id == "claim:1")
    cs = c1.attrs["counter_signals"]
    assert len(cs) == 1
    assert cs[0]["text"] == "Ablation drop on small data."
    assert cs[0]["signal_type"] == "ablation_drop"
    assert cs[0]["evidence_ref_id"] == "figure:2"


def test_claim_label_full_text_no_truncation():
    """cluster 模式下保留完整文本，渲染时由 renderer 自行 wrap。"""
    _seed()
    g = build_graph(ARXIV)
    c2 = next(n for n in g.nodes if n.node_id == "claim:2")
    assert "ConvNets" in c2.label   # 完整保留
    assert not c2.label.endswith("…")


def test_citation_chip_dedup():
    """同 citation 被多个 claim 引用时，全局 chip 行只出现一次。"""
    _seed()
    # 让 claim 2 也 cite citation:1
    c2 = Claim.objects.get(claim_id=f"{ARXIV}:claim:2")
    ClaimEvidence.objects.create(claim=c2, material_id=f"{ARXIV}:citation:1", relation="supports")
    g = build_graph(ARXIV)
    cits = [n for n in g.nodes if n.kind == "citation"]
    assert len(cits) == 1


def test_build_graph_empty_for_unknown_arxiv():
    g = build_graph("nonexistent-paper")
    assert g.paper_arxiv_id == "nonexistent-paper"
    assert g.nodes == []
    assert g.edges == []
