"""LLM 预算 / 截断阈值中心（ft-034 P0-2 / review-A H13）.

只声明常量，不强制替换调用点（替换属 F2 / 后续 sprint 工作）。

每个常量上方注明：源 review、量纲含义、当前调用方，便于后续重构追溯。
"""
from __future__ import annotations


# review-A H13: 长论文 markdown 截断字符上限。
# 当前调用方：apps/interpret/interpreter.py:34 (MARKDOWN_CHAR_BUDGET)
# 量纲：UTF-8 字符（len(markdown_str)），不是 token。
MARKDOWN_CHAR_BUDGET: int = 30_000

# review-A H13: TL;DR summary 中文字符上限（单行卡片显示用）。
# 当前调用方：interpret/tldr.py SYSTEM 中"不超过 60 字"约束 + 邮件渲染裁剪。
# 80 留 25% 余量给 LLM 偶发超长。
TLDR_MAX_LEN: int = 80

# review-A H13: deep_interpret 喂给 LLM 的 caption 数量上限。
# 当前调用方：interpret/deep_interpret.py:112 ``captions[:8]``。
# 论文常含 10+ 张图，超过 8 张 token 膨胀且边际信息递减。
DEEP_CAPTION_LIMIT: int = 8

# review-A H13: figure_picker LLM 兜底时喂的候选 figure 上限。
# 当前调用方：interpret/figure_picker.py:140 ``figures[:15]``。
# 单次 LLM call 80 max_tokens 选号，过多候选会 token 超限。
FIGURE_PICKER_TOP_K: int = 15


__all__ = [
    "MARKDOWN_CHAR_BUDGET",
    "TLDR_MAX_LEN",
    "DEEP_CAPTION_LIMIT",
    "FIGURE_PICKER_TOP_K",
]
