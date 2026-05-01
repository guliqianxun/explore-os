"""apps.llm.services.brief_generate — Brief 生成 service（ft-034 P0-3）.

把原 ``apps/papers/brief_generator.py`` 函数体内 5 处惰性 ``import apps.extract.*``
+ ``from interpret.*`` 反向 import 全部搬到这里。``apps.papers.brief_generator``
退化为 thin orchestrator：取 paper → 调本 service → 持久化 PaperBrief。

输入：``paper_id`` 或 ``Paper`` instance。
输出：``BriefData`` dict —— 含 6 个 ft-033 brief 字段（abstract_zh / keywords /
tldr_zh / for_you / method_summary_zh / key_innovation / limitations），由调用
方写入 PaperBrief。

设计要点：
- **不持久化** —— 让 ORM 副作用留在 ``apps.papers`` 层，service 是纯 LLM + 装配。
- **不再惰性 import**（review-A H8）—— ``apps.extract.*`` / 服务模块都正向 import。
- TLDR_MAX_LEN 走 ``apps.llm.budgets.TLDR_MAX_LEN``。
- caption 上限走 ``apps.llm.budgets.DEEP_CAPTION_LIMIT``（与 deep service 内部一致）。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TypedDict

from django.conf import settings

from apps.extract.caption_extractor import Caption as PCaption
from apps.extract.models import Figure, Section as DBSection
from apps.extract.section_extractor import (
    BUCKET_KEYWORDS,
    PaperChunks as PChunks,
    Section as PSection,
)
from apps.llm.budgets import DEEP_CAPTION_LIMIT, TLDR_MAX_LEN
from apps.llm.services.deep_interpret import deep_interpret_rich
from apps.llm.services.skim_interpret import skim_interpret
from apps.papers.models import Paper
from sources.base import Item
from subscriptions.loader import PerspectiveSpec, load

log = logging.getLogger(__name__)


# ---------------- BriefData TypedDict ----------------


class BriefData(TypedDict):
    """6 个 ft-033 brief 字段 + 元信息。caller 据此写 PaperBrief。"""

    abstract_zh: str
    keywords: list[str]
    tldr_zh: str
    method_summary_zh: str
    key_innovation: list[str]
    limitations: list[str]
    for_you: str
    perspective_used: str
    model_used: str
    # ft-040: paper 主语言（'zh' | 'en'）。决定 _zh 字段内容是中文还是英文。
    lang: str


# ---------------- subscription / perspective ----------------


def _subscriptions_yaml_path() -> Path:
    p = getattr(settings, "SUBSCRIPTIONS_YAML", None)
    return Path(p) if p else Path(settings.BASE_DIR) / "subscriptions.yaml"


def _resolve_perspective() -> PerspectiveSpec:
    """从 active subscription 读 perspective；多订阅取第一个；fallback researcher."""
    try:
        path = _subscriptions_yaml_path()
        if not path.exists():
            return PerspectiveSpec(preset="researcher")
        for s in load(path):
            if s.enabled and (s.perspective.preset or s.perspective.custom):
                return s.perspective
    except Exception as exc:  # noqa: BLE001
        log.warning("perspective 解析失败 fallback researcher: %r", exc)
    return PerspectiveSpec(preset="researcher")


# ---------------- 装配 helpers（搬自 apps/papers/brief_generator.py） ----------------


def _classify_bucket_from_path(path: str) -> str:
    """根据 docling Section.path 字符串匹配 ``BUCKET_KEYWORDS`` 的桶名."""
    p = (path or "").lower()
    for bucket, keywords in BUCKET_KEYWORDS:
        if any(kw in p for kw in keywords):
            return bucket
    return "other"


def _build_chunks(paper: Paper) -> PChunks:
    """从 docling Section 表组装 ``PaperChunks`` 喂给 ``deep_interpret_rich``."""
    rows = DBSection.objects.filter(
        paper_arxiv_id=paper.arxiv_id or "",
    ).order_by("seq")
    sections: list[PSection] = []
    for r in rows:
        if not (r.raw_text or "").strip():
            continue
        sections.append(PSection(
            bucket=_classify_bucket_from_path(r.path),
            title=r.path,
            text=r.raw_text,
        ))
    return PChunks(arxiv_id=paper.arxiv_id or paper.key, sections=sections)


def _build_captions(paper: Paper) -> list[PCaption]:
    """从 ``Figure`` 表组装 ``Caption`` 列表（仅前 ``DEEP_CAPTION_LIMIT`` 张，控 token）."""
    out: list[PCaption] = []
    for f in Figure.objects.filter(
        paper_arxiv_id=paper.arxiv_id or "",
    ).order_by("seq")[:DEEP_CAPTION_LIMIT]:
        cap = (f.caption or "").strip()
        if not cap:
            continue
        out.append(PCaption(
            arxiv_id=f.paper_arxiv_id,
            kind="figure",
            number=f.seq,
            text=cap,
            page=f.page or 0,
            bbox_caption=(0.0, 0.0, 0.0, 0.0),
            bbox_image=(0.0, 0.0, 0.0, 0.0),
            references=[],
        ))
    return out


def _abstract_from_sections(paper: Paper) -> str:
    """Fallback：当 ``paper.abstract`` 空时，从 docling Section 实时拉."""
    qs = DBSection.objects.filter(paper_arxiv_id=paper.arxiv_id or "")
    sec = (
        qs.filter(path__icontains="abstract")
        .exclude(raw_text="")
        .order_by("seq")
        .first()
        or qs.exclude(raw_text="").order_by("seq").first()
    )
    return (sec.raw_text or "").strip()[:4000] if sec else ""


def _build_item(paper: Paper) -> Item:
    """把 Paper + abstract 组装为 ``sources.base.Item`` 喂给 skim/deep service。

    paper.abstract 空时走 fallback 并把回填结果写回 paper.abstract（缓存）。
    """
    abstract = paper.abstract or ""
    if not abstract.strip():
        abstract = _abstract_from_sections(paper)
        if abstract:
            paper.abstract = abstract
            paper.save(update_fields=["abstract"])
    return Item(
        external_id=paper.arxiv_id or paper.key,
        title=paper.title or "",
        abstract=abstract,
        url=f"https://arxiv.org/abs/{paper.arxiv_id}" if paper.arxiv_id else "",
        source_key="reuse",
        group="papers",
    )


def _compose_tldr(text: str, max_len: int = TLDR_MAX_LEN) -> str:
    """从 abstract_zh 头部按句末截 TL;DR.

    优先句末（``。``/``；``/``. ``/``;``），找不到再 ellipsis。
    """
    if not text:
        return ""
    text = text.strip()
    if len(text) <= max_len:
        return text
    head = text[:max_len]
    min_idx = max_len // 3
    for sep in ("。", "；", ". ", ";"):
        idx = head.rfind(sep)
        if idx >= min_idx:
            return head[: idx + len(sep)].strip()
    return head + "…"


# ---------------- public API ----------------


def generate_brief_data(paper: Paper) -> BriefData:
    """对 ``paper`` 跑 skim+deep interpret，装配并返回 ``BriefData`` dict.

    **不持久化** —— caller (``apps.papers.brief_generator.generate_brief``) 写
    PaperBrief。

    skim_interpret 失败（LLM error / abstract 空）→ 仍返回带空字段的 BriefData，
    避免 caller 陷入死循环；caller 据 ``abstract_zh`` 是否空判断有效性。
    """
    item = _build_item(paper)
    persp = _resolve_perspective()

    skim = skim_interpret(item, persp)
    chunks = _build_chunks(paper)
    captions = _build_captions(paper)
    deep = deep_interpret_rich(item, chunks, captions, [], persp)

    abstract_zh = (skim.abstract_zh if skim else "") or ""
    keywords = list(skim.keywords) if skim else []
    tldr_zh = _compose_tldr(abstract_zh) if abstract_zh else _compose_tldr(paper.abstract)

    persp_label = (persp.custom or persp.preset or "")[:128]

    # ft-040: paper 语言；skim/deep 都已带 lang 字段（默认从 paper 检测）。
    # 用 deep.lang 兜底（skim 失败仍取得 deep.lang）；都没有 fallback 'zh'。
    lang = getattr(skim, "lang", None) or getattr(deep, "lang", None) or "zh"

    return BriefData(
        abstract_zh=abstract_zh,
        keywords=keywords,
        tldr_zh=tldr_zh,
        method_summary_zh=getattr(deep, "method_summary", "") or "",
        key_innovation=list(getattr(deep, "key_innovation", []) or []),
        limitations=list(getattr(deep, "limitations", []) or []),
        for_you=getattr(deep, "for_you", "") or "",
        perspective_used=persp_label,
        model_used="",  # SkimOut/DeepOut 暂未带 model 名；留空待 ft-014 升级
        lang=lang,
    )


__all__ = ["BriefData", "generate_brief_data"]
