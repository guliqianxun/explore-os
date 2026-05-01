"""ft-033 + ft-034 P0-3: brief 持久化层（thin orchestrator）.

本模块在 ft-034 P0-3 后退化为 thin wrapper：
  - 取 Paper + 跳过既存判断
  - 调 ``apps.llm.services.brief_generate.generate_brief_data`` 拿 LLM 结果
  - ``update_or_create`` 落 PaperBrief（ORM 副作用留在 papers 层）

LLM 装配 / 反向 import 全部下沉到 ``apps.llm.services.brief_generate``。
本文件**严禁** ``from interpret.*``（review-A H8）。

LLM 失控控制：默认手动触发（POST endpoint），ingest 链不自动跑。
"""
from __future__ import annotations

import logging

from apps.llm.services.brief_generate import (
    _compose_tldr,
    _resolve_perspective,
    generate_brief_data,
)
from apps.papers.models import Paper, PaperBrief

# 向后兼容 re-export（apps/api/tests_brief.py 仍 import 这两个 helper）。
# 函数实现已搬到 apps.llm.services.brief_generate；这里保留别名仅供老测试。
__all__ = ["_compose_tldr", "_resolve_perspective", "generate_brief"]

log = logging.getLogger(__name__)


def generate_brief(paper: Paper, *, regenerate: bool = False) -> PaperBrief:
    """对 ``paper`` 跑 skim+deep interpret 并落库。

    ``regenerate=False`` 时若已有非空 brief（``abstract_zh`` 有内容）直接返回。
    LLM 调用同步阻塞——首次会等 5–15s，按钮上要给 loading 态。

    skim 失败 → 仍落一行空 brief，避免下次调用陷入死循环；前端按 ``has_brief``
    区分但 ``abstract_zh`` 也可能为空。
    """
    existing = PaperBrief.objects.filter(paper=paper).first()
    if existing and not regenerate and existing.abstract_zh:
        return existing

    data = generate_brief_data(paper)

    brief, _created = PaperBrief.objects.update_or_create(
        paper=paper,
        defaults=dict(
            abstract_zh=data["abstract_zh"],
            keywords=data["keywords"],
            method_summary_zh=data["method_summary_zh"],
            key_innovation=data["key_innovation"],
            limitations=data["limitations"],
            for_you=data["for_you"],
            tldr_zh=data["tldr_zh"],
            perspective_used=data["perspective_used"],
            model_used=data["model_used"],
            lang=data.get("lang", ""),
        ),
    )
    return brief
