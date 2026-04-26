"""ft-021: Excalidraw renderer.

输出标准 Excalidraw JSON（``.excalidraw`` 后缀）。可拖入 excalidraw.com /
桌面 app 直接打开。schema 5 年稳定（参考 packages/excalidraw/data/types.ts）。

约束：
* 不引第三方 nanoid 依赖；用 ``_nanoid()`` 自己生成 16 字符随机 id。
* figure 节点的 PNG 走 base64 dataURL，写入 ``files`` 字段；rect 用 ``image`` element。
* 边色固定：supports 蓝 / illustrates 绿 / contradicts 红 dashed / cites 灰。
* 布局走 ``apps.render.layout._layout``，与 SVG renderer 共享。
"""
from __future__ import annotations

import base64
import json
import secrets
import string
import time
from pathlib import Path

from apps.render.base import PaperGraphModel
from apps.render.layout import _layout

# ---------------- 样式常量 ----------------

NODE_W = 240
NODE_H = 80
FIGURE_W = 240
FIGURE_H = 160

NODE_STYLE: dict[str, dict[str, str]] = {
    "claim":    {"strokeColor": "#1971c2", "backgroundColor": "#e7f5ff"},
    "table":    {"strokeColor": "#7048e8", "backgroundColor": "#f3f0ff"},
    "citation": {"strokeColor": "#868e96", "backgroundColor": "#f1f3f5"},
    # figure 走 image element，不需要 fill；保留占位以避免 KeyError
    "figure":   {"strokeColor": "#2f9e44", "backgroundColor": "#ebfbee"},
}

EDGE_STYLE: dict[str, dict[str, str]] = {
    "supports":     {"strokeColor": "#1971c2", "strokeStyle": "solid"},
    "illustrates":  {"strokeColor": "#2f9e44", "strokeStyle": "solid"},
    "contradicts":  {"strokeColor": "#e03131", "strokeStyle": "dashed"},
    "cites":        {"strokeColor": "#868e96", "strokeStyle": "solid"},
}


# ---------------- 工具 ----------------

_NANOID_ALPHABET = string.ascii_letters + string.digits + "_-"


def _nanoid(n: int = 16) -> str:
    """16 字符随机 id（不引依赖）。"""
    return "".join(secrets.choice(_NANOID_ALPHABET) for _ in range(n))


def _now_ms() -> int:
    return int(time.time() * 1000)


def _base_element(*, etype: str, eid: str, x: int, y: int, w: int, h: int) -> dict:
    return {
        "id": eid,
        "type": etype,
        "x": x,
        "y": y,
        "width": w,
        "height": h,
        "angle": 0,
        "strokeWidth": 1,
        "strokeStyle": "solid",
        "roughness": 1,
        "opacity": 100,
        "groupIds": [],
        "frameId": None,
        "roundness": None,
        "seed": secrets.randbelow(2**31),
        "version": 1,
        "versionNonce": secrets.randbelow(2**31),
        "isDeleted": False,
        "boundElements": [],
        "updated": _now_ms(),
        "link": None,
        "locked": False,
    }


# ---------------- Renderer ----------------

