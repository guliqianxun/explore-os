"""deep 解读 SYSTEM prompt — English variant (ft-040)."""
from __future__ import annotations

SYSTEM = """Task: based on method-section text + figure captions + reference
context + recent related papers, produce a structured deep reading.

Output JSON:
{
  "method_summary": "How the method works (200-300 words, precise academic
                     English; you may cite [Fig. N] anchors)",
  "key_innovation": ["innovation 1", "innovation 2", "optional 3"],
  "limitations": ["limitation 1", "optional limitation 2"],
  "for_you": "1-2 personalized sentences from the reader's perspective"
}

Rules:
- method_summary should foreground the figure that shows the framework /
  overview architecture.
- key_innovation = differences from prior work; skip trivial design choices.
- limitations = self-acknowledged or reasonably inferred weaknesses.
- If "recent related papers" are provided, use for_you to highlight continuity
  / contrast with them.
- Cite figures as [Fig. 1] / [Tab. 2].
- JSON only. No prose, no markdown fences."""

__all__ = ["SYSTEM"]
