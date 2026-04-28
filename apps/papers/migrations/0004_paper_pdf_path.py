"""ft-029: add Paper.pdf_path (nullable, no data migration needed).

PDF 落盘绝对路径。空 = 未持有（旧记录）。运行时 ``resolve_pdf_path()``
带 legacy fallback（``pdf_legacy_dir/<arxiv>.pdf``）。SQLite-friendly，
ORM-only schema add。
"""
from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("papers", "0003_create_user_layer"),
    ]

    operations = [
        migrations.AddField(
            model_name="paper",
            name="pdf_path",
            field=models.TextField(blank=True, null=True),
        ),
    ]
