"""ft-033: 回填既有 Paper.abstract — 从 docling 抽出来的 Section 找 abstract.

策略：
  1) ``Section.path icontains 'abstract'`` 的最低 ordinal/seq 行
  2) 没匹配 → ordinal=1 / seq=1 第一个 section
  3) 仍没 → 留空（前端 fallback title）

reverse 是 no-op：不重置 abstract（用户后续可能手动改）。
"""
from __future__ import annotations

from django.db import migrations


_MAX_ABSTRACT_LEN = 4000


def _pick_abstract_text(Section, paper) -> str:
    qs = Section.objects.filter(paper=paper)
    sec = (
        qs.filter(path__icontains="abstract").order_by("seq").first()
        or qs.order_by("seq").first()
    )
    if sec and sec.raw_text:
        return sec.raw_text.strip()[:_MAX_ABSTRACT_LEN]
    return ""


def backfill(apps, schema_editor):
    Paper = apps.get_model("papers", "Paper")
    Section = apps.get_model("extract", "Section")
    for p in Paper.objects.filter(abstract=""):
        text = _pick_abstract_text(Section, p)
        if text:
            p.abstract = text
            p.save(update_fields=["abstract"])


def noop(apps, schema_editor):
    """reverse no-op：不擦 abstract，避免破坏用户后续手动编辑。"""


class Migration(migrations.Migration):

    dependencies = [
        ("papers", "0005_paperbrief_paper_abstract"),
        ("extract", "0004_make_paper_fk_required"),
    ]

    operations = [
        migrations.RunPython(backfill, reverse_code=noop),
    ]
