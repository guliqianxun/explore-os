"""Thin re-export wrapper after ft-019 migration.

实际实现已搬到 ``apps.extract.figure_extractor``。本模块仅保持既有 import 不破，
ft-020 阶段会清理调用方后删除。
"""
from apps.extract.figure_extractor import *  # noqa: F401,F403
from apps.extract.figure_extractor import (  # noqa: F401
    CAPTION_MAX_DIST,
    CAPTION_RE,
    MAX_ASPECT_RATIO,
    MAX_FIGURES_PER_PAPER,
    MIN_PIX_AREA,
    Figure,
    extract_figures,
    figures_root,
    load_index,
    save_index,
)
