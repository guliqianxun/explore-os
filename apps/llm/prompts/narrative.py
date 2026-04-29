"""Narrative 跨篇合成 SYSTEM prompt（迁自 interpret/narrative.py:20 NARRATIVE_SYSTEM_SUFFIX）.

调用方仍要在前面拼 ``perspective_prefix`` 视角段，本字符串只是后缀。
"""
from __future__ import annotations

SYSTEM = """任务：你有一组今日入选的论文要点（含索引号、标题、一句话要点、综合分）。
请产出中文 JSON：
{
  "hero_sentence": "一句统领全天的话，点出主题聚类或最大新闻",
  "bullets": [
    "主题1（#索引 #索引）：1 句话概括这组论文在做的事",
    "主题2（#索引）：...",
    "主题3（#索引）：..."
  ],
  "note_for_you": "基于视角给读者的一句个人化建议，如推荐先读哪几篇"
}

规则：
- hero_sentence 不要用"今日论文""今天我们"模板词。
- bullets 数量 2-4 条，按重要性降序。
- 引用论文用 #索引 形式（索引=输入里提供的 id）。
- 只输出 JSON，不要解释。"""

__all__ = ["SYSTEM"]
