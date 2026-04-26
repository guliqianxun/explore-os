"""ft-021: ExcalidrawRenderer Cluster Cards 模板验证（2026-04-26 重写）.

不依赖 DB。构造小 PaperGraphModel（cluster 形态：claim attrs 含 evidences /
counter_signals / citations）→ render → 校验 JSON schema。
"""
from __future__ import annotations

import base64
import json

from apps.render.base import GraphNode, PaperGraphModel
from apps.render.excalidraw_renderer import ExcalidrawRenderer

# 1x1 transparent PNG
_PNG_1x1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


def _make_cluster_graph(image_path: str = "") -> PaperGraphModel:
    """两张 claim 卡片 + 一张 citation chip。claim:1 含 figure 缩略 + counter_signal。"""
    nodes = [
        GraphNode(
            "claim:1", "claim",
            "Our method outperforms SOTA by 3.2 percent on the benchmark.",
            {
                "claim_type": "result",
                "confidence": 0.9,
                "claim_id": "test:claim:1",
                "evidences": [
                    {"kind": "figure", "ref_id": "figure:1",
                     "label": "Figure 1: pipeline overview", "image_path": image_path,
                     "page": 2},
                    {"kind": "table", "ref_id": "table:1",
                     "label": "Table 1: SOTA comparison", "page": 4},
                ],
                "section_evidences": [],
                "counter_signals": [
                    {"text": "Ablation drop on small data.",
                     "signal_type": "ablation_drop",
                     "evidence_ref_id": "figure:2",
                     "evidence_label": "Figure 2: ablation curve"},
                ],
                "citations": [],
            },
        ),
        GraphNode(
            "claim:2", "claim",
            "A novel masked-image pretraining objective for ConvNets.",
            {
                "claim_type": "proposal",
                "confidence": 0.85,
                "claim_id": "test:claim:2",
                "evidences": [],
                "section_evidences": [
                    {"kind": "section", "ref_id": "section:1", "label": "1. Introduction"},
                ],
                "counter_signals": [],
                "citations": [
                    {"ref_id": "citation:1", "bibkey": "vaswani2017", "year": 2017,
                     "label": "vaswani2017 (2017)"},
                ],
            },
        ),
        GraphNode(
            "citation:1", "citation",
            "vaswani2017 (2017)",
            {"bibkey": "vaswani2017", "year": 2017},
        ),
    ]
    return PaperGraphModel("test-paper", nodes, [])  # cluster 模式 edges 永远空


def test_render_top_level_schema(tmp_path):
    out = ExcalidrawRenderer().render(_make_cluster_graph(), tmp_path)
    assert out.exists()
    assert out.name == "graph.excalidraw"
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["type"] == "excalidraw"
    assert doc["version"] == 2
    assert doc["source"] == "explore-os"
    assert "elements" in doc
    assert "files" in doc
    assert "appState" in doc


def test_render_no_arrows_in_cluster_mode(tmp_path):
    """cluster 模式不画跨卡片箭头。"""
    out = ExcalidrawRenderer().render(_make_cluster_graph(), tmp_path)
    doc = json.loads(out.read_text(encoding="utf-8"))
    arrows = [el for el in doc["elements"] if el["type"] == "arrow"]
    assert arrows == []


def test_render_claim_card_has_card_frame_and_header(tmp_path):
    """每张 claim 卡片：外框 rect + header strip rect + body inner rect (+ counter_signal rect)."""
    out = ExcalidrawRenderer().render(_make_cluster_graph(), tmp_path)
    doc = json.loads(out.read_text(encoding="utf-8"))
    rects = [el for el in doc["elements"] if el["type"] == "rectangle"]
    # claim:1: card + header + body_inner + cs_bg + cs_inner = 5
    # claim:2: card + header + body_inner = 3 (无 counter_signal)
    # citation:1 chip = 1
    # 共 9 个 rect
    assert len(rects) == 9


def test_render_embeds_figure_thumbnail(tmp_path):
    img = tmp_path / "fig1.png"
    img.write_bytes(_PNG_1x1)
    g = _make_cluster_graph(image_path=str(img))
    out = ExcalidrawRenderer().render(g, tmp_path)
    doc = json.loads(out.read_text(encoding="utf-8"))
    images = [el for el in doc["elements"] if el["type"] == "image"]
    assert len(images) == 1   # claim:1 的 figure evidence 嵌入一张缩略
    assert len(doc["files"]) == 1
    file_obj = next(iter(doc["files"].values()))
    assert file_obj["mimeType"] == "image/png"
    assert file_obj["dataURL"].startswith("data:image/png;base64,")
    assert images[0]["fileId"] in doc["files"]


def test_render_no_files_when_image_missing(tmp_path):
    g = _make_cluster_graph(image_path="")
    out = ExcalidrawRenderer().render(g, tmp_path)
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["files"] == {}


def test_render_claim_full_text_in_card(tmp_path):
    """完整 claim text 应出现（不再 [:40] 截断）。"""
    out = ExcalidrawRenderer().render(_make_cluster_graph(), tmp_path)
    doc = json.loads(out.read_text(encoding="utf-8"))
    text_elts = [el for el in doc["elements"] if el["type"] == "text"]
    all_text = "\n".join(el.get("text", "") for el in text_elts)
    assert "outperforms SOTA by 3.2" in all_text
    assert "ConvNets" in all_text


def test_render_counter_signal_shown_with_signal_type(tmp_path):
    out = ExcalidrawRenderer().render(_make_cluster_graph(), tmp_path)
    doc = json.loads(out.read_text(encoding="utf-8"))
    text_elts = [el for el in doc["elements"] if el["type"] == "text"]
    all_text = "\n".join(el.get("text", "") for el in text_elts)
    assert "ablation_drop" in all_text
    assert "Ablation drop on small data" in all_text


def test_render_section_evidence_uses_section_marker(tmp_path):
    out = ExcalidrawRenderer().render(_make_cluster_graph(), tmp_path)
    doc = json.loads(out.read_text(encoding="utf-8"))
    text_elts = [el for el in doc["elements"] if el["type"] == "text"]
    all_text = "\n".join(el.get("text", "") for el in text_elts)
    assert "§" in all_text
    assert "1. Introduction" in all_text
