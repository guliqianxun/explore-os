"""Thin re-export wrapper after ft-019 migration.

实际实现已搬到 ``apps.extract.section_extractor``。本模块仅保持既有 import 不破，
ft-020 阶段会清理调用方后删除。
"""
from apps.extract.section_extractor import *  # noqa: F401,F403
from apps.extract.section_extractor import (  # noqa: F401
    BUCKET_CHAR_CAP,
    BUCKET_KEYWORDS,
    HEADING_RE,
    PaperChunks,
    Section,
    _classify_bucket,
    _parse_to_markdown,
    _split_by_heading,
    chunk_pdf,
)
