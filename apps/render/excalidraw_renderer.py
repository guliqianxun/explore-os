"""ft-021: Excalidraw renderer —— Cluster Cards 模板（2026-04-26 重写）.

每个 claim 是自包含卡片：
- 顶部 header strip：claim_type 徽章 + confidence
- 中部 body：claim 文本（auto-wrap 到 card 宽度）
- evidence 区：figure 缩略图（左）+ caption（右），table/section 仅文字
- 底部 counter_signal 红条（如有）
- 底部 cite chips（如有）

不画跨卡片箭头 —— 视觉关系靠物理包含表达。
"""
from __future__ import annotations

import base64
import json
import secrets
import string
import time
from pathlib import Path

from apps.render.base import PaperGraphModel
from apps.render.layout import (
    CARD_H,
    CARD_W,
    CHIP_H,
    CHIP_W,
    layout_cluster,
)

# ---------------- 样式常量 ----------------

PAD = 16

# header strip
HEADER_H = 28
HEADER_BG = "#dee2e6"

# body 文本区域
BODY_Y = HEADER_H + 8
BODY_H = 130       # claim 文本最大高度

# evidence 区
EV_Y = BODY_Y + BODY_H + 8
EV_THUMB_W = 130
EV_THUMB_H = 100
EV_TEXT_PAD = 12

# counter_signal 红条
CS_BG = "#fff0f0"
CS_STROKE = "#e03131"

# claim_type → 徽章颜色
CLAIM_TYPE_COLOR = {
    "proposal":    "#1971c2",
    "result":      "#2f9e44",
    "ablation":    "#e8590c",
    "theoretical": "#7048e8",
}

CARD_STYLE = {
    "strokeColor": "#1971c2",
    "backgroundColor": "#f8f9fa",
}

CHIP_STYLE = {
    "strokeColor": "#868e96",
    "backgroundColor": "#f1f3f5",
}


# ---------------- 工具 ----------------

_NANOID_ALPHABET = string.ascii_letters + string.digits + "_-"


def _nanoid(n: int = 16) -> str:
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


def _text_element(*, x: int, y: int, w: int, h: int, text: str, font_size: int = 16,
                  text_align: str = "left", container_id: str | None = None) -> dict:
    eid = _nanoid()
    elt = _base_element(etype="text", eid=eid, x=x, y=y, w=w, h=h)
    elt["text"] = text
    elt["fontSize"] = font_size
    elt["fontFamily"] = 1
    elt["textAlign"] = text_align
    elt["verticalAlign"] = "top"
    elt["baseline"] = font_size - 2
    elt["containerId"] = container_id
    elt["originalText"] = text
    elt["lineHeight"] = 1.25
    return elt


# ---------------- Renderer ----------------

