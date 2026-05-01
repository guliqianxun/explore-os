"""ft-028: Paper 顶层实体 + user_* 4 张表.

设计要点：
- ``Paper.key`` 为 ``[A-Z2-9]{8}`` Zotero 风格随机串（32^8 ≈ 1.1e12 空间，
  per-paper 个体冲突概率近 0；``gen_key()`` 仍 retry 3 次再让 IntegrityError
  冒泡）。``arxiv_id`` / ``doi`` 降为 Paper 元数据列（unique 但可空）。
- ``UserPaperStatus`` 与 Paper 一一对应。Paper 创建时由 signal 自动新建一条
  default ``new`` 行（见 ``apps/papers/signals.py``）。
- ``UserComment`` append-only：API 仅暴露 POST + GET 列表 + PATCH（且只能改
  ``hidden``），不提供 PUT / DELETE。
- ``UserTag.unique_together = (paper, tag)``。
- ``UserBacklink`` 双向：通过 ``related_name="backlinks_out / backlinks_in"``
  实现 ``paper.backlinks_out / paper.backlinks_in`` 互查。
- 所有表加 ``papers_`` db_table 前缀，兼容未来 SQLite 拆库（CLAUDE.md 锁
  定）。
"""
from __future__ import annotations

import secrets

from django.db import IntegrityError, models, transaction


# ``[A-Z2-9]`` 32 字符（去掉 0/1/I/O 视觉歧义字符），8 位 = 32^8 ≈ 1.1e12
# Zotero-style. 去 I/O 避免与 1/0 混淆；去 0/1 避免与 O/I 混淆。
PAPER_KEY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
PAPER_KEY_LEN = 8


class PaperStatus(models.TextChoices):
    NEW = "new", "New"
    QUEUED = "queued", "Queued"
    READING = "reading", "Reading"
    READ_KEPT = "read_kept", "Read · Kept"
    READ_DROPPED = "read_dropped", "Read · Dropped"
    ARCHIVED = "archived", "Archived"


# 状态机合法转换图：from → set(to). UI / API 强制走这张图，避免脏跳。
# 任意状态都可以回 ``new``（撤销）；任意状态可 archive；read_* 可互转
# （改主意）。
STATUS_TRANSITIONS: dict[str, set[str]] = {
    PaperStatus.NEW.value: {
        PaperStatus.QUEUED.value,
        PaperStatus.READING.value,
        PaperStatus.READ_DROPPED.value,
        PaperStatus.ARCHIVED.value,
    },
    PaperStatus.QUEUED.value: {
        PaperStatus.NEW.value,
        PaperStatus.READING.value,
        PaperStatus.READ_DROPPED.value,
        PaperStatus.ARCHIVED.value,
    },
    PaperStatus.READING.value: {
        PaperStatus.NEW.value,
        PaperStatus.QUEUED.value,
        PaperStatus.READ_KEPT.value,
        PaperStatus.READ_DROPPED.value,
        PaperStatus.ARCHIVED.value,
    },
    PaperStatus.READ_KEPT.value: {
        PaperStatus.NEW.value,
        PaperStatus.READING.value,
        PaperStatus.READ_DROPPED.value,
        PaperStatus.ARCHIVED.value,
    },
    PaperStatus.READ_DROPPED.value: {
        PaperStatus.NEW.value,
        PaperStatus.READING.value,
        PaperStatus.READ_KEPT.value,
        PaperStatus.ARCHIVED.value,
    },
    PaperStatus.ARCHIVED.value: {
        PaperStatus.NEW.value,
        PaperStatus.QUEUED.value,
        PaperStatus.READING.value,
    },
}


def is_legal_transition(src: str, dst: str) -> bool:
    """状态机合法转换检查。同状态自跳视为合法（幂等）。"""
    if src == dst:
        return True
    return dst in STATUS_TRANSITIONS.get(src, set())


class Paper(models.Model):
    """论文顶层实体.

    身份：``key``（Zotero 风格 8 字符稳定 ID）+ ``arxiv_id`` / ``doi``
    可选元数据。``key`` 在 ``save()`` 时若空则 ``gen_key()`` 三次重试再
    冒泡 IntegrityError。
    """

    key = models.CharField(max_length=PAPER_KEY_LEN, unique=True, db_index=True)
    title = models.TextField()
    arxiv_id = models.CharField(
        max_length=64, null=True, blank=True, unique=True, db_index=True,
    )
    doi = models.CharField(max_length=128, null=True, blank=True, db_index=True)
    # ft-029: 落盘 PDF 的绝对路径（由 ingest 链路写入；空表示未持有）。
    # 走 TextField 避开 Path 长度上限；SQLite-friendly。
    pdf_path = models.TextField(null=True, blank=True)
    # ft-033: 原文 abstract（从 docling 第一个 abstract section 回填 / ingest 时写入）。
    # 是 brief_generator 喂给 skim_interpret 的输入；空时 brief 仅显示 title。
    abstract = models.TextField(blank=True, default="")
    # 作者上传的 keywords（区别于 brief.keywords —— 后者是 LLM 抽出的）。
    # arxiv 元数据无原生 keywords 字段，主要由 PDF/URL ingest 时用户填入或
    # detail 页手动编辑。空数组表示 paper 未声明 author keywords。
    keywords = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "papers_paper"

    def __str__(self) -> str:  # pragma: no cover
        return f"Paper(key={self.key}, arxiv_id={self.arxiv_id})"

    # ---------------- key gen ----------------

    @classmethod
    def gen_key(cls) -> str:
        """生成 8 字符 ``[A-Z2-9]`` 随机串（``secrets``-based）。"""
        return "".join(
            secrets.choice(PAPER_KEY_ALPHABET) for _ in range(PAPER_KEY_LEN)
        )

    def save(self, *args, **kwargs):  # noqa: D401
        """落库前若 key 空则三次重试生成；仍冲突则让 IntegrityError 冒泡。"""
        if self.key:
            return super().save(*args, **kwargs)

        last_exc: IntegrityError | None = None
        for _ in range(3):
            self.key = self.gen_key()
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError as exc:
                last_exc = exc
                self.key = ""  # 让下一轮重试
        # 三次都冲突：让最后一次抛出（极低概率，理论上 32^8 远大于本地数据）
        if last_exc is not None:
            raise last_exc
        return None


