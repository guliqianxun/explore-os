"""ft-028 step 3/9: 给 5 类 material 加 nullable ``paper`` FK + index.

nullable 是为了让现有数据先 ALTER 通过；下一步 0003 data migration 把
``paper_id`` 填上，再 0004 改成 NOT NULL。
"""
from __future__ import annotations

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("extract", "0001_initial"),
        ("papers", "0002_backfill_papers"),
    ]

    operations = [
        migrations.AddField(
            model_name="section",
            name="paper",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="sections",
                to="papers.paper",
            ),
        ),
        migrations.AddField(
            model_name="figure",
            name="paper",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="figures",
                to="papers.paper",
            ),
        ),
        migrations.AddField(
            model_name="table",
            name="paper",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="tables",
                to="papers.paper",
            ),
        ),
        migrations.AddField(
            model_name="equation",
            name="paper",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="equations",
                to="papers.paper",
            ),
        ),
        migrations.AddField(
            model_name="citation",
            name="paper",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="citations",
                to="papers.paper",
            ),
        ),
    ]
