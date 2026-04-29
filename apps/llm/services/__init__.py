"""apps.llm.services — LLM 能力 public 接口（ft-034 P0-1 / P0-3）.

F2 落地：
- skim_interpret.py（搬自 ``interpret/interpretation.py:skim_interpret``）
- deep_interpret.py（搬自 ``interpret/deep_interpret.py:deep_interpret_rich``）
- brief_generate.py（搬自 ``apps/papers/brief_generator.py`` 装配逻辑）

剩余 stub（后续 sprint）：
- extract_claims.py
- rewriter.py
"""
from apps.llm.services import brief_generate, deep_interpret, skim_interpret

__all__ = ["skim_interpret", "deep_interpret", "brief_generate"]