class UserPaperStatus(models.Model):
    """每篇论文的阅读状态（单用户场景，OneToOne）.

    Paper 创建时由 signal 自动建一条 default ``new``。状态切换走 API
    ``POST /api/papers/<id>/status/``，会先检查 :func:`is_legal_transition`。
    """

    paper = models.OneToOneField(
        Paper, on_delete=models.CASCADE, related_name="user_status",
    )
    status = models.CharField(
        max_length=24,
        choices=PaperStatus.choices,
        default=PaperStatus.NEW.value,
        db_index=True,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "papers_user_status"

    def __str__(self) -> str:  # pragma: no cover
        return f"UserPaperStatus(paper={self.paper.key}, status={self.status})"


class UserComment(models.Model):
    """append-only 评论：仅可标 ``hidden``，不提供 PUT/DELETE."""

    paper = models.ForeignKey(
        Paper, on_delete=models.CASCADE, related_name="comments",
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    hidden = models.BooleanField(default=False)

    class Meta:
        db_table = "papers_user_comment"
        ordering = ["created_at"]


class UserTag(models.Model):
    """论文级 tag。``unique_together(paper, tag)`` 防重复。"""

    paper = models.ForeignKey(
        Paper, on_delete=models.CASCADE, related_name="tags",
    )
    tag = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "papers_user_tag"
        unique_together = [("paper", "tag")]
        ordering = ["created_at"]


class UserBacklink(models.Model):
    """paper ↔ paper 双向链接。``relation`` 可选（如 supports/contradicts）.

    通过 ``backlinks_out``（src=this paper）+ ``backlinks_in``（dst=this paper）
    实现双向查询。
    """

    src = models.ForeignKey(
        Paper, on_delete=models.CASCADE, related_name="backlinks_out",
    )
    dst = models.ForeignKey(
        Paper, on_delete=models.CASCADE, related_name="backlinks_in",
    )
    relation = models.CharField(max_length=64, blank=True, default="")
    note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "papers_user_backlink"
        unique_together = [("src", "dst", "relation")]
        ordering = ["created_at"]


class PaperBrief(models.Model):
    """ft-033: 复用老邮件 pipeline (interpret/interpretation.py) 的内容缓存壳.

    skim_interpret + deep_interpret 现是内存 dataclass，本表把它们落 SQLite，
    让 BriefView / PaperDetail / 其它 UI 视图都能吃同一份缓存。生成走
    ``brief_generator.generate_brief(paper)``。OneToOne 决定一篇 paper 一份
    brief；regenerate 是覆盖式更新（updated_at 跟 auto_now）。

    Out-of-Scope（v1.2）：历史版本 / 跨用户共享 / per-paper perspective override。
    """

    paper = models.OneToOneField(
        Paper, on_delete=models.CASCADE,
        related_name="brief", primary_key=True,
    )
    # skim_interpret 产出
    abstract_zh = models.TextField(blank=True, default="")
    keywords = models.JSONField(default=list, blank=True)
    # deep_interpret 产出（iter-002 占位的字段也透传，前端按需展示）
    method_summary_zh = models.TextField(blank=True, default="")
    key_innovation = models.JSONField(default=list, blank=True)
    limitations = models.JSONField(default=list, blank=True)
    for_you = models.TextField(blank=True, default="")
    # 一句话 TL;DR（从 abstract_zh 头部按句末截）
    tldr_zh = models.TextField(blank=True, default="")
    # meta — 用于审计 / "用什么视角生成的" 提示
    perspective_used = models.CharField(max_length=128, blank=True, default="")
    model_used = models.CharField(max_length=64, blank=True, default="")
    generated_at = models.DateTimeField(auto_now=True)
    # ft-040: paper 主语言。``zh`` | ``en``。决定 _zh 字段内容是中文还是英文。
    lang = models.CharField(max_length=8, blank=True, default="")

    class Meta:
        db_table = "papers_brief"

    def __str__(self) -> str:  # pragma: no cover
        return f"PaperBrief(paper={self.paper.key}, persp={self.perspective_used})"
