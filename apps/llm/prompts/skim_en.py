"""skim 解读 SYSTEM prompt — English variant (ft-040).

When the paper's primary language is English, we summarize **in English** rather
than translating to Chinese. JSON keys stay identical (``abstract_zh``,
``keywords``) so downstream consumers don't branch on language; the storage
layer records ``PaperBrief.lang`` separately.
"""
from __future__ import annotations

SYSTEM = """Task: produce a refined English summary of the paper's abstract +
3-5 domain keywords.

Output JSON:
{
  "abstract_zh": "tightened English summary of the abstract — keep it factual,
                  preserve technical terms verbatim, ~same length as the input
                  (no aggressive compression). Despite the field name, write
                  English here when the source paper is English.",
  "keywords": ["keyword1", "keyword2", "keyword3"]
}

Rules:
- Keep professional academic tone; do not paraphrase into casual English.
- keywords are for retrieval — capture the paper's core concepts; avoid
  generic terms like "machine learning".
- JSON only. No prose, no markdown fences."""

__all__ = ["SYSTEM"]
