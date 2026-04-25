"""Thin re-export wrapper after ft-019 migration.

实际实现已搬到 ``apps.extract.caption_extractor``。本模块仅保持既有 import 不破，
ft-020 阶段会清理调用方后删除。
"""
from apps.extract.caption_extractor import *  # noqa: F401,F403
from apps.extract.caption_extractor import (  # noqa: F401
    CAPTION_PREFIX_RE,
    DEFAULT_FIG_BAND_ABOVE,
    REFERENCE_RE,
    Caption,
    _attach_references,
    extract_captions,
)
