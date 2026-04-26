"""ft-020: ``python manage.py interpret_paper <arxiv_id>`` 跑 L1+L2 并落库.

依赖：``apps.extract`` 抽取产物已落 ``extract_*`` 表 + media/pdf/<arxiv_id>.pdf 已存在。
"""
from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.interpret.interpreter import DefaultInterpreter
from apps.interpret.persist import persist_result


class Command(BaseCommand):
    help = "Run L1 (claim extraction) + L2 (counter signals) for a paper and persist results."

    def add_arguments(self, parser):
        parser.add_argument("arxiv_id", help="arXiv id, e.g. 2401.12345")
        parser.add_argument(
            "--pdf-path",
            default=None,
            help="Override PDF path (default: media/pdf/<arxiv_id>.pdf)",
        )

    def handle(self, *args, **opts):
        arxiv_id: str = opts["arxiv_id"]
        pdf_path = (
            Path(opts["pdf_path"])
            if opts.get("pdf_path")
            else Path(settings.BASE_DIR) / "media" / "pdf" / f"{arxiv_id}.pdf"
        )
        if not pdf_path.exists():
            raise CommandError(f"PDF not found: {pdf_path}")

        self.stdout.write(f"[interpret] arxiv_id={arxiv_id} pdf={pdf_path}")
        result = DefaultInterpreter().interpret(arxiv_id, pdf_path)
        counts = persist_result(result)
        self.stdout.write(self.style.SUCCESS(
            "[interpret] done: "
            f"claims={counts['claims']} "
            f"evidence={counts['evidence']} "
            f"signals={counts['signals']}"
        ))
