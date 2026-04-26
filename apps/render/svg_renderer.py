"""ft-021: SVG fallback renderer.

最简实现，纯静态可嵌邮件 / 浏览器：节点 ``<rect>`` + ``<text>``，figure 用
``<image href="data:image/png;base64,...">``，边用 ``<line>`` + 居中 ``<text>``。
布局复用 ``apps.render.layout._layout``（与 ExcalidrawRenderer 同源）。
"""
from __future__ import annotations

import base64
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from apps.render.base import PaperGraphModel
from apps.render.layout import _layout

NODE_W = 240
NODE_H = 80
FIGURE_W = 240
FIGURE_H = 160

NODE_STROKE = {
    "claim":    "#1971c2",
    "table":    "#7048e8",
    "citation": "#868e96",
    "figure":   "#2f9e44",
}
NODE_FILL = {
    "claim":    "#e7f5ff",
    "table":    "#f3f0ff",
    "citation": "#f1f3f5",
    "figure":   "#ebfbee",
}

EDGE_STROKE = {
    "supports":    "#1971c2",
    "illustrates": "#2f9e44",
    "contradicts": "#e03131",
    "cites":       "#868e96",
}


class SvgRenderer:
    """实现 ``apps.render.base.GraphRenderer`` Protocol（SVG 兜底）。"""

    def render(self, graph: PaperGraphModel, out_dir: Path) -> Path:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        pos = _layout(graph)

        # 计算 viewBox
        if pos:
            xs = [p[0] for p in pos.values()]
            ys = [p[1] for p in pos.values()]
            min_x, max_x = min(xs) - 40, max(xs) + NODE_W + 40
            min_y, max_y = min(ys) - 40, max(ys) + max(NODE_H, FIGURE_H) + 40
        else:
            min_x, min_y, max_x, max_y = 0, 0, 800, 600
        width = max_x - min_x
        height = max_y - min_y

        parts: list[str] = []
        parts.append(
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="{min_x} {min_y} {width} {height}" '
            f'width="{width}" height="{height}">'
        )
        # defs: arrow marker
        parts.append(
            '<defs>'
            '<marker id="arrow" viewBox="0 0 10 10" refX="10" refY="5" '
            'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
            '<path d="M0,0 L10,5 L0,10 z" fill="context-stroke"/>'
            '</marker>'
            '</defs>'
        )

        # --- 边（先画，节点叠在上方） ---
        for e in graph.edges:
            sp = pos.get(e.from_id)
            tp = pos.get(e.to_id)
            if not sp or not tp:
                continue
            x1 = sp[0] + NODE_W // 2
            y1 = sp[1] + NODE_H
            x2 = tp[0] + NODE_W // 2
            y2 = tp[1]
            stroke = EDGE_STROKE[e.kind]
            dash = ' stroke-dasharray="6,4"' if e.kind == "contradicts" else ""
            parts.append(
                f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                f'stroke="{stroke}" stroke-width="2"{dash} '
                f'marker-end="url(#arrow)"/>'
            )
            if e.label:
                mx, my = (x1 + x2) // 2, (y1 + y2) // 2
                parts.append(
                    f'<text x="{mx}" y="{my}" font-size="12" fill="{stroke}" '
                    f'text-anchor="middle">{xml_escape(e.label)}</text>'
                )

        # --- 节点 ---
        for n in graph.nodes:
            x, y = pos.get(n.node_id, (0, 0))
            if n.kind == "figure":
                href = self._figure_href(n.attrs.get("image_path", ""))
                if href:
                    parts.append(
                        f'<image href="{href}" x="{x}" y="{y}" '
                        f'width="{FIGURE_W}" height="{FIGURE_H}"/>'
                    )
                else:
                    # 占位 rect
                    parts.append(
                        f'<rect x="{x}" y="{y}" width="{FIGURE_W}" height="{FIGURE_H}" '
                        f'fill="{NODE_FILL["figure"]}" stroke="{NODE_STROKE["figure"]}"/>'
                    )
                if n.label:
                    parts.append(
                        f'<text x="{x}" y="{y + FIGURE_H + 14}" font-size="12" '
                        f'fill="#212529">{xml_escape(n.label)}</text>'
                    )
                continue

            stroke = NODE_STROKE[n.kind]
            fill = NODE_FILL[n.kind]
            parts.append(
                f'<rect x="{x}" y="{y}" width="{NODE_W}" height="{NODE_H}" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="1.5" rx="6"/>'
            )
            parts.append(
                f'<text x="{x + 10}" y="{y + 26}" font-size="14" fill="#212529">'
                f'{xml_escape(n.label or n.node_id)}</text>'
            )

        parts.append("</svg>")

        out_path = out_dir / "graph.svg"
        out_path.write_text("".join(parts), encoding="utf-8")
        return out_path

    def _figure_href(self, image_path: str) -> str:
        if not image_path:
            return ""
        p = Path(image_path)
        if not p.is_file():
            return ""
        try:
            data = p.read_bytes()
        except OSError:
            return ""
        b64 = base64.b64encode(data).decode("ascii")
        return f"data:image/png;base64,{b64}"
