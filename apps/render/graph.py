"""ft-021: 从 interpret_* + extract_* 表构建 ``PaperGraphModel``.
（含 LaTeX → PNG 即时渲染：equation evidence 通过 matplotlib.mathtext 转图。）


**Cluster Cards 模板（2026-04-26 重写）**：

每个 claim 是自包含卡片，evidence / counter_signals / citations 全部
**反规范化挂在 claim 节点的 attrs** 上。这样 renderer 直接迭代 claim 节点
画卡片即可，**不再需要跨卡片箭头**。

* 节点：`claim`（主卡片）+ `citation`（底部 chip 行，按需）
* `figure` / `table` 不作为独立节点 —— 嵌在 claim 卡片内部
* `counter_signal` 不作为独立节点 —— 作为 claim 卡片底部红条
* `equation` / `section` 不入图（同 spec lock）
* `edges` 列表保留为空（保留接口，未来 v1.x 可加 inter-claim 关系）
"""
from __future__ import annotations

from pathlib import Path

from django.conf import settings

from apps.render.base import GraphNode, PaperGraphModel
from apps.render.equation_render import png_size, render_latex_to_png


def _equation_image_path(arxiv_id: str, seq: str) -> Path:
    base = Path(getattr(settings, "BASE_DIR", Path.cwd())) / "media" / "equations" / arxiv_id
    return base / f"eq_{seq}.png"


