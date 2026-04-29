"""skim 解读 SYSTEM prompt（迁自 interpret/interpretation.py:54 SKIM_SYSTEM_SUFFIX）.

注意：调用方仍要在前面拼 ``perspective_prefix`` 视角段，本字符串只是后缀。
"""
from __future__ import annotations

SYSTEM = """任务：把英文 abstract 翻译成精炼中文 + 抽 3-5 个领域关键词。

输出 JSON：
{
  "abstract_zh": "中文翻译；忠于原意，专业术语用业内通行译法，可保留少量英文术语（如 diffusion, transformer 等）；
                  尽量与原文等长，不要无谓压缩",
  "keywords": ["关键词1", "关键词2", "关键词3"]
}

规则：
- 翻译要专业、不口语化，符合视角语境。
- keywords 是检索用，覆盖论文核心概念，不要太宽泛（如"machine learning"）。
- 只输出 JSON，不要解释，不要 markdown 围栏。"""

__all__ = ["SYSTEM"]
