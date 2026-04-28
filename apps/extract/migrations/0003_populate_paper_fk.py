"""ft-028 step 4/9: 把 5 类 material 的 ``paper_id`` 从 ``paper_arxiv_id`` 填上.

经过 papers/0002，每个 distinct ``paper_arxiv_id`` 对应一行 Paper；
这里 JOIN 写回 ``paper_id``。

reverse：把 ``paper_id`` 清回 NULL（NOT NULL 的迁移要 0004 才发生，
所以 reverse 安全）。
"""
from __future__ import annotations

from django.db import migrations


_MODELS = ["Section", "Figure", "Table", "Equation", "Citation"]


def forwards(apps, schema_editor):
    Paper = apps.get_model("papers", "Paper")
    paper_by_arxiv: dict[str, int] = {
        aid: pid
        for aid, pid in Paper.objects.exclude(arxiv_id__isnull=True)
        .values_list("arxiv_id", "id")
    }
    for model_name in _MODELS:
        Model = apps.get_model("extract", model_name)
        for arxiv_id, paper_id in paper_by_arxiv.items():
            Model.objects.filter(paper_arxiv_id=arxiv_id, paper_id__isnull=True).update(
                paper_id=paper_id,
            )


def backwards(apps, schema_editor):
    for model_name in _MODELS:
        Model = apps.get_model("extract", model_name)
        Model.objects.update(paper_id=None)


class Migration(migrations.Migration):

    dependencies = [
        ("extract", "0002_add_paper_fk_nullable"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
