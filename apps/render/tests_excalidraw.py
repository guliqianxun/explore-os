"""ft-021: ExcalidrawRenderer 输出 schema 验证.

不依赖 DB。构造小 PaperGraphModel → render → ``json.loads()`` 校验：
- top-level ``type == "excalidraw"``
- elements 数 = rect/image + text + arrow 之和
- files 字段含 base64 image
- 边色 strokeColor 按 kind 正确
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

from apps.render.base import GraphEdge, GraphNode, PaperGraphModel
from apps.render.excalidraw_renderer import ExcalidrawRenderer

# 1x1 transparent PNG
_PNG_1x1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


def _make_graph(tmp_image: Path | None = None) -> PaperGraphModel:
    nodes = [
        GraphNode("claim:1", "claim", "Our method beats SOTA",
                  {"claim_type": "result", "confidence": 0.9}),
        GraphNode("claim:2", "claim", "A novel pretraining objective",
                  {"claim_type": "proposal", "confidence": 0.8}),
        GraphNode("figure:1", "figure", "Fig 1: overview",
                  {"image_path": str(tmp_image) if tmp_image else "", "page": 2}),
        GraphNode("table:1", "table", "Tab 1: SOTA", {"page": 4}),
        GraphNode("citation:1", "citation", "vaswani2017 (2017)", {}),
    ]
    edges = [
        GraphEdge("claim:1", "table:1", "supports"),
        GraphEdge("claim:1", "figure:1", "illustrates"),
        GraphEdge("claim:2", "citation:1", "cites"),
        GraphEdge("claim:1", "figure:1", "contradicts", label="ablation_drop"),
    ]
    return PaperGraphModel("test-paper", nodes, edges)


def test_render_top_level_schema(tmp_path):
    out = ExcalidrawRenderer().render(_make_graph(), tmp_path)
    assert out.exists()
    assert out.name == "graph.excalidraw"
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["type"] == "excalidraw"
    assert doc["version"] == 2
    assert doc["source"] == "explore-os"
    assert "elements" in doc
    assert "files" in doc
    assert "appState" in doc


def test_render_elements_count(tmp_path):
    """3 rect 节点 (claim*2 + table + citation = 4 rect) + 4 text(rect 内) + 1 image + 1 caption-text + 4 arrow.

    更稳的断言：分别按 type 计数。"""
    g = _make_graph()
    out = ExcalidrawRenderer().render(g, tmp_path)
    doc = json.loads(out.read_text(encoding="utf-8"))
    by_type: dict[str, int] = {}
    for el in doc["elements"]:
        by_type[el["type"]] = by_type.get(el["type"], 0) + 1

    # 4 rect 节点（claim:1, claim:2, table:1, citation:1）
    assert by_type.get("rectangle") == 4
    # 1 image（figure:1）
    assert by_type.get("image") == 1
    # text: 每 rect 一个 + figure caption 一个 = 5
    assert by_type.get("text") == 5
    # arrow: 每条边一个
    assert by_type.get("arrow") == 4

    # 总元素数
    assert len(doc["elements"]) == 4 + 1 + 5 + 4


def test_render_embeds_figure_as_base64(tmp_path):
    img = tmp_path / "fig1.png"
    img.write_bytes(_PNG_1x1)
    g = _make_graph(tmp_image=img)
    out = ExcalidrawRenderer().render(g, tmp_path)
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert len(doc["files"]) == 1
    file_id, file_obj = next(iter(doc["files"].items()))
    assert file_obj["mimeType"] == "image/png"
    assert file_obj["dataURL"].startswith("data:image/png;base64,")
    # image element 的 fileId 应当指向该 file
    img_elts = [el for el in doc["elements"] if el["type"] == "image"]
    assert img_elts[0]["fileId"] == file_id


def test_render_skips_files_when_image_missing(tmp_path):
    g = _make_graph(tmp_image=None)
    out = ExcalidrawRenderer().render(g, tmp_path)
    doc = json.loads(out.read_text(encoding="utf-8"))
    # image_path 为空 → files 为空但 image element 仍在
    assert doc["files"] == {}
    assert any(el["type"] == "image" for el in doc["elements"])


def test_render_edge_colors_per_kind(tmp_path):
    g = _make_graph()
    out = ExcalidrawRenderer().render(g, tmp_path)
    doc = json.loads(out.read_text(encoding="utf-8"))
    arrows = [el for el in doc["elements"] if el["type"] == "arrow"]
    colors = sorted(a["strokeColor"] for a in arrows)
    # supports 蓝 + illustrates 绿 + cites 灰 + contradicts 红
    assert colors == sorted(["#1971c2", "#2f9e44", "#868e96", "#e03131"])
    # contradicts 必须 dashed
    contra = [a for a in arrows if a["strokeColor"] == "#e03131"]
    assert contra[0]["strokeStyle"] == "dashed"


def test_render_arrow_bindings_link_node_elements(tmp_path):
    g = _make_graph()
    out = ExcalidrawRenderer().render(g, tmp_path)
    doc = json.loads(out.read_text(encoding="utf-8"))
    elt_ids = {el["id"] for el in doc["elements"]
               if el["type"] in ("rectangle", "image")}
    for arrow in (el for el in doc["elements"] if el["type"] == "arrow"):
        assert arrow["startBinding"]["elementId"] in elt_ids
        assert arrow["endBinding"]["elementId"] in elt_ids
