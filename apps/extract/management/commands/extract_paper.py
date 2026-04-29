"""ft-019: ``python manage.py extract_paper <arxiv_id>`` 把缓存 PDF 跑全套抽取并落库.

DEPRECATED (ft-034 P1-4): 0 ``call_command`` 引用，与 ``apps/api/ingest._run_extract``
逻辑重复。生产入口走 ``chain_extract_interpret_render``；本 CLI 仅 dev 调试 fallback。
v1.4 决议是否删除。

PDF 路径默认在 ``EXPLORE_OS_DATA_DIR/media/pdf/<arxiv_id>.pdf``（ft-022 起走 paths 抽象，
不再 hardcode ``BASE_DIR/media``）。可通过 ``--pdf-path`` 覆盖。
"""
from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.core.paths import pdf_legacy_dir
from apps.extract.extractor import extract, persist_result


class Command(BaseCommand):
    help = "Extract sections / figures / tables / equations / citations for a paper PDF."

    def add_arguments(self, parser):
        parser.add_argument("arxiv_id", help="arXiv id, e.g. 2401.12345")
        parser.add_argument(
            "--pdf-path",
            default=None,
            help="Override PDF path (default: <DATA_DIR>/media/pdf/<arxiv_id>.pdf)",
        )

    def handle(self, *args, **opts):
        arxiv_id: str = opts["arxiv_id"]
        pdf_path = (
            Path(opts["pdf_path"])
            if opts.get("pdf_path")
            else pdf_legacy_dir() / f"{arxiv_id}.pdf"
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
