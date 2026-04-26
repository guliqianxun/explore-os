"""ft-021: Cluster Cards 网格布局（2026-04-26 重写）.

claim 卡片是自包含单元，按 confidence 降序填入网格；citation 作为底部 chip 行。

* claim 卡片：480×400，左右 padding 60
* 每行 2 张卡片
* 网格起点 x=80 / y=80
* 行间距 480 (= 400 + 80 gap)
* citation chip：140×40，底部按 chip_per_row=8 排
"""
from __future__ import annotations

from apps.render.base import PaperGraphModel

# claim 卡片
CARD_W = 480
CARD_H = 400
CARD_GAP_X = 60
CARD_GAP_Y = 80
CARDS_PER_ROW = 2
GRID_X0 = 80
GRID_Y0 = 80

# citation chip
CHIP_W = 140
CHIP_H = 40
CHIP_GAP_X = 16
CHIP_GAP_Y = 12
CHIPS_PER_ROW = 8
CHIP_ROW_TITLE_GAP = 60   # citation chip 行与最后一排 claim 卡片的距离


def layout_cluster(graph: PaperGraphModel) -> dict[str, tuple[int, int]]:
    """返回 ``{node_id: (x, y)}``。claim 卡片按 confidence 降序网格摆放，
    citation chip 紧跟其后底部 chip 行。"""
    pos: dict[str, tuple[int, int]] = {}

    claims = [n for n in graph.nodes if n.kind == "claim"]
    claims.sort(key=lambda n: (-(n.attrs.get("confidence") or 0.0), n.node_id))
    for i, n in enumerate(claims):
        col = i % CARDS_PER_ROW
        row = i // CARDS_PER_ROW
        x = GRID_X0 + col * (CARD_W + CARD_GAP_X)
        y = GRID_Y0 + row * (CARD_H + CARD_GAP_Y)
        pos[n.node_id] = (x, y)

    # citation chip 行起点 y = 最后一行 claim 卡片底部 + gap
    if claims:
        n_rows = (len(claims) + CARDS_PER_ROW - 1) // CARDS_PER_ROW
        chip_y0 = GRID_Y0 + n_rows * (CARD_H + CARD_GAP_Y) - CARD_GAP_Y + CHIP_ROW_TITLE_GAP
    else:
        chip_y0 = GRID_Y0

    cits = [n for n in graph.nodes if n.kind == "citation"]
    cits.sort(key=lambda n: n.node_id)
    for i, n in enumerate(cits):
        col = i % CHIPS_PER_ROW
        row = i // CHIPS_PER_ROW
        x = GRID_X0 + col * (CHIP_W + CHIP_GAP_X)
        y = chip_y0 + row * (CHIP_H + CHIP_GAP_Y)
        pos[n.node_id] = (x, y)

    return pos


# 兼容旧导出（其它模块和测试用 `_layout`）
_layout = layout_cluster
