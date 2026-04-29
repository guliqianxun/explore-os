"""ft-033: brief 内容生成器 — 复用 ``interpret/interpretation.py`` 老 pipeline.

不重写老逻辑；只在 apps 层加缓存壳：
  - ``_build_item(paper)``：从 Paper + extract 数据组装 ad-hoc ``Item``
  - ``_resolve_perspective()``：从 active subscription yaml 读 PerspectiveSpec
  - ``generate_brief(paper, regenerate=False)``：调老 skim/deep_interpret
    并 ``update_or_create`` 落 PaperBrief

LLM 失控控制：默认手动触发（POST endpoint），ingest 链不自动跑。
"""
from __future__ import annotations

import logging
from pathlib import Path

from django.conf import settings

from sources.base import Item
from subscriptions.loader import PerspectiveSpec, load

from apps.papers.models import Paper, PaperBrief

log = logging.getLogger(__name__)


_TLDR_MAX_LEN = 80


def _subscriptions_yaml_path() -> Path:
    """与 ``apps/api/subscriptions_views`` 同套约定，便于 settings override."""
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


def _classify_bucket_from_path(path: str) -> str:
    """根据 docling Section.path 字符串匹配 ``BUCKET_KEYWORDS`` 的桶名.

    ``method`` / ``experiments`` / ``conclusion`` 等。匹配失败回 ``other``，
    会被 ``PaperChunks.by_bucket`` 在不被消费时自然丢弃。
    """
    from apps.extract.section_extractor import BUCKET_KEYWORDS

    p = (path or "").lower()
    for bucket, keywords in BUCKET_KEYWORDS:
        if any(kw in p for kw in keywords):
            return bucket
    return "other"


def _build_chunks(paper: Paper):
    """从 docling Section 表组装 ``PaperChunks`` 喂给 ``deep_interpret_rich``.

    每个非空 raw_text 行落一个 ``Section`` 入桶；空行跳过。
    """
    from apps.extract.models import Section as DBSection
    from apps.extract.section_extractor import (
        PaperChunks as PChunks,
        Section as PSection,
    )

    rows = DBSection.objects.filter(
        paper_arxiv_id=paper.arxiv_id or "",
    ).order_by("seq")
    sections = []
    for r in rows:
        if not (r.raw_text or "").strip():
            continue
        sections.append(PSection(
            bucket=_classify_bucket_from_path(r.path),
            title=r.path,
            text=r.raw_text,
        ))
    return PChunks(arxiv_id=paper.arxiv_id or paper.key, sections=sections)


def _build_captions(paper: Paper):
    """从 ``Figure`` 表组装 ``Caption`` 列表（仅前 8 张，控 token）.

    ingest 链没存正文引用上下文 — references 留空，``deep_interpret_rich``
    仍能用 caption 文本做框架图识别。
    """
    from apps.extract.caption_extractor import Caption as PCaption
    from apps.extract.models import Figure

    out = []
    for f in Figure.objects.filter(
        paper_arxiv_id=paper.arxiv_id or "",
    ).order_by("seq")[:8]:
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
    """Fallback：当 ``paper.abstract`` 空时，从 docling Section 实时拉.

    ingest 链落 paper 时不写 paper.abstract（仅 0006 backfill 跑过一次），
    所以新抽的 paper 会走这条 fallback。匹配 ``path icontains 'abstract'``
    最低 ``seq`` 的非空 raw_text；找不到再取 ``seq`` 最小的非空段。
    """
    from apps.extract.models import Section

    qs = Section.objects.filter(paper_arxiv_id=paper.arxiv_id or "")
    sec = (
        qs.filter(path__icontains="abstract")
        .exclude(raw_text="")
        .order_by("seq")
        .first()
        or qs.exclude(raw_text="").order_by("seq").first()
    )
    return (sec.raw_text or "").strip()[:4000] if sec else ""


def _build_item(paper: Paper) -> Item:
    """把 Paper + abstract 组装为 ``sources.base.Item`` 喂给老 pipeline.

    ``paper.abstract`` 空时走 ``_abstract_from_sections`` fallback，并把回填
    结果写回 ``paper.abstract`` 缓存（避免下次 generate_brief 重新查 Section）。
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


def _compose_tldr(text: str, max_len: int = _TLDR_MAX_LEN) -> str:
    """从 abstract_zh 头部按句末截 TL;DR.

    优先句末（``。``/``；``/``. ``/``;``），找不到再 ellipsis。
    """
    if not text:
        return ""
    text = text.strip()
    if len(text) <= max_len:
        return text
    head = text[:max_len]
    # 句末符号优先：避免极短头部（< max_len/3）后即截，让 TL;DR 看起来像短句
    min_idx = max_len // 3
    for sep in ("。", "；", ". ", ";"):
        idx = head.rfind(sep)
        if idx >= min_idx:
            return head[: idx + len(sep)].strip()
    return head + "…"


def generate_brief(paper: Paper, *, regenerate: bool = False) -> PaperBrief:
    """对 ``paper`` 跑 skim+deep interpret 并落库。

    ``regenerate=False`` 时若已有非空 brief（``abstract_zh`` 有内容）直接返回。
    LLM 调用同步阻塞——首次会等 5–15s，按钮上要给 loading 态。

    skim_interpret 失败（LLM error / abstract 空）→ 仍落一行空 brief，
    避免下次调用陷入死循环；前端按 ``has_brief`` 区分但 ``abstract_zh`` 也可能为空。
    """
    # 惰性 import，避免在测试 mock 时拉起 LLM client
    from interpret.deep_interpret import deep_interpret_rich
    from interpret.interpretation import skim_interpret

    existing = PaperBrief.objects.filter(paper=paper).first()
    if existing and not regenerate and existing.abstract_zh:
        return existing

    item = _build_item(paper)
    persp = _resolve_perspective()

    skim = skim_interpret(item, persp)
    # ft-033 增强：组装 method/experiments/conclusion chunks + figure captions，
    # 调 deep_interpret_rich 拿 method_summary / key_innovation / limitations / for_you
    chunks = _build_chunks(paper)
    captions = _build_captions(paper)
    deep = deep_interpret_rich(item, chunks, captions, [], persp)

    abstract_zh = (skim.abstract_zh if skim else "") or ""
    keywords = list(skim.keywords) if skim else []
    tldr_zh = _compose_tldr(abstract_zh) if abstract_zh else _compose_tldr(paper.abstract)

    persp_label = (persp.custom or persp.preset or "")[:128]

    brief, _created = PaperBrief.objects.update_or_create(
        paper=paper,
        defaults=dict(
            abstract_zh=abstract_zh,
            keywords=keywords,
            method_summary_zh=getattr(deep, "method_summary", "") or "",
            key_innovation=list(getattr(deep, "key_innovation", []) or []),
            limitations=list(getattr(deep, "limitations", []) or []),
            for_you=getattr(deep, "for_you", "") or "",
            tldr_zh=tldr_zh,
            perspective_used=persp_label,
            model_used="",  # SkimOut/DeepOut 暂未带 model 名；留空待 ft-014 升级
        ),
    )
    return brief
