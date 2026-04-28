"""ft-028: signals 自动桥接 ``paper_arxiv_id`` ↔ ``Paper`` FK.

设计：现有 extractor / interpreter / persist 流向 5 类 material + Claim 表
写 ``paper_arxiv_id``（CharField）。本次重构在这些表上加了 ``paper`` FK，
但**不修改**已有的 persist 代码（CLAUDE.md 锁：保留 docling 抽取流不动，
派发文档允许列里也明确 forbid ``apps/extract/extractors/**``）。

折中：用 ``pre_save`` signal 在落库前如果 ``paper_id is None`` 但
``paper_arxiv_id`` 非空，就 ``get_or_create(Paper)`` 把 FK 补上。这样
既有写入路径零改动，新接口和 user_* 表能享受 FK；signal 也是
``UserPaperStatus`` 自动落 default ``new`` 行的入口。
"""
from __future__ import annotations

import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.extract.models import Citation, Equation, Figure, Section, Table
from apps.interpret.models import Claim
from apps.papers.models import Paper, PaperStatus, UserPaperStatus

log = logging.getLogger(__name__)


def _ensure_paper_fk(instance) -> None:
    """通用 paper FK 自动桥接.

    ``paper`` 已显式赋值 → 不动。
    ``paper`` 为空但 ``paper_arxiv_id`` 非空 → ``get_or_create(Paper)`` 补 FK。
    两者都空 → 让 model NOT NULL 直接报错（说明上游忘了传）。
    """
    if getattr(instance, "paper_id", None) is not None:
        return
    arxiv_id = getattr(instance, "paper_arxiv_id", "") or ""
    if not arxiv_id:
        return
    paper, _ = Paper.objects.get_or_create(
        arxiv_id=arxiv_id,
        defaults={"title": f"arxiv:{arxiv_id}"},
    )
    instance.paper = paper


# ---- extract / interpret 落库前自动补 paper FK ----

@receiver(pre_save, sender=Section)
@receiver(pre_save, sender=Figure)
@receiver(pre_save, sender=Table)
@receiver(pre_save, sender=Equation)
@receiver(pre_save, sender=Citation)
@receiver(pre_save, sender=Claim)
def _autowire_paper_fk(sender, instance, **kwargs):  # noqa: ANN001, D401
    """在 5 类 material + Claim 落库前桥接 paper_arxiv_id → Paper FK。"""
    _ensure_paper_fk(instance)


# ---- Paper 创建后自动建 default UserPaperStatus ----

@receiver(post_save, sender=Paper)
def _create_default_status(sender, instance, created, **kwargs):  # noqa: ANN001, D401
    """Paper 新建时自动落一条 ``status=new``，供 user_* 层使用。"""
    if not created:
        return
    UserPaperStatus.objects.get_or_create(
        paper=instance,
        defaults={"status": PaperStatus.NEW.value},
    )
