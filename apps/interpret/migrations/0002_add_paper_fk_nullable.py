"""ft-028 step 6/9: 给 ``Claim`` 加 nullable ``paper`` FK + index.

``ClaimEvidence`` / ``CounterSignal`` 二跳到 paper（``claim__paper``），
这里只动 Claim 表。
"""
from __future__ import annotations

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("interpret_v2", "0001_initial"),
        ("papers", "0002_backfill_papers"),
    ]

    operations = [
        migrations.AddField(
            model_name="claim",
            name="paper",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="claims",
                to="papers.paper",
            ),
        ),
    ]
