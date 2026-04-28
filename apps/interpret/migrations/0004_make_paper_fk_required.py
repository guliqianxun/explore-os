"""ft-028 step 8/9: 把 ``Claim.paper`` 改成 NOT NULL."""
from __future__ import annotations

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("interpret_v2", "0003_populate_paper_fk"),
    ]

    operations = [
        migrations.AlterField(
            model_name="claim",
            name="paper",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="claims",
                to="papers.paper",
            ),
        ),
    ]
