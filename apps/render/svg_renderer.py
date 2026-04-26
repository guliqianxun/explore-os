"""ft-021: SVG renderer —— Cluster Cards 模板（2026-04-26 重写）.

跟 ExcalidrawRenderer 同形态，但纯静态 SVG（任意浏览器 / 邮件可看）。
布局复用 layout_cluster。
"""
from __future__ import annotations

import base64
from pathlib import Path
from xml.sax.saxutils import escape

from apps.render.base import PaperGraphModel
from apps.render.layout import (
    CARD_H,
    CARD_W,
    CHIP_H,
    CHIP_W,
    layout_cluster,
)

HEADER_H = 28
PAD = 16
BODY_Y = HEADER_H + 8
BODY_H = 130
EV_Y = BODY_Y + BODY_H + 8
EV_THUMB_W = 130
EV_THUMB_H = 100
EV_TEXT_PAD = 12

CLAIM_TYPE_COLOR = {
    "proposal":    "#1971c2",
    "result":      "#2f9e44",
    "ablation":    "#e8590c",
    "theoretical": "#7048e8",
}


def _wrap(text: str, max_chars: int) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    out, line = [], ""
    for ch in text:
        if ch == "\n":
            if line:
                out.append(line)
                line = ""
            continue
        line += ch
        if len(line) >= max_chars:
            out.append(line)
            line = ""
    if line:
        out.append(line)
    return out


def _truncate(s: str, n: int) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


