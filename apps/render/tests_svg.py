"""ft-021: SvgRenderer Cluster Cards 模板验证（2026-04-26 重写）.

不依赖 DB。断言 SVG 含 claim 卡片矩形 / figure 缩略 image / counter_signal 红条 等。
"""
from __future__ import annotations

import base64

from apps.render.base import GraphNode, PaperGraphModel
from apps.render.svg_renderer import SvgRenderer

_PNG_1x1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


def _cluster_graph(image_path: str = "") -> PaperGraphModel:
    nodes = [
        GraphNode(
            "claim:1", "claim",
            "Our method outperforms SOTA by 3.2 percent.",
            {
                "claim_type": "result", "confidence": 0.9,
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
                     "evidence_label": "Figure 2"},
                ],
                "citations": [],
            },
        ),
        GraphNode(
            "claim:2", "claim",
            "A novel pretraining objective.",
            {
                "claim_type": "proposal", "confidence": 0.7,
                "evidences": [],
                "section_evidences": [
                    {"kind": "section", "ref_id": "section:1", "label": "1. Intro"},
                ],
                "counter_signals": [],
                "citations": [],
            },
        ),
        GraphNode("citation:1", "citation", "vaswani2017 (2017)", {}),
    ]
    return PaperGraphModel("test-paper", nodes, [])


def test_svg_outputs_file(tmp_path):
    out = SvgRenderer().render(_cluster_graph(), tmp_path)
    assert out.exists()
    assert out.name == "graph.svg"
    text = out.read_text(encoding="utf-8")
    assert text.startswith("<svg")
    assert text.endswith("</svg>")


def test_svg_no_lines_in_cluster_mode(tmp_path):
    """cluster 模式不画跨卡片箭头/线。"""
    out = SvgRenderer().render(_cluster_graph(), tmp_path)
    text = out.read_text(encoding="utf-8")
    assert text.count("<line") == 0


def test_svg_contains_claim_card_rects(tmp_path):
    """每张 claim 卡片：外框 + header strip；含 counter_signal 还多一个红条；
    无图时 figure evidence 退化为占位 rect；citation chip 一个 rect。"""
    out = SvgRenderer().render(_cluster_graph(), tmp_path)
    text = out.read_text(encoding="utf-8")
    # claim:1 = card + header + cs_strip + figure_placeholder = 4 (image_path="")
    # claim:2 = card + header = 2
    # citation:1 chip = 1
    # 共 7 个 rect
    assert text.count("<rect") == 7


def test_svg_embeds_figure_image(tmp_path):
    img = tmp_path / "fig1.png"
    img.write_bytes(_PNG_1x1)
    out = SvgRenderer().render(_cluster_graph(image_path=str(img)), tmp_path)
    text = out.read_text(encoding="utf-8")
    assert text.count("<image") == 1
    assert "data:image/png;base64," in text


def test_svg_no_image_falls_back_to_placeholder(tmp_path):
    out = SvgRenderer().render(_cluster_graph(image_path=""), tmp_path)
    text = out.read_text(encoding="utf-8")
    assert text.count("<image") == 0
    # 占位 rect 替代 image，多 1 个 rect → 7
    assert text.count("<rect") == 7


def test_svg_counter_signal_text_rendered(tmp_path):
    out = SvgRenderer().render(_cluster_graph(), tmp_path)
    text = out.read_text(encoding="utf-8")
    assert "ablation_drop" in text
    assert "Ablation drop on small data" in text


def test_svg_section_evidence_marker(tmp_path):
    out = SvgRenderer().render(_cluster_graph(), tmp_path)
    text = out.read_text(encoding="utf-8")
    assert "§" in text
    assert "1. Intro" in text


def test_svg_claim_full_text_no_truncation(tmp_path):
    out = SvgRenderer().render(_cluster_graph(), tmp_path)
    text = out.read_text(encoding="utf-8")
    assert "outperforms SOTA by 3.2" in text