class ExcalidrawRenderer:
    """实现 ``apps.render.base.GraphRenderer`` Protocol。"""

    def render(self, graph: PaperGraphModel, out_dir: Path) -> Path:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        pos = _layout(graph)
        elements: list[dict] = []
        files: dict[str, dict] = {}
        # node_id → element id（rect 或 image），arrow 绑定用
        node_elt_id: dict[str, str] = {}

        # --- 节点 ---
        for n in graph.nodes:
            x, y = pos.get(n.node_id, (0, 0))

            if n.kind == "figure":
                file_id = _nanoid()
                self._maybe_embed_file(n.attrs.get("image_path", ""), file_id, files)
                img_eid = _nanoid()
                img = _base_element(
                    etype="image", eid=img_eid, x=x, y=y, w=FIGURE_W, h=FIGURE_H,
                )
                img["fileId"] = file_id
                img["status"] = "saved"
                img["scale"] = [1, 1]
                elements.append(img)
                node_elt_id[n.node_id] = img_eid

                # caption 文字 element（不绑定，独立放在图下方）
                if n.label:
                    elements.append(self._text_element(
                        x=x, y=y + FIGURE_H + 4, w=FIGURE_W, h=20,
                        text=n.label,
                    ))
                continue

            # rectangle 节点（claim / table / citation）
            style = NODE_STYLE[n.kind]
            rect_eid = _nanoid()
            text_eid = _nanoid()
            rect = _base_element(
                etype="rectangle", eid=rect_eid, x=x, y=y, w=NODE_W, h=NODE_H,
            )
            rect["strokeColor"] = style["strokeColor"]
            rect["backgroundColor"] = style["backgroundColor"]
            rect["fillStyle"] = "solid"
            rect["boundElements"] = [{"type": "text", "id": text_eid}]
            elements.append(rect)

            text = self._text_element(
                x=x + 8, y=y + 8, w=NODE_W - 16, h=NODE_H - 16,
                text=n.label,
            )
            text["containerId"] = rect_eid
            elements.append(text)
            node_elt_id[n.node_id] = rect_eid

        # --- 边 ---
        for e in graph.edges:
            src_eid = node_elt_id.get(e.from_id)
            dst_eid = node_elt_id.get(e.to_id)
            if not src_eid or not dst_eid:
                continue
            sx, sy = pos.get(e.from_id, (0, 0))
            tx, ty = pos.get(e.to_id, (0, 0))
            # 起点：源 rect 底部中点；终点：目标 rect 顶部中点
            x1, y1 = sx + NODE_W // 2, sy + NODE_H
            x2, y2 = tx + NODE_W // 2, ty
            arrow_eid = _nanoid()
            arrow = _base_element(
                etype="arrow", eid=arrow_eid, x=x1, y=y1, w=x2 - x1, h=y2 - y1,
            )
            style = EDGE_STYLE[e.kind]
            arrow["strokeColor"] = style["strokeColor"]
            arrow["strokeStyle"] = style["strokeStyle"]
            arrow["points"] = [[0, 0], [x2 - x1, y2 - y1]]
            arrow["lastCommittedPoint"] = None
            arrow["startBinding"] = {"elementId": src_eid, "focus": 0, "gap": 1}
            arrow["endBinding"] = {"elementId": dst_eid, "focus": 0, "gap": 1}
            arrow["startArrowhead"] = None
            arrow["endArrowhead"] = "arrow"
            if e.label:
                arrow["label"] = {"text": e.label}
            elements.append(arrow)

        doc = {
            "type": "excalidraw",
            "version": 2,
            "source": "explore-os",
            "elements": elements,
            "appState": {
                "gridSize": None,
                "viewBackgroundColor": "#ffffff",
            },
            "files": files,
        }

        out_path = out_dir / "graph.excalidraw"
        out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        return out_path

    # ---- helpers ----

    def _text_element(self, *, x: int, y: int, w: int, h: int, text: str) -> dict:
        eid = _nanoid()
        elt = _base_element(etype="text", eid=eid, x=x, y=y, w=w, h=h)
        elt["text"] = text
        elt["fontSize"] = 16
        elt["fontFamily"] = 1
        elt["textAlign"] = "left"
        elt["verticalAlign"] = "top"
        elt["baseline"] = 14
        elt["containerId"] = None
        elt["originalText"] = text
        elt["lineHeight"] = 1.25
        return elt

    def _maybe_embed_file(self, image_path: str, file_id: str, files: dict) -> None:
        """读 figure PNG → base64 dataURL → 写入 files 字段。
        路径不存在 / 读失败时静默跳过，依然产出可打开的 .excalidraw。"""
        if not image_path:
            return
        p = Path(image_path)
        if not p.is_file():
            return
        try:
            data = p.read_bytes()
        except OSError:
            return
        b64 = base64.b64encode(data).decode("ascii")
        files[file_id] = {
            "id": file_id,
            "mimeType": "image/png",
            "dataURL": f"data:image/png;base64,{b64}",
            "created": _now_ms(),
        }
