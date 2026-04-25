"""ft-019: ``python manage.py extract_paper <arxiv_id>`` 把缓存 PDF 跑全套抽取并落库.

PDF 路径默认在 ``media/pdf/<arxiv_id>.pdf``（与 ft-013/014 缓存一致）。
可通过 ``--pdf-path`` 覆盖。
"""
from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.extract.extractor import extract, persist_result


class Command(BaseCommand):
    help = "Extract sections / figures / tables / equations / citations for a paper PDF."

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

        self.stdout.write(f"[extract] arxiv_id={arxiv_id} pdf={pdf_path}")
        result = extract(pdf_path, arxiv_id)
        counts = persist_result(result)
        self.stdout.write(self.style.SUCCESS(
            "[extract] done: "
            f"sections={counts['sections']} "
            f"figures={counts['figures']} "
            f"tables={counts['tables']} "
            f"equations={counts['equations']} "
            f"citations={counts['citations']}"
        ))
