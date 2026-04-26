"""ft-021: 从 interpret_* + extract_* 表构建 ``PaperGraphModel``.

规则锁定（与 dsp-005 / ft-021 spec 一致）：

* 节点四类：claim / figure / table / citation；equation / section 不入图。
* counter_signal 简化为 ``contradicts`` 边注解，不作为独立节点。
* node_id 用短形（``claim:1`` / ``figure:3``），与 ``material_id`` 全形（``<arxiv>:<type>:<seq>``）
  通过 ``rsplit(':', 1)[1]`` 双向映射。
"""
from __future__ import annotations

from apps.render.base import GraphEdge, GraphNode, PaperGraphModel


def build_graph(arxiv_id: str) -> PaperGraphModel:
    """从 DB 组装 PaperGraphModel。"""
    # 局部 import 避免 app loading 顺序问题。
    from apps.extract.models import Citation, Figure, Table
    from apps.interpret.models import Claim, CounterSignal

    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    cited_materials: dict[str, str] = {}  # full material_id → short

    claims = (
        Claim.objects.filter(paper_arxiv_id=arxiv_id)
        .prefetch_related("evidences")
        .order_by("claim_id")
    )
    for c in claims:
        seq = c.claim_id.rsplit(":", 1)[1]
        node_id = f"claim:{seq}"
        nodes.append(GraphNode(
            node_id=node_id,
            kind="claim",
            label=c.text[:40] + ("…" if len(c.text) > 40 else ""),
            attrs={
                "claim_type": c.claim_type,
                "confidence": c.confidence,
                "claim_id": c.claim_id,
            },
        ))
        for e in c.evidences.all():
            # material_id: <arxiv_id>:<type>:<seq>
            parts = e.material_id.split(":")
            if len(parts) < 3:
                continue
            kind = parts[-2]
            if kind not in ("figure", "table", "citation"):
                continue  # equation / section 不入图（spec lock）
            short = f"{kind}:{e.material_id.rsplit(':', 1)[1]}"
            cited_materials[e.material_id] = short
            edge_kind = "illustrates" if e.relation == "illustrates" else "supports"
            edges.append(GraphEdge(from_id=node_id, to_id=short, kind=edge_kind))

    # counter_signal 简化为「contradicts」边
    signals = (
        CounterSignal.objects.filter(claim__paper_arxiv_id=arxiv_id)
        .select_related("claim")
        .order_by("signal_id")
    )
    for cs in signals:
        claim_seq = cs.claim.claim_id.rsplit(":", 1)[1]
        parts = cs.evidence_material_id.split(":")
        if len(parts) < 3:
            continue
        ev_kind = parts[-2]
        if ev_kind not in ("figure", "table", "citation"):
            continue
        short = f"{ev_kind}:{cs.evidence_material_id.rsplit(':', 1)[1]}"
        cited_materials[cs.evidence_material_id] = short
        edges.append(GraphEdge(
            from_id=f"claim:{claim_seq}",
            to_id=short,
            kind="contradicts",
            label=cs.signal_type,
        ))

    # 把被 cite 的 material 加成节点
    for full, short in cited_materials.items():
        kind = full.split(":")[-2]
        if kind == "figure":
            f = Figure.objects.filter(material_id=full).first()
            if f:
                nodes.append(GraphNode(
                    node_id=short,
                    kind="figure",
                    label=(f.caption or "")[:30],
                    attrs={"image_path": f.image_path, "page": f.page},
                ))
        elif kind == "table":
            t = Table.objects.filter(material_id=full).first()
            if t:
                nodes.append(GraphNode(
                    node_id=short,
                    kind="table",
                    label=(t.caption or "")[:30],
                    attrs={"page": t.page},
                ))
        elif kind == "citation":
            c = Citation.objects.filter(material_id=full).first()
            if c:
                nodes.append(GraphNode(
                    node_id=short,
                    kind="citation",
                    label=f"{c.bibkey} ({c.year if c.year is not None else '?'})",
                    attrs={"raw_text": c.raw_text[:200]},
                ))

    return PaperGraphModel(paper_arxiv_id=arxiv_id, nodes=nodes, edges=edges)
