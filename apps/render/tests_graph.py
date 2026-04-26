"""ft-021: build_graph() 结构化测试.

直接在 SQLite 真写 Claim + ClaimEvidence + CounterSignal + Figure + Table + Citation
（不需要 mock LLM / docling），断言 build_graph() 输出 nodes / edges 数量、
kind 正确，且 counter_signal 转 contradicts 边。
"""
from __future__ import annotations

import pytest

from apps.extract.models import Citation, Equation, Figure, Section, Table
from apps.interpret.models import Claim, ClaimEvidence, CounterSignal
from apps.render.graph import build_graph

pytestmark = pytest.mark.django_db

ARXIV = "2401.99001"


def _seed():
    # extract materials —— 包含 figure / table / citation / equation / section（后两个不入图）
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

    # 2 claims
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

    # Evidence: c1 supports table:1 + illustrates figure:1; c2 supports equation:1 (skip!)
    ClaimEvidence.objects.create(
        claim=c1, material_id=f"{ARXIV}:table:1", relation="supports",
    )
    ClaimEvidence.objects.create(
        claim=c1, material_id=f"{ARXIV}:figure:1", relation="illustrates",
    )
    ClaimEvidence.objects.create(
        claim=c1, material_id=f"{ARXIV}:citation:1", relation="supports",
    )
    # equation / section 不应入图
    ClaimEvidence.objects.create(
        claim=c2, material_id=f"{ARXIV}:equation:1", relation="quantifies",
    )
    ClaimEvidence.objects.create(
        claim=c2, material_id=f"{ARXIV}:section:1", relation="supports",
    )

    # counter signal: claim c1 contradicted by figure:2 ablation drop
    CounterSignal.objects.create(
        signal_id=f"{ARXIV}:signal:1", claim=c1,
        text="Ablation drop on small data.",
        signal_type="ablation_drop",
        evidence_material_id=f"{ARXIV}:figure:2",
    )
    return c1, c2


def test_build_graph_node_kinds_only_four():
    _seed()
    g = build_graph(ARXIV)
    kinds = {n.kind for n in g.nodes}
    # claim + figure + table + citation；equation/section 严禁入图
    assert kinds == {"claim", "figure", "table", "citation"}


def test_build_graph_node_counts():
    _seed()
    g = build_graph(ARXIV)
    by_kind = {k: 0 for k in ("claim", "figure", "table", "citation")}
    for n in g.nodes:
        by_kind[n.kind] += 1
    # 2 claims + figure:1 + figure:2 (from counter) + table:1 + citation:1
    assert by_kind == {"claim": 2, "figure": 2, "table": 1, "citation": 1}


def test_build_graph_node_id_short_form():
    _seed()
    g = build_graph(ARXIV)
    ids = {n.node_id for n in g.nodes}
    assert "claim:1" in ids
    assert "claim:2" in ids
    assert "figure:1" in ids
    assert "figure:2" in ids  # from counter signal
    assert "table:1" in ids
    assert "citation:1" in ids
    # 无全形（无 arxiv 前缀）
    assert all(not nid.startswith(ARXIV) for nid in ids)


def test_build_graph_edge_kinds():
    _seed()
    g = build_graph(ARXIV)
    # claim:1 → table:1 (supports), figure:1 (illustrates), citation:1 (supports)
    # claim:1 → figure:2 (contradicts) ← from counter signal
    edge_tuples = {(e.from_id, e.to_id, e.kind) for e in g.edges}
    assert ("claim:1", "table:1", "supports") in edge_tuples
    assert ("claim:1", "figure:1", "illustrates") in edge_tuples
    assert ("claim:1", "citation:1", "supports") in edge_tuples
    assert ("claim:1", "figure:2", "contradicts") in edge_tuples
    # equation / section evidence 不入边
    assert not any("equation" in e.to_id for e in g.edges)
    assert not any("section" in e.to_id for e in g.edges)


def test_build_graph_counter_signal_label_carries_signal_type():
    _seed()
    g = build_graph(ARXIV)
    contradicts = [e for e in g.edges if e.kind == "contradicts"]
    assert len(contradicts) == 1
    assert contradicts[0].label == "ablation_drop"


def test_build_graph_claim_label_truncated():
    _seed()
    g = build_graph(ARXIV)
    c2 = next(n for n in g.nodes if n.node_id == "claim:2")
    # 长 text 应被截到 40 字 + 省略号
    assert c2.label.endswith("…")
    assert len(c2.label) <= 41


def test_build_graph_citation_label_has_bibkey_and_year():
    _seed()
    g = build_graph(ARXIV)
    cit = next(n for n in g.nodes if n.node_id == "citation:1")
    assert "vaswani2017" in cit.label
    assert "2017" in cit.label


def test_build_graph_empty_for_unknown_arxiv():
    g = build_graph("nonexistent-paper")
    assert g.paper_arxiv_id == "nonexistent-paper"
    assert g.nodes == []
    assert g.edges == []