def build_graph(arxiv_id: str) -> PaperGraphModel:
    """从 DB 组装 cluster-oriented PaperGraphModel。"""
    # 局部 import 避免 app loading 顺序问题。
    from apps.extract.models import Citation, Figure, Table
    from apps.interpret.models import Claim, CounterSignal

    nodes: list[GraphNode] = []
    cited_citation_short_ids: dict[str, GraphNode] = {}  # short_id → node（去重）

    claims = (
        Claim.objects.filter(paper_arxiv_id=arxiv_id)
        .prefetch_related("evidences", "counter_signals")
        .order_by("claim_id")
    )

    # 收集所有被 cite 的 figure/table material_id → 详情，避免重复 DB 查询
    fig_cache: dict[str, dict] = {}
    tbl_cache: dict[str, dict] = {}
    cit_cache: dict[str, dict] = {}
    eq_cache: dict[str, dict] = {}

    def _resolve_evidence(material_id: str) -> dict | None:
        """material_id → 反规范化字典（kind/label/image_path/page/etc）。
        equation / section 返回 None（不入卡片）。"""
        parts = material_id.split(":")
        if len(parts) < 3:
            return None
        kind = parts[-2]
        seq = parts[-1]
        ref_id = f"{kind}:{seq}"
        if kind == "figure":
            if material_id not in fig_cache:
                f = Figure.objects.filter(material_id=material_id).first()
                fig_cache[material_id] = (
                    {
                        "kind": "figure",
                        "ref_id": ref_id,
                        "label": (f.caption or "")[:200],
                        "image_path": f.image_path or "",
                        "page": f.page,
                    }
                    if f
                    else None
                )
            return fig_cache[material_id]
        if kind == "table":
            if material_id not in tbl_cache:
                t = Table.objects.filter(material_id=material_id).first()
                tbl_cache[material_id] = (
                    {
                        "kind": "table",
                        "ref_id": ref_id,
                        "label": (t.caption or "")[:200],
                        "page": t.page,
                    }
                    if t
                    else None
                )
            return tbl_cache[material_id]
        if kind == "citation":
            if material_id not in cit_cache:
                c = Citation.objects.filter(material_id=material_id).first()
                cit_cache[material_id] = (
                    {
                        "kind": "citation",
                        "ref_id": ref_id,
                        "bibkey": c.bibkey,
                        "year": c.year,
                        "label": f"{c.bibkey} ({c.year if c.year is not None else '?'})",
                    }
                    if c
                    else None
                )
            return cit_cache[material_id]
        if kind == "section":
            return {"kind": "section", "ref_id": ref_id, "label": ""}
        if kind == "equation":
            if material_id not in eq_cache:
                from apps.extract.models import Equation
                eq = Equation.objects.filter(material_id=material_id).first()
                if eq:
                    latex = (eq.latex_or_text or "").strip()
                    img_path = _equation_image_path(arxiv_id, seq)
                    rendered = render_latex_to_png(latex, img_path) if latex else False
                    dims = png_size(img_path) if rendered else None
                    eq_cache[material_id] = {
                        "kind": "equation",
                        "ref_id": ref_id,
                        "label": latex[:300],
                        "page": eq.page,
                        "image_path": str(img_path) if rendered else "",
                        "image_w": dims[0] if dims else 0,
                        "image_h": dims[1] if dims else 0,
                    }
                else:
                    eq_cache[material_id] = None
            return eq_cache[material_id]
        return None

    for c in claims:
        seq = c.claim_id.rsplit(":", 1)[1]
        node_id = f"claim:{seq}"

        evidences: list[dict] = []
        section_evidences: list[dict] = []
        equation_evidences: list[dict] = []
        citations_in_claim: list[dict] = []
        for e in c.evidences.all():
            ev = _resolve_evidence(e.material_id)
            if ev is None:
                continue
            ev["relation"] = e.relation
            if ev["kind"] == "section":
                section_evidences.append(ev)
            elif ev["kind"] == "equation":
                equation_evidences.append(ev)
            elif ev["kind"] == "citation":
                citations_in_claim.append(ev)
                # 同时累积到全局 chip 行
                if ev["ref_id"] not in cited_citation_short_ids:
                    cited_citation_short_ids[ev["ref_id"]] = GraphNode(
                        node_id=ev["ref_id"],
                        kind="citation",
                        label=ev["label"],
                        attrs={"bibkey": ev["bibkey"], "year": ev["year"]},
                    )
            else:
                evidences.append(ev)

        counter_signals: list[dict] = []
        for cs in c.counter_signals.all().order_by("signal_id"):
            ev = _resolve_evidence(cs.evidence_material_id)
            counter_signals.append(
                {
                    "text": cs.text,
                    "signal_type": cs.signal_type,
                    "evidence_ref_id": ev["ref_id"] if ev else "",
                    "evidence_label": ev["label"] if ev else "",
                }
            )

        nodes.append(
            GraphNode(
                node_id=node_id,
                kind="claim",
                label=c.text,  # 完整文本，渲染时 wrap，不再 [:40]
                attrs={
                    "claim_type": c.claim_type,
                    "confidence": c.confidence,
                    "claim_id": c.claim_id,
                    "evidences": evidences,
                    "section_evidences": section_evidences,
                    "equation_evidences": equation_evidences,
                    "counter_signals": counter_signals,
                    "citations": citations_in_claim,
                },
            )
        )

    # 同时也兜底扫一遍 counter_signal 的 evidence（可能引到没出现在 evidences 里的 material）
    cs_qs = (
        CounterSignal.objects.filter(claim__paper_arxiv_id=arxiv_id)
        .select_related("claim")
        .order_by("signal_id")
    )
    for cs in cs_qs:
        ev = _resolve_evidence(cs.evidence_material_id)
        if ev and ev["kind"] == "citation":
            if ev["ref_id"] not in cited_citation_short_ids:
                cited_citation_short_ids[ev["ref_id"]] = GraphNode(
                    node_id=ev["ref_id"],
                    kind="citation",
                    label=ev["label"],
                    attrs={"bibkey": ev["bibkey"], "year": ev["year"]},
                )

    # citation chip 行（全局去重，按 ref_id 排序）
    citation_nodes = [cited_citation_short_ids[k] for k in sorted(cited_citation_short_ids)]
    nodes.extend(citation_nodes)

    # cluster 模式：edges 为空（关系全部内嵌进 claim attrs）
    return PaperGraphModel(paper_arxiv_id=arxiv_id, nodes=nodes, edges=[])
