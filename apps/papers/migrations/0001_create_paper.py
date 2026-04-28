"""ft-028 step 1/9: 新建 ``papers_paper`` 表（Paper 顶层实体）.

不依赖任何既有 app 表 — 单纯 schema add，可独立 forward / reverse。
"""
from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies: list = []

    operations = [
        migrations.CreateModel(
            name="Paper",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID",
                )),
                ("key", models.CharField(db_index=True, max_length=8, unique=True)),
                ("title", models.TextField()),
                ("arxiv_id", models.CharField(
                    blank=True, db_index=True, max_length=64, null=True, unique=True,
                )),
                ("doi", models.CharField(
                    blank=True, db_index=True, max_length=128, null=True,
                )),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "papers_paper"},
        ),
    ]
