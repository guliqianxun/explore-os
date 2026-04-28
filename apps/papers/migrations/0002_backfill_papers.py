"""ft-028 step 2/9: data migration — 从既有 ``paper_arxiv_id`` 集合批量创建 Paper.

来源：``extract_sections`` distinct ``paper_arxiv_id``（覆盖最完整；
figure / table / equation / citation / claim 都 by 同一个 paper 抽出，
section 一定在）。fallback：把 figure / table / equation / citation /
claim 的 distinct paper_arxiv_id 也合并进来，以防极端情况某 paper 没
section（理论上不会）。

Title 取该 paper 的第一个 section.path，前提是 path 不像 "1 Introduction"
之类的分章标题；否则 fallback ``arxiv:<arxiv_id>``。

reverse：删除所有由本迁移创建的 Paper（按 arxiv_id 反查；不删 user_*
因为后面的迁移会单独反向）。
"""
from __future__ import annotations

import re
import secrets

from django.db import migrations


# 与 ``apps/papers/models.py`` 保持一致。这里复制是为了避免 migration
# 直接 import models（runtime model 可能在反向迁移时不存在）。
PAPER_KEY_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ23456789"
PAPER_KEY_LEN = 8


_GENERIC_TITLE_RE = re.compile(
    r"^\s*(\d+\.|\d+\s|abstract|introduction|references|conclusion|appendix|background)",
    re.IGNORECASE,
)


def _gen_key() -> str:
    return "".join(secrets.choice(PAPER_KEY_ALPHABET) for _ in range(PAPER_KEY_LEN))


def _looks_like_title(path: str) -> bool:
    """path 是否像论文标题（不是常见的章节名 / 编号开头）。"""
    if not path:
        return False
    if _GENERIC_TITLE_RE.match(path):
        return False
    # 长度 < 5 大概率是占位符，不当 title 用
    return len(path.strip()) >= 5


def _gather_arxiv_ids(apps) -> set[str]:
    """从所有持有 ``paper_arxiv_id`` 的表里收 distinct id."""
    ids: set[str] = set()
    for app_label, model_name in [
        ("extract", "Section"),
        ("extract", "Figure"),
        ("extract", "Table"),
        ("extract", "Equation"),
        ("extract", "Citation"),
        ("interpret_v2", "Claim"),
    ]:
        try:
            model = apps.get_model(app_label, model_name)
        except LookupError:
            continue
        for aid in model.objects.values_list("paper_arxiv_id", flat=True).distinct():
            if aid:
                ids.add(aid)
    return ids


def _pick_title(apps, arxiv_id: str) -> str:
    Section = apps.get_model("extract", "Section")
    candidates = (
        Section.objects.filter(paper_arxiv_id=arxiv_id).order_by("seq")
        .values_list("path", flat=True)[:5]
    )
    for path in candidates:
        if _looks_like_title(path):
            return path
    return f"arxiv:{arxiv_id}"


def _generate_unique_key(Paper, used_keys: set[str]) -> str:
    """三次重试找一个未占用的 key（含本次进程中已分配的）。"""
    for _ in range(8):  # 数据迁移容忍多一些重试
        key = _gen_key()
        if key in used_keys:
            continue
        if not Paper.objects.filter(key=key).exists():
            used_keys.add(key)
            return key
    # 极端情况：让最后一个 key 落库失败由 IntegrityError 冒泡
    return _gen_key()


def forwards(apps, schema_editor):
    Paper = apps.get_model("papers", "Paper")
    arxiv_ids = sorted(_gather_arxiv_ids(apps))
    used_keys: set[str] = set(Paper.objects.values_list("key", flat=True))

    for aid in arxiv_ids:
        if Paper.objects.filter(arxiv_id=aid).exists():
            continue
        title = _pick_title(apps, aid)
        key = _generate_unique_key(Paper, used_keys)
        Paper.objects.create(key=key, arxiv_id=aid, title=title)


def backwards(apps, schema_editor):
    """反向：把通过本迁移创建的 Paper 全删（用 ``arxiv_id`` 在抽取库里反查）.

    注意：本迁移可能在 ``user_*`` 表已建好的状态下被反向（papers/0003 在
    后面），但 OneToOne / FK 都是 CASCADE，一并清理即可。
    """
    Paper = apps.get_model("papers", "Paper")
    arxiv_ids = _gather_arxiv_ids(apps)
    if arxiv_ids:
        Paper.objects.filter(arxiv_id__in=arxiv_ids).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("papers", "0001_create_paper"),
        # 必须等 extract / interpret_v2 表都在，才能 distinct paper_arxiv_id
        ("extract", "0001_initial"),
        ("interpret_v2", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
