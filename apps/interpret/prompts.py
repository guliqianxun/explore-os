"""ft-020: L1 / L2 prompt 模板."""
from __future__ import annotations

L1_SYSTEM = """你是论文逻辑还原专家。从论文中抽取作者明确做出的可验证 claim。
每条 claim 必须 cite 至少一个 material id（[§:N] / [fig:N] / [tbl:N] / [eq:N]）。
无 cite 的 claim 必须丢弃。
返回严格 JSON：
{"claims": [
  {"text": "中文化简短陈述（1-2 句）",
   "text_en": "原文 span（可空）",
   "claim_type": "proposal|result|ablation|theoretical",
   "source_section_path": "...",
   "confidence": 0.0-1.0,
   "evidences": [{"material_id": "[fig:1]", "relation": "supports|illustrates|quantifies"}]}
]}"""

L1_USER_TEMPLATE = """=== Material Catalog ===
{catalog}

=== Paper Markdown ===
{markdown}

=== Task ===
抽取 5-15 条 claim。每条简短中文（1-2 句），cite ≥1 material。返回严格 JSON。"""


L2_SYSTEM = """你是论文反向信号复盘专家。**只读论文内**已写出的反向证据，
严禁引用论文外的 prior work 或自己的常识。每条 signal 必须：
1. 挂在已抽出的某条 claim 上（用 claim_idx，0-based 索引到下方 claims 列表）
2. 引用一个 material id（[§:N] / [fig:N] / [tbl:N] / [eq:N]，必填）
信号类型限定 4 类：
- limitation：limitation 段明确写出的限制
- ablation_drop：ablation 表中性能下降的 component
- failure_case：discussion / failure case 的负面结果
- prior_work_better：related work 段作者承认的 prior work 优势

返回严格 JSON：
{"counter_signals": [
  {"text": "中文反向信号陈述",
   "signal_type": "limitation|ablation_drop|failure_case|prior_work_better",
   "evidence_material_id": "[§:5]",
   "claim_idx": 0}
]}
找不到反向信号就返回 {"counter_signals": []}，不要编造。"""

L2_USER_TEMPLATE = """=== Material Catalog ===
{catalog}

=== Paper Markdown ===
{markdown}

=== Existing Claims (按 idx 0-based) ===
{claims_brief}

=== Task ===
扫论文内反向证据，挂回上面 claim。每条 signal 必须 cite material。返回严格 JSON。"""


def render_claims_brief(claims: list[dict]) -> str:
    """把 claims 列表渲染为给 L2 看的简表（idx + text + cite 简写）。"""
    lines = []
    for i, c in enumerate(claims):
        ev = ", ".join(e.get("material_id", "") for e in c.get("evidences", []))
        lines.append(f"[{i}] {c.get('text', '')}  cite={ev}")
    return "\n".join(lines) if lines else "(no claims)"
