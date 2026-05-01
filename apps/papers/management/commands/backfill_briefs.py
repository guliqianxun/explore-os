"""ft-040: 一次性给所有「extract 跑过但 brief 空」的 paper 补 brief。

判别：``Paper`` 行存在，且：
  - 有 docling Section（extract 已跑）
  - 没有 PaperBrief，或 PaperBrief.abstract_zh 为空

用法::

    uv run python manage.py backfill_briefs            # dry-run 列出
    uv run python manage.py backfill_briefs --apply    # 真跑
    uv run python manage.py backfill_briefs --apply --limit 1
    uv run python manage.py backfill_briefs --apply --paper 71ce5f63fb0b6795
"""
from __future__ import annotations

import time

from django.core.management.base import BaseCommand

from apps.extract.models import Section
from apps.papers.brief_generator import generate_brief
from apps.papers.models import Paper, PaperBrief


class Command(BaseCommand):
    help = "Generate PaperBrief for ingested papers that are missing one."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="actually run LLM")
        parser.add_argument("--limit", type=int, default=0, help="cap N papers")
        parser.add_argument("--paper", type=str, default="", help="single paper arxiv_id (or key)")
        parser.add_argument("--sleep", type=float, default=1.0, help="seconds between LLM calls")

    def handle(self, *args, apply: bool, limit: int, paper: str, sleep: float, **kw):
        if paper:
            paper = paper.strip()
            p = Paper.objects.filter(arxiv_id=paper).first()
            if p is None:
                p = Paper.objects.filter(key=paper).first()
            if p is None:
                self.stderr.write(f"paper not found: {paper}")
                return
            targets = [p]
        else:
            arxiv_ids_with_sections = set(
                Section.objects.values_list("paper_arxiv_id", flat=True).distinct(),
            )
            qs = Paper.objects.filter(arxiv_id__in=arxiv_ids_with_sections)
            targets = []
            for pp in qs:
                b = PaperBrief.objects.filter(paper=pp).first()
                if b and (b.abstract_zh or "").strip():
                    continue
                targets.append(pp)
            if limit:
                targets = targets[:limit]

        self.stdout.write(
            f"found {len(targets)} candidate(s). apply={apply}, sleep={sleep}",
        )
        if not targets:
            return

        ok = 0
        failed = 0
        for i, pp in enumerate(targets, 1):
            label = pp.arxiv_id or pp.key
            self.stdout.write(f"  [{i}/{len(targets)}] {label} ({pp.title[:60]!r}) ...")
            if not apply:
                continue
            try:
                b = generate_brief(pp, regenerate=True)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"    OK  lang={b.lang!r}  abs={len(b.abstract_zh)}  "
                        f"innov={len(b.key_innovation)}  limit={len(b.limitations)}",
                    ),
                )
                ok += 1
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(f"    FAIL {exc!r}")
                failed += 1
            if sleep and i < len(targets):
                time.sleep(sleep)

        self.stdout.write(
            self.style.SUCCESS(
                f"\ndone: ok={ok} failed={failed} (applied={apply})",
            ),
        )
