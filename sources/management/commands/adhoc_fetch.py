"""Ad-hoc fetch: 调一次所有注册 fetcher 并按分组打印结果。

仅用于实战验证（ft-003 / ft-004），不走订阅 / 不入库 / 不调 LLM / 不发邮件。

示例：
    uv run python manage.py adhoc_fetch \\
        --keywords "video generation" "text-to-video" \\
        --arxiv-categories cs.CV cs.LG \\
        --since-days 7 \\
        --limit 20
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from django.core.management.base import BaseCommand

# 触发 fetcher 注册
from sources import fetchers  # noqa: F401
from sources.base import REGISTRY, SourceQuery


class Command(BaseCommand):
    help = "Ad-hoc fetch from all registered sources (no DB / no LLM / no email)."
    requires_system_checks: list = []

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--keywords", nargs="+", required=True,
            help="通用关键词（arXiv fallback + HF 过滤）",
        )
        parser.add_argument(
            "--arxiv-query", default="",
            help="arXiv 原生布尔查询串，优先于 keywords",
        )
        parser.add_argument(
            "--arxiv-categories", nargs="*", default=[],
            help="arXiv categories（如 cs.CV cs.LG）",
        )
        parser.add_argument(
            "--since-days", type=int, default=7,
            help="往前推几天",
        )
        parser.add_argument(
            "--limit", type=int, default=20,
            help="每个 source 上限",
        )
        parser.add_argument(
            "--sources", nargs="*", default=None,
            help="只跑指定 source key（默认全部）",
        )
        parser.add_argument(
            "--verbose-http", action="store_true",
            help="打印 httpx DEBUG 日志",
        )

    def handle(self, *args, **opts) -> None:
        if opts["verbose_http"]:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)

        since = datetime.now(timezone.utc) - timedelta(days=opts["since_days"])
        query = SourceQuery(
            keywords=opts["keywords"],
            arxiv_query=opts["arxiv_query"],
            arxiv_categories=opts["arxiv_categories"],
            hf_keywords=opts["keywords"],
        )

        keys = opts["sources"] or list(REGISTRY.keys())
        self.stdout.write(self.style.NOTICE(
            f">> since={since.date().isoformat()}  limit={opts['limit']}  "
            f"sources={keys}  keywords={opts['keywords']}"
        ))

        all_items = []
        dedup_seen: dict[str, list[str]] = defaultdict(list)

        for key in keys:
            if key not in REGISTRY:
                self.stderr.write(self.style.ERROR(f"  skip unknown source: {key}"))
                continue
            fetcher = REGISTRY[key]
            t0 = datetime.now()
            try:
                items = fetcher.fetch(query, since=since, limit=opts["limit"])
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(self.style.ERROR(f"  [{key}] raised: {exc!r}"))
                continue
            dt = (datetime.now() - t0).total_seconds()
            self.stdout.write(self.style.SUCCESS(
                f"  [{key}] got {len(items)} items in {dt:.1f}s"
            ))
            for it in items:
                dedup_seen[it.dedup_key].append(key)
                all_items.append(it)

        # 按 group 聚合输出
        groups: dict[str, list] = defaultdict(list)
        for it in all_items:
            groups[it.group].append(it)

        self.stdout.write("")
        for group, items in groups.items():
            self.stdout.write(self.style.MIGRATE_HEADING(
                f"=== {group.upper()} ({len(items)} items) ==="
            ))
            for it in items:
                overlap = dedup_seen.get(it.dedup_key, [])
                dup_tag = f"  [dup across: {'+'.join(overlap)}]" if len(overlap) > 1 else ""
                date_str = (
                    it.published_at.date().isoformat() if it.published_at else "????-??-??"
                )
                authors = ", ".join(it.authors[:3]) + (
                    f" (+{len(it.authors) - 3})" if len(it.authors) > 3 else ""
                )
                self.stdout.write(
                    f"\n  - [{it.source_key}] {date_str}  {it.title}{dup_tag}\n"
                    f"    {authors}\n"
                    f"    {it.url}\n"
                    f"    dedup_key={it.dedup_key}"
                )

        # 跨源去重统计
        cross = sum(1 for keys in dedup_seen.values() if len(set(keys)) > 1)
        self.stdout.write("")
        self.stdout.write(self.style.NOTICE(
            f"== total={len(all_items)}  unique_keys={len(dedup_seen)}  "
            f"cross_source_dups={cross}"
        ))