class ExcalidrawRenderer:
    """实现 ``apps.render.base.GraphRenderer`` Protocol。Cluster Cards 模板。"""

    def render(self, graph: PaperGraphModel, out_dir: Path) -> Path:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        pos = layout_cluster(graph)
        elements: list[dict] = []
        files: dict[str, dict] = {}
        # 同 image_path 去重 file_id
        path_to_file_id: dict[str, str] = {}

        for n in graph.nodes:
            x, y = pos.get(n.node_id, (0, 0))
            if n.kind == "claim":
                self._render_claim_card(n, x, y, elements, files, path_to_file_id)
            elif n.kind == "citation":
                self._render_citation_chip(n, x, y, elements)

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

    # ---- claim 卡片（核心） ----

    def _render_claim_card(self, n, x: int, y: int, elements: list[dict],
                            files: dict, path_to_file_id: dict[str, str]) -> None:
        # 1. 卡片外框
        card_id = _nanoid()
        card = _base_element(etype="rectangle", eid=card_id, x=x, y=y, w=CARD_W, h=CARD_H)
        card.update({
            "strokeColor": CARD_STYLE["strokeColor"],
            "backgroundColor": CARD_STYLE["backgroundColor"],
            "fillStyle": "solid",
            "roundness": {"type": 3},   # 圆角
        })
        elements.append(card)

        # 2. header strip（claim_type 徽章 + confidence 数字）
        header_bg = _base_element(etype="rectangle", eid=_nanoid(),
                                  x=x, y=y, w=CARD_W, h=HEADER_H)
        ctype = n.attrs.get("claim_type", "result")
        header_color = CLAIM_TYPE_COLOR.get(ctype, "#868e96")
        header_bg.update({
            "strokeColor": header_color,
            "backgroundColor": header_color,
            "fillStyle": "solid",
            "roundness": {"type": 3},
        })
        elements.append(header_bg)

        conf = n.attrs.get("confidence", 0.0)
        header_text = f"  [{ctype}]   conf {conf:.2f}"
        elements.append(_text_element(
            x=x + 8, y=y + 5, w=CARD_W - 16, h=HEADER_H - 8,
            text=header_text, font_size=14, container_id=None,
        ))

        # 3. body claim text（绑到 invisible inner rect 让 Excalidraw auto-wrap）
        body_inner_id = _nanoid()
        body_inner = _base_element(etype="rectangle", eid=body_inner_id,
                                   x=x + PAD, y=y + BODY_Y, w=CARD_W - 2 * PAD, h=BODY_H)
        body_inner.update({
            "strokeColor": "transparent",
            "backgroundColor": "transparent",
            "fillStyle": "solid",
            "strokeWidth": 0,
        })
        body_text = _text_element(
            x=x + PAD + 4, y=y + BODY_Y + 4,
            w=CARD_W - 2 * PAD - 8, h=BODY_H - 8,
            text=n.label, font_size=15,
            container_id=body_inner_id,
        )
        body_inner["boundElements"] = [{"type": "text", "id": body_text["id"]}]
        elements.append(body_inner)
        elements.append(body_text)

        # 4. evidence 区（figure 缩略 + 文字 / table 仅文字 / section 仅文字）
        evidences = n.attrs.get("evidences", []) or []
        section_ev = n.attrs.get("section_evidences", []) or []

        ev_y = y + EV_Y
        ev_x = x + PAD
        max_ev_y = y + CARD_H - 60  # 给 counter_signal 留 60px

        # 先画 figure（最显眼）
        for ev in evidences:
            if ev_y >= max_ev_y:
                break
            if ev.get("kind") == "figure":
                file_id = self._embed_image(ev.get("image_path", ""), files, path_to_file_id)
                if file_id:
                    img_eid = _nanoid()
                    img = _base_element(
                        etype="image", eid=img_eid,
                        x=ev_x, y=ev_y, w=EV_THUMB_W, h=EV_THUMB_H,
                    )
                    img["fileId"] = file_id
                    img["status"] = "saved"
                    img["scale"] = [1, 1]
                    elements.append(img)
                cap = self._truncate(ev.get("label", "") or "", 90)
                cap_text = f"Fig {ev.get('ref_id', '').split(':')[-1]}: {cap}"
                elements.append(_text_element(
                    x=ev_x + EV_THUMB_W + EV_TEXT_PAD,
                    y=ev_y + 4,
                    w=CARD_W - 2 * PAD - EV_THUMB_W - EV_TEXT_PAD,
                    h=EV_THUMB_H - 8,
                    text=cap_text, font_size=12,
                ))
                ev_y += EV_THUMB_H + 8
            elif ev.get("kind") == "table":
                cap = self._truncate(ev.get("label", "") or "", 100)
                line = f"📋 Tbl {ev.get('ref_id', '').split(':')[-1]}: {cap}"
                elements.append(_text_element(
                    x=ev_x, y=ev_y,
                    w=CARD_W - 2 * PAD, h=22,
                    text=line, font_size=12,
                ))
                ev_y += 26

        # 然后是 section evidence（小字）
        for ev in section_ev:
            if ev_y >= max_ev_y:
                break
            line = f"§ {ev.get('label', ev.get('ref_id', ''))}"
            elements.append(_text_element(
                x=ev_x, y=ev_y,
                w=CARD_W - 2 * PAD, h=20,
                text=line, font_size=11,
            ))
            ev_y += 22

        # equation evidence：优先嵌入 mathtext 渲染的 PNG；失败时退回 monospace 文本
        eq_ev = n.attrs.get("equation_evidences", []) or []
        EQ_AREA_W = CARD_W - 2 * PAD - 64       # 留 64 给行首「∑ Eq N」标签
        EQ_MAX_H = 56                            # 单条公式最大高度
        for ev in eq_ev[:3]:
            if ev_y >= max_ev_y:
                break
            ref_seq = ev.get("ref_id", "").split(":")[-1]
            img_path = ev.get("image_path", "") or ""
            iw = int(ev.get("image_w") or 0)
            ih = int(ev.get("image_h") or 0)
            file_id = self._embed_image(img_path, files, path_to_file_id) if (iw and ih) else ""
            if file_id and iw and ih:
                # 按比例缩放：以 EQ_MAX_H 为高度上限，按比例算宽；若宽度超限再按宽缩
                disp_h = EQ_MAX_H
                disp_w = int(iw * disp_h / ih)
                if disp_w > EQ_AREA_W:
                    disp_w = EQ_AREA_W
                    disp_h = max(20, int(ih * disp_w / iw))
                # 行首标签竖向居中
                elements.append(_text_element(
                    x=ev_x, y=ev_y + max(0, (disp_h - 16) // 2),
                    w=60, h=20,
                    text=f"∑ Eq {ref_seq}",
                    font_size=12,
                ))
                img_eid = _nanoid()
                img = _base_element(
                    etype="image", eid=img_eid,
                    x=ev_x + 64, y=ev_y, w=disp_w, h=disp_h,
                )
                img["fileId"] = file_id
                img["status"] = "saved"
                img["scale"] = [1, 1]
                elements.append(img)
                ev_y += disp_h + 6
            else:
                latex = self._truncate(ev.get("label", "") or "", 70)
                line = f"∑ Eq {ref_seq}: {latex}"
                elt = _text_element(
                    x=ev_x, y=ev_y,
                    w=CARD_W - 2 * PAD, h=20,
                    text=line, font_size=11,
                )
                elt["fontFamily"] = 3
                elements.append(elt)
                ev_y += 22

        # 5. counter_signal 红条（card 底部，按数量自适应高度）
        css = n.attrs.get("counter_signals", []) or []
        if css:
            n_lines = min(len(css), 3)
            cs_h = 24 + n_lines * 30   # 1 条 ≈ 54，3 条 ≈ 114
            cs_y = y + CARD_H - cs_h
            cs_bg = _base_element(etype="rectangle", eid=_nanoid(),
                                  x=x, y=cs_y, w=CARD_W, h=cs_h)
            cs_bg.update({
                "strokeColor": CS_STROKE,
                "backgroundColor": CS_BG,
                "fillStyle": "solid",
                "roundness": {"type": 3},
            })
            elements.append(cs_bg)
            cs_inner_id = _nanoid()
            cs_inner = _base_element(etype="rectangle", eid=cs_inner_id,
                                     x=x + PAD, y=cs_y + 4,
                                     w=CARD_W - 2 * PAD, h=cs_h - 8)
            cs_inner.update({
                "strokeColor": "transparent",
                "backgroundColor": "transparent",
                "fillStyle": "solid",
                "strokeWidth": 0,
            })
            cs_lines = []
            for cs in css[:3]:
                t = self._truncate(cs.get("text", "") or "", 80)
                cs_lines.append(f"⚠ [{cs.get('signal_type', '')}] {t}")
            cs_text = _text_element(
                x=x + PAD + 4, y=cs_y + 6,
                w=CARD_W - 2 * PAD - 8, h=cs_h - 12,
                text="\n".join(cs_lines), font_size=11,
                container_id=cs_inner_id,
            )
            cs_inner["boundElements"] = [{"type": "text", "id": cs_text["id"]}]
            elements.append(cs_inner)
            elements.append(cs_text)

    # ---- citation chip（底部行） ----

    def _render_citation_chip(self, n, x: int, y: int, elements: list[dict]) -> None:
        chip_id = _nanoid()
        chip = _base_element(etype="rectangle", eid=chip_id, x=x, y=y, w=CHIP_W, h=CHIP_H)
        chip.update({
            "strokeColor": CHIP_STYLE["strokeColor"],
            "backgroundColor": CHIP_STYLE["backgroundColor"],
            "fillStyle": "solid",
            "roundness": {"type": 3},
        })
        elements.append(chip)
        text = _text_element(
            x=x + 6, y=y + 8, w=CHIP_W - 12, h=CHIP_H - 16,
            text=n.label, font_size=11, container_id=chip_id,
        )
        chip["boundElements"] = [{"type": "text", "id": text["id"]}]
        elements.append(text)

    # ---- helpers ----

    def _embed_image(self, image_path: str, files: dict,
                     path_to_file_id: dict[str, str]) -> str:
        if not image_path:
            return ""
        if image_path in path_to_file_id:
            return path_to_file_id[image_path]
        p = Path(image_path)
        if not p.is_file():
            return ""
        try:
            data = p.read_bytes()
        except OSError:
            return ""
        file_id = _nanoid()
        b64 = base64.b64encode(data).decode("ascii")
        files[file_id] = {
            "id": file_id,
            "mimeType": "image/png",
            "dataURL": f"data:image/png;base64,{b64}",
            "created": _now_ms(),
        }
        path_to_file_id[image_path] = file_id
        return file_id

    def _truncate(self, s: str, n: int) -> str:
        s = (s or "").strip()
        if len(s) <= n:
            return s
        return s[: n - 1] + "…"
