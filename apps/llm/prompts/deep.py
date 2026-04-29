"""deep 解读 SYSTEM prompt（迁自 interpret/deep_interpret.py:26 DEEP_SYSTEM_SUFFIX）.

调用方仍要在前面拼 ``perspective_prefix`` 视角段，本字符串只是后缀。
"""
from __future__ import annotations

SYSTEM = """任务：基于方法章节文本 + 配图 caption + 正文引用上下文 + 近期推送过的相关论文，
产出论文结构化深度解读。输出 JSON：
{
  "method_summary": "方法怎么做的（200-300字，精炼学术语言；可引用 [Fig. N] 锚点）",
  "key_innovation": ["关键创新点 1", "关键创新点 2", "可选 3"],
  "limitations": ["局限 1", "可选局限 2"],
  "for_you": "结合视角的 1-2 句个人化解读"
}

规则：
- method_summary 优先解释 caption 含 framework/overview 那张图描述的结构。
- key_innovation 是"相对已有工作的差异点"，避免列 trivial 设计。
- limitations 从论文自承或可推断的弱点出发。
- 若提供"近期推送过的相关论文"，可在 for_you 里点出与之的延续/差异关系（让读者建立 trend 感）。
- 用 [Fig. 1] / [Tab. 2] 形式引用配图。
- 只输出 JSON，不要解释，不要 markdown 围栏。"""

__all__ = ["SYSTEM"]
