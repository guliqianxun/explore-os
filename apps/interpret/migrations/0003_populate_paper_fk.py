"""ft-028 step 7/9: 把 ``Claim.paper_id`` 从 ``paper_arxiv_id`` 填上.

reverse：把 ``paper_id`` 清回 NULL。
"""
from __future__ import annotations

from django.db import migrations


def forwards(apps, schema_editor):
    Paper = apps.get_model("papers", "Paper")
    Claim = apps.get_model("interpret_v2", "Claim")
    paper_by_arxiv: dict[str, int] = {
        aid: pid
        for aid, pid in Paper.objects.exclude(arxiv_id__isnull=True)
        .values_list("arxiv_id", "id")
    }
    for arxiv_id, paper_id in paper_by_arxiv.items():
        Claim.objects.filter(paper_arxiv_id=arxiv_id, paper_id__isnull=True).update(
            paper_id=paper_id,
        )


def backwards(apps, schema_editor):
    Claim = apps.get_model("interpret_v2", "Claim")
    Claim.objects.update(paper_id=None)


class Migration(migrations.Migration):

    dependencies = [
        ("interpret_v2", "0002_add_paper_fk_nullable"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
