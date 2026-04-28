"""ft-028 step 5/9: 把 5 类 material 的 ``paper`` FK 改成 NOT NULL.

到这里所有现有行都已通过 0003 填好 ``paper_id``。
"""
from __future__ import annotations

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("extract", "0003_populate_paper_fk"),
    ]

    operations = [
        migrations.AlterField(
            model_name="section",
            name="paper",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="sections",
                to="papers.paper",
            ),
        ),
        migrations.AlterField(
            model_name="figure",
            name="paper",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="figures",
                to="papers.paper",
            ),
        ),
        migrations.AlterField(
            model_name="table",
            name="paper",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="tables",
                to="papers.paper",
            ),
        ),
        migrations.AlterField(
            model_name="equation",
            name="paper",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="equations",
                to="papers.paper",
            ),
        ),
        migrations.AlterField(
            model_name="citation",
            name="paper",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="citations",
                to="papers.paper",
            ),
        ),
    ]
