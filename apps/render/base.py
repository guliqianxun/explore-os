"""ft-021: 图谱渲染器接口契约 + dataclass.

PaperGraphModel 是图谱抽象层，由 ``apps.render.graph.build_graph`` 从
``apps.interpret.models`` + ``apps.extract.models`` 组装而来。
具体 renderer（Excalidraw / SVG）只消费 PaperGraphModel，不直接读 DB。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

NodeKind = Literal["claim", "figure", "table", "citation"]
EdgeKind = Literal["supports", "illustrates", "contradicts", "cites"]


@dataclass
class GraphNode:
    node_id: str          # claim:1 / figure:3 / table:5 / citation:42
    kind: NodeKind
    label: str            # 节点显示文字（claim 短摘要 / caption 头部 / bibkey）
    attrs: dict = field(default_factory=dict)


@dataclass
class GraphEdge:
    from_id: str
    to_id: str
    kind: EdgeKind
    label: str = ""


@dataclass
class PaperGraphModel:
    paper_arxiv_id: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class GraphRenderer(Protocol):
    def render(self, graph: PaperGraphModel, out_dir: Path) -> Path: ...
