"""ft-021: 共用极简分层布局.

规则（不做自动布局，留给后续 v1.x dagre/elkjs）：

* y=100：claim 行（按 confidence 降序，间隔 280px）
* y=350：figure / table 行（间隔 280px）
* y=600：citation 行（间隔 280px）

返回 ``{node_id: (x, y)}``。
"""
from __future__ import annotations

from apps.render.base import PaperGraphModel

ROW_Y_CLAIM = 100
ROW_Y_EVIDENCE = 350     # figure / table
ROW_Y_CITATION = 600

X_START = 100
X_STRIDE = 280


def _layout(graph: PaperGraphModel) -> dict[str, tuple[int, int]]:
    """简单分层布局：claim → figure/table → citation 三行。"""
    pos: dict[str, tuple[int, int]] = {}

    # claim 行 —— 按 confidence 降序，再按 node_id 稳定排序
    claims = [n for n in graph.nodes if n.kind == "claim"]
    claims.sort(
        key=lambda n: (-(n.attrs.get("confidence") or 0.0), n.node_id),
    )
    for i, n in enumerate(claims):
        pos[n.node_id] = (X_START + i * X_STRIDE, ROW_Y_CLAIM)

    # figure / table 行
    evid = [n for n in graph.nodes if n.kind in ("figure", "table")]
    evid.sort(key=lambda n: n.node_id)
    for i, n in enumerate(evid):
        pos[n.node_id] = (X_START + i * X_STRIDE, ROW_Y_EVIDENCE)

    # citation 行
    cits = [n for n in graph.nodes if n.kind == "citation"]
    cits.sort(key=lambda n: n.node_id)
    for i, n in enumerate(cits):
        pos[n.node_id] = (X_START + i * X_STRIDE, ROW_Y_CITATION)

    return pos
