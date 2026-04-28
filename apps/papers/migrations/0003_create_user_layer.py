"""ft-028 step 9/9: 新建 user_* 4 张表（status / comment / tag / backlink）.

放在最后是因为它们都是 Paper 的下游 FK；前面的迁移完事后这里只 schema add。
``UserPaperStatus`` 是 OneToOne：每篇 Paper 创建时由 ``apps.papers.signals``
post_save 自动落一条 ``new``，data migration 兜底为已存在的 Paper 也补上。
"""
from __future__ import annotations

import django.db.models.deletion
from django.db import migrations, models


def populate_default_status(apps, schema_editor):
    """对所有现有 Paper 兜底建一条 default ``new`` 状态行（signal 在
    旧 Paper 已落库后才注册，所以需要 data migration 一次性补齐）。
    """
    Paper = apps.get_model("papers", "Paper")
    UserPaperStatus = apps.get_model("papers", "UserPaperStatus")
    for paper in Paper.objects.all():
        UserPaperStatus.objects.get_or_create(
            paper=paper, defaults={"status": "new"},
        )


def remove_default_status(apps, schema_editor):
    UserPaperStatus = apps.get_model("papers", "UserPaperStatus")
    UserPaperStatus.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("papers", "0002_backfill_papers"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserPaperStatus",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID",
                )),
                ("status", models.CharField(
                    choices=[
                        ("new", "New"),
                        ("queued", "Queued"),
                        ("reading", "Reading"),
                        ("read_kept", "Read · Kept"),
                        ("read_dropped", "Read · Dropped"),
                        ("archived", "Archived"),
                    ],
                    db_index=True, default="new", max_length=24,
                )),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("paper", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="user_status",
                    to="papers.paper",
                )),
            ],
            options={"db_table": "papers_user_status"},
        ),
        migrations.CreateModel(
            name="UserComment",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID",
                )),
                ("text", models.TextField()),
                ("created_at", models.DateTimeField(
                    auto_now_add=True, db_index=True,
                )),
                ("hidden", models.BooleanField(default=False)),
                ("paper", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="comments",
                    to="papers.paper",
                )),
            ],
            options={
                "db_table": "papers_user_comment",
                "ordering": ["created_at"],
            },
        ),
        migrations.CreateModel(
            name="UserTag",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID",
                )),
                ("tag", models.CharField(max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("paper", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="tags",
                    to="papers.paper",
                )),
            ],
            options={
                "db_table": "papers_user_tag",
                "ordering": ["created_at"],
                "unique_together": {("paper", "tag")},
            },
        ),
        migrations.CreateModel(
            name="UserBacklink",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID",
                )),
                ("relation", models.CharField(blank=True, default="", max_length=64)),
                ("note", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("dst", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="backlinks_in",
                    to="papers.paper",
                )),
                ("src", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="backlinks_out",
                    to="papers.paper",
                )),
            ],
            options={
                "db_table": "papers_user_backlink",
                "ordering": ["created_at"],
                "unique_together": {("src", "dst", "relation")},
            },
        ),
        migrations.RunPython(populate_default_status, remove_default_status),
    ]
