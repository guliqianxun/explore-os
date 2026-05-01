"""ft-031.5 follow-up: 一次性回填 Paper.abstract 给 ingest arxiv 链路漏写的存量行。

判别：``arxiv_id`` 形似 arXiv id（YYMM.nnnnn[vN]）且 ``abstract`` 为空。
拉 arXiv API metadata，写回 abstract 和（可能 fallback 形如 "arxiv:xxx" 的）title。

用法::

    uv run python manage.py backfill_abstracts          # dry run
    uv run python manage.py backfill_abstracts --apply  # 真写
    uv run python manage.py backfill_abstracts --limit 5
"""
from __future__ import annotations

import re
import time

import httpx
from django.core.management.base import BaseCommand

from apps.papers.models import Paper
from sources.fetchers.arxiv import _parse_atom

ARXIV_ID_RE = re.compile(r"^\d{4}\.\d{4,5}(v\d+)?$")


class Command(BaseCommand):
    help = "Backfill Paper.abstract from arXiv API for rows missing it."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="actually write")
        parser.add_argument("--limit", type=int, default=0, help="cap N rows")
        parser.add_argument(
            "--sleep", type=float, default=0.5, help="seconds between API calls",
        )

    def handle(self, *args, apply: bool, limit: int, sleep: float, **kw):
        qs = Paper.objects.filter(abstract="").exclude(arxiv_id="")
        targets = [
            p for p in qs if p.arxiv_id and ARXIV_ID_RE.match(p.arxiv_id)
        ]
        if limit:
            targets = targets[:limit]
        self.stdout.write(
            f"found {len(targets)} candidates "
            f"(apply={apply}, sleep={sleep})",
        )

        ok = 0
        empty = 0
        failed = 0
        for i, p in enumerate(targets, 1):
            arxiv_id = p.arxiv_id
            try:
                r = httpx.get(
                    f"http://export.arxiv.org/api/query?id_list={arxiv_id}",
                    timeout=15.0,
                    follow_redirects=True,
                )
                r.raise_for_status()
                items = _parse_atom(r.text)
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(f"  [{i}/{len(targets)}] {arxiv_id} FAIL {exc!r}")
                failed += 1
                continue
            if not items or not items[0].abstract:
                self.stdout.write(f"  [{i}/{len(targets)}] {arxiv_id} EMPTY")
                empty += 1
                continue
            it = items[0]
            self.stdout.write(
                f"  [{i}/{len(targets)}] {arxiv_id} → {len(it.abstract)} chars",
            )
            if apply:
                p.abstract = it.abstract
                if not p.title or p.title.startswith("arxiv:"):
                    p.title = it.title or p.title
                p.save(update_fields=["abstract", "title"])
            ok += 1
            if sleep:
                time.sleep(sleep)

        self.stdout.write(
            self.style.SUCCESS(
                f"\ndone: ok={ok} empty={empty} failed={failed} "
                f"(applied={apply})",
            ),
        )
