"""ft-013: 精读深度解读（纯文本 LLM）.

输入：method/exp/conclusion 文本 + caption 列表 + 引用上下文 + 近期 memory。
输出：method_summary / key_innovation / limitations / for_you（带 [Fig. N] 锚点）.

不再调多模态。架构图由 figure_picker 选好后由调用方渲染 PNG（pdf_renderer），
DeepOut.figure_path 仍承载图路径，但只用于邮件展示，不送 LLM。
"""
from __future__ import annotations

import logging

# ft-034 P0-2: SYSTEM + model 集中在 apps.llm
from apps.llm.models import get_profile
from apps.llm.prompts.deep import SYSTEM as DEEP_SYSTEM_SUFFIX
# ft-034 P1-3: thin re-export wrapper 清理 → 直 import apps.extract.*
from apps.extract.caption_extractor import Caption
from apps.extract.section_extractor import PaperChunks
from interpret.interpretation import DEEP_PLACEHOLDER, DeepOut, perspective_prefix
from interpret.llm import LLMError, chat, extract_json
from sources.base import Item
from subscriptions.loader import PerspectiveSpec
from subscriptions.memory import PaperRecord

log = logging.getLogger(__name__)


def deep_interpret_rich(
    item: Item,
    chunks: PaperChunks | None,
    captions: list[Caption] | None,
    memory_papers: list[PaperRecord] | None,
    perspective: PerspectiveSpec,
) -> DeepOut:
    out = DeepOut(abstract=item.abstract or "", placeholder=DEEP_PLACEHOLDER)
    body = _compose_body(chunks) if chunks else ""
    cap_block = _compose_captions(captions or [])
    mem_block = _compose_memory(memory_papers or [])

    if not body and not cap_block:
        log.info("deep_interpret_rich: no body & no captions for %s, placeholder",
                 item.dedup_key)
        return out

    system = perspective_prefix(perspective) + DEEP_SYSTEM_SUFFIX
    user = (
        f"title: {item.title}\n\n"
        f"abstract: {item.abstract}\n"
    )
    if body:
        user += f"\n=== 方法 / 实验 / 结论文本 ===\n{body}\n"
    if cap_block:
        user += f"\n=== 论文配图 captions + 引用上下文 ===\n{cap_block}\n"
    if mem_block:
        user += f"\n=== 近期推送过的相关论文（供联想/对比） ===\n{mem_block}\n"
    user += "\n请产出 JSON 四段。"

    profile = get_profile("deep")
    try:
        res = chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            model=profile.model,
            temperature=0.3,
            max_tokens=900,
            timeout=60.0,
        )
        parsed = extract_json(res.content)
    except (LLMError, Exception) as exc:  # noqa: BLE001
        log.warning("deep_interpret_rich failed for %s: %r", item.dedup_key, exc)
        return out

    out.method_summary = str(parsed.get("method_summary") or "").strip()
    out.key_innovation = [str(s).strip() for s in parsed.get("key_innovation") or []][:4]
    out.limitations = [str(s).strip() for s in parsed.get("limitations") or []][:3]
    out.for_you = str(parsed.get("for_you") or "").strip()
    return out


# ---------------- helpers ----------------

def _compose_body(chunks: PaperChunks) -> str:
    parts = []
    for b in ("method", "experiments", "conclusion"):
        txt = chunks.by_bucket(b)
        if txt:
            parts.append(f"## {b}\n{txt}")
    return "\n\n".join(parts)


def _compose_captions(captions: list[Caption]) -> str:
    if not captions:
        return ""
    lines = []
    for c in captions[:8]:   # 上限避免 token 过多
        lines.append(f"[{c.label}] {c.text}")
        for ref in c.references[:2]:
            lines.append(f"    引用上下文：{ref}")
    return "\n".join(lines)


def _compose_memory(papers: list[PaperRecord]) -> str:
    if not papers:
        return ""
    # 只取最近 8 条避免 token 膨胀
    recent = papers[-8:]
    lines = []
    for p in recent:
        kw = "/".join(p.keywords[:3]) if p.keywords else ""
        zh = (p.abstract_zh or p.one_liner)[:120]
        lines.append(f"- {p.target_date}  {p.title}  ({kw})  ::  {zh}")
    return "\n".join(lines)
