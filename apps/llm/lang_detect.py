"""ft-040: 论文语言检测（用于选 zh/en prompt 变体）.

启发式：抽样 title + abstract 看是否含 CJK 统一汉字 (U+4E00–U+9FFF)。
有 → ``zh``；否则 → ``en``。

不做 ML 检测：英文论文偶有作者中文名（拼音），不会触发；中文论文 abstract
通常含大量汉字，触发稳定。
"""
from __future__ import annotations

import re

_CJK_RE = re.compile(r"[一-鿿]")


def detect_paper_lang(title: str = "", abstract: str = "") -> str:
    """返回 ``'zh'`` 或 ``'en'``。空输入默认 ``'en'``（最大众场景 = arxiv 英文）."""
    sample = f"{title or ''} {abstract or ''}"
    return "zh" if _CJK_RE.search(sample) else "en"


__all__ = ["detect_paper_lang"]
