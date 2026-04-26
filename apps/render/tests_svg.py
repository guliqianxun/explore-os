"""ft-021: SvgRenderer 输出验证.

不依赖 DB。断言 ``<svg>`` 含 ``<rect>`` / ``<image>`` / ``<line>`` 数量正确。
"""
from __future__ import annotations

import base64

from apps.render.base import GraphEdge, GraphNode, PaperGraphModel
from apps.render.svg_renderer import SvgRenderer

_PNG_1x1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


def _graph(image_path: str = "") -> PaperGraphModel:
    return PaperGraphModel(
        "test-paper",
        nodes=[
            GraphNode("claim:1", "claim", "C1", {"confidence": 0.9}),
            GraphNode("claim:2", "claim", "C2", {"confidence": 0.7}),
            GraphNode("figure:1", "figure", "Fig overview", {"image_path": image_path}),
            GraphNode("table:1", "table", "Tab 1", {}),
            GraphNode("citation:1", "citation", "vaswani2017 (2017)", {}),
        ],
        edges=[
            GraphEdge("claim:1", "figure:1", "illustrates"),
            GraphEdge("claim:1", "table:1", "supports"),
            GraphEdge("claim:2", "citation:1", "cites"),
            GraphEdge("claim:1", "figure:1", "contradicts", label="ablation_drop"),
        ],
    )


def test_svg_outputs_file(tmp_path):
    out = SvgRenderer().render(_graph(), tmp_path)
    assert out.exists()
    assert out.name == "graph.svg"
    text = out.read_text(encoding="utf-8")
    assert text.startswith("<svg")
    assert text.endswith("</svg>")


def test_svg_contains_rects_and_lines_and_image(tmp_path):
    img = tmp_path / "fig1.png"
    img.write_bytes(_PNG_1x1)
    out = SvgRenderer().render(_graph(image_path=str(img)), tmp_path)
    text = out.read_text(encoding="utf-8")
    # 4 个 rect 节点（claim*2 + table + citation）
    assert text.count("<rect") == 4
    # 1 个 image（figure:1）
    assert text.count("<image") == 1
    # 4 条 line（边）
    assert text.count("<line") == 4
    # contradicts 边走 dasharray
    assert "stroke-dasharray" in text


def test_svg_no_image_falls_back_to_rect(tmp_path):
    """image_path 为空时 figure 节点退化为占位 rect。"""
    out = SvgRenderer().render(_graph(image_path=""), tmp_path)
    text = out.read_text(encoding="utf-8")
    assert text.count("<image") == 0
    # 此时 figure 也变成 rect → 5 rect
    assert text.count("<rect") == 5


def test_svg_edge_label_rendered(tmp_path):
    out = SvgRenderer().render(_graph(), tmp_path)
    text = out.read_text(encoding="utf-8")
    assert "ablation_drop" in text
