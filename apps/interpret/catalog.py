"""ft-020: 从 ``extract_*`` 表组装 LLM cite 目标 catalog.

输出 (catalog_text, allowed_material_ids):
  - catalog_text: 给 LLM 看的索引清单，简写形式 ``[§:N] / [fig:N] / [tbl:N] / [eq:N]``
  - allowed_material_ids: full form 集合（``<arxiv_id>:<type>:<seq>``），用于 cite 校验

LLM 返回简写后由 ``resolve_short_to_full`` 翻回 full form 再校验。
"""
from __future__ import annotations

import re

from apps.extract.models import Equation, Figure, Section, Table

# Short form 简写 ↔ extract type 名映射
_SHORT_TO_TYPE = {
    "§": "section",
    "fig": "figure",
    "tbl": "table",
    "eq": "equation",
}
_TYPE_TO_SHORT = {v: k for k, v in _SHORT_TO_TYPE.items()}

# 解析 [fig:1] / [§:3] / [tbl:5] / [eq:2]
_SHORT_RE = re.compile(r"^\s*\[?\s*(§|fig|tbl|eq)\s*:\s*(\d+)\s*\]?\s*$")
# material_id 解析：<arxiv_id>:<type>:<seq>
_MID_RE = re.compile(r"^(?P<arxiv>.+?):(?P<type>section|figure|table|equation):(?P<seq>\d+)$")


def _seq(material_id: str) -> int:
    """从 material_id 末段解析 seq。"""
    m = _MID_RE.match(material_id)
    if not m:
        return 0
    return int(m.group("seq"))


def build_catalog(arxiv_id: str) -> tuple[str, set[str]]:
    """读 extract_* 表，组装 LLM 可用 catalog + allowed full material_id 集合。

    只用 level=1 的 canonical sections（清洁层已 demote noise 至 level=2）。
    Equation 截到前 20 条，避免炸 token。
    """
    lines: list[str] = []
    allowed: set[str] = set()

    for s in Section.objects.filter(paper_arxiv_id=arxiv_id, level=1).order_by("seq"):
        lines.append(f"[§:{_seq(s.material_id)}] {s.path}")
        allowed.add(s.material_id)

    for f in Figure.objects.filter(paper_arxiv_id=arxiv_id).order_by("seq"):
        cap = (f.caption or "")[:200]
        lines.append(f"[fig:{_seq(f.material_id)}] p{f.page} {cap}")
        allowed.add(f.material_id)

    for t in Table.objects.filter(paper_arxiv_id=arxiv_id).order_by("seq"):
        cap = (t.caption or "")[:200]
        lines.append(f"[tbl:{_seq(t.material_id)}] p{t.page} {cap}")
        allowed.add(t.material_id)

    for e in Equation.objects.filter(paper_arxiv_id=arxiv_id).order_by("seq")[:20]:
        latex = (e.latex_or_text or "")[:120]
        lines.append(f"[eq:{_seq(e.material_id)}] {latex}")
        allowed.add(e.material_id)

    return "\n".join(lines), allowed


def resolve_short_to_full(short: str, arxiv_id: str) -> str | None:
    """``[fig:1]`` / ``fig:1`` → ``<arxiv_id>:figure:1``.

    无法解析返回 None（调用方应丢弃）。已是 full form 的也直接尝试匹配返回。
    """
    if not short:
        return None
    s = short.strip()
    # 已是 full form？
    m_full = _MID_RE.match(s)
    if m_full:
        return s
    m = _SHORT_RE.match(s)
    if not m:
        return None
    short_kind, seq = m.group(1), m.group(2)
    type_name = _SHORT_TO_TYPE.get(short_kind)
    if type_name is None:
        return None
    return f"{arxiv_id}:{type_name}:{int(seq)}"