class SvgRenderer:
    """实现 GraphRenderer Protocol。Cluster Cards SVG 版。"""

    def render(self, graph: PaperGraphModel, out_dir: Path) -> Path:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        pos = layout_cluster(graph)
        if not pos:
            view_w, view_h = 800, 600
        else:
            xs = [p[0] for p in pos.values()]
            ys = [p[1] for p in pos.values()]
            view_w = max(xs) + CARD_W + 80
            view_h = max(ys) + CARD_H + 80

        body: list[str] = []
        for n in graph.nodes:
            x, y = pos.get(n.node_id, (0, 0))
            if n.kind == "claim":
                body.extend(self._render_claim_card(n, x, y))
            elif n.kind == "citation":
                body.extend(self._render_chip(n, x, y))

        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {view_w} {view_h}" '
            f'width="{view_w}" height="{view_h}" '
            f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif">'
            + "".join(body)
            + "</svg>"
        )
        out_path = out_dir / "graph.svg"
        out_path.write_text(svg, encoding="utf-8")
        return out_path

    def _render_claim_card(self, n, x: int, y: int) -> list[str]:
        out: list[str] = []
        out.append(
            f'<rect x="{x}" y="{y}" width="{CARD_W}" height="{CARD_H}" '
            f'rx="6" fill="#f8f9fa" stroke="#1971c2" stroke-width="1"/>'
        )
        ctype = n.attrs.get("claim_type", "result")
        color = CLAIM_TYPE_COLOR.get(ctype, "#868e96")
        out.append(
            f'<rect x="{x}" y="{y}" width="{CARD_W}" height="{HEADER_H}" '
            f'rx="6" fill="{color}"/>'
        )
        conf = n.attrs.get("confidence", 0.0)
        out.append(
            f'<text x="{x + 8}" y="{y + 19}" fill="#ffffff" font-size="13" font-weight="600">'
            f'[{escape(ctype)}]   conf {conf:.2f}</text>'
        )

        body_lines = _wrap(n.label or "", 36)
        ty = y + BODY_Y + 4
        for line in body_lines[:6]:
            out.append(
                f'<text x="{x + PAD + 4}" y="{ty + 16}" '
                f'fill="#212529" font-size="14">{escape(line)}</text>'
            )
            ty += 22

        ev_y = y + EV_Y
        ev_x = x + PAD
        evidences = n.attrs.get("evidences", []) or []
        section_ev = n.attrs.get("section_evidences", []) or []
        max_ev_y = y + CARD_H - 60

        for ev in evidences:
            if ev_y >= max_ev_y:
                break
            if ev.get("kind") == "figure":
                img_path = ev.get("image_path", "")
                href = self._image_data_url(img_path)
                if href:
                    out.append(
                        f'<image x="{ev_x}" y="{ev_y}" width="{EV_THUMB_W}" '
                        f'height="{EV_THUMB_H}" href="{href}" '
                        f'preserveAspectRatio="xMidYMid meet"/>'
                    )
                else:
                    out.append(
                        f'<rect x="{ev_x}" y="{ev_y}" width="{EV_THUMB_W}" '
                        f'height="{EV_THUMB_H}" fill="#e9ecef" stroke="#adb5bd"/>'
                    )
                cap = _truncate(ev.get("label", "") or "", 90)
                cap_text = f"Fig {ev.get('ref_id', '').split(':')[-1]}: {cap}"
                cap_lines = _wrap(cap_text, 30)
                ty = ev_y + 4
                for line in cap_lines[:5]:
                    out.append(
                        f'<text x="{ev_x + EV_THUMB_W + EV_TEXT_PAD}" y="{ty + 12}" '
                        f'fill="#495057" font-size="11">{escape(line)}</text>'
                    )
                    ty += 16
                ev_y += EV_THUMB_H + 8
            elif ev.get("kind") == "table":
                cap = _truncate(ev.get("label", "") or "", 100)
                line = f"Tbl {ev.get('ref_id', '').split(':')[-1]}: {cap}"
                out.append(
                    f'<text x="{ev_x}" y="{ev_y + 14}" fill="#495057" font-size="12">'
                    f'{escape(line)}</text>'
                )
                ev_y += 22

        for ev in section_ev:
            if ev_y >= max_ev_y:
                break
            line = f"§ {ev.get('label', ev.get('ref_id', ''))}"
            out.append(
                f'<text x="{ev_x}" y="{ev_y + 12}" fill="#868e96" font-size="11">'
                f'{escape(line)}</text>'
            )
            ev_y += 18

        # equation evidence：优先嵌入 mathtext PNG（按原始宽高比缩放）
        eq_ev = n.attrs.get("equation_evidences", []) or []
        EQ_AREA_W = CARD_W - 2 * PAD - 64
        EQ_MAX_H = 56
        for ev in eq_ev[:3]:
            if ev_y >= max_ev_y:
                break
            ref_seq = ev.get("ref_id", "").split(":")[-1]
            href = self._image_data_url(ev.get("image_path", "") or "")
            iw = int(ev.get("image_w") or 0)
            ih = int(ev.get("image_h") or 0)
            if href and iw and ih:
                disp_h = EQ_MAX_H
                disp_w = int(iw * disp_h / ih)
                if disp_w > EQ_AREA_W:
                    disp_w = EQ_AREA_W
                    disp_h = max(20, int(ih * disp_w / iw))
                label_y = ev_y + max(16, disp_h // 2 + 4)
                out.append(
                    f'<text x="{ev_x}" y="{label_y}" fill="#495057" font-size="12">'
                    f'∑ Eq {escape(ref_seq)}</text>'
                )
                out.append(
                    f'<image x="{ev_x + 64}" y="{ev_y}" width="{disp_w}" '
                    f'height="{disp_h}" href="{href}" '
                    f'preserveAspectRatio="xMidYMid meet"/>'
                )
                ev_y += disp_h + 6
            else:
                latex = _truncate(ev.get("label", "") or "", 70)
                line = f"∑ Eq {ref_seq}: {latex}"
                out.append(
                    f'<text x="{ev_x}" y="{ev_y + 12}" fill="#495057" font-size="11" '
                    f'font-family="ui-monospace,Cascadia Code,Menlo,monospace">'
                    f'{escape(line)}</text>'
                )
                ev_y += 18

        css = n.attrs.get("counter_signals", []) or []
        if css:
            n_lines = min(len(css), 3)
            cs_h = 24 + n_lines * 30
            cs_y = y + CARD_H - cs_h
            out.append(
                f'<rect x="{x}" y="{cs_y}" width="{CARD_W}" height="{cs_h}" '
                f'rx="6" fill="#fff0f0" stroke="#e03131"/>'
            )
            ty = cs_y + 18
            for cs in css[:3]:
                t = _truncate(cs.get("text", "") or "", 60)
                line = f"⚠ [{cs.get('signal_type', '')}] {t}"
                out.append(
                    f'<text x="{x + PAD + 4}" y="{ty}" fill="#c92a2a" font-size="11">'
                    f'{escape(line)}</text>'
                )
                ty += 28
        return out

    def _render_chip(self, n, x: int, y: int) -> list[str]:
        return [
            f'<rect x="{x}" y="{y}" width="{CHIP_W}" height="{CHIP_H}" '
            f'rx="6" fill="#f1f3f5" stroke="#868e96"/>',
            f'<text x="{x + 8}" y="{y + 24}" fill="#495057" font-size="11">'
            f'{escape(_truncate(n.label or "", 22))}</text>',
        ]

    def _image_data_url(self, image_path: str) -> str:
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
