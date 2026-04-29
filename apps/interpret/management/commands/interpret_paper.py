"""ft-020: ``python manage.py interpret_paper <arxiv_id>`` 跑 L1+L2 并落库.

DEPRECATED (ft-034 P1-4): 0 ``call_command`` 引用，与 ``apps/api/ingest._run_interpret``
逻辑重复。生产入口走 ``chain_extract_interpret_render``；本 CLI 仅 dev 调试 fallback。
v1.4 决议是否删除。

依赖：``apps.extract`` 抽取产物已落 ``extract_*`` 表 + ``EXPLORE_OS_DATA_DIR/media/pdf/<arxiv_id>.pdf``
已存在（ft-022 起走 paths 抽象，不再 hardcode ``BASE_DIR/media``）。
"""
from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.core.paths import pdf_legacy_dir
from apps.interpret.interpreter import DefaultInterpreter
from apps.interpret.persist import persist_result


class Command(BaseCommand):
    help = "Run L1 (claim extraction) + L2 (counter signals) for a paper and persist results."

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

        self.stdout.write(f"[interpret] arxiv_id={arxiv_id} pdf={pdf_path}")
        result = DefaultInterpreter().interpret(arxiv_id, pdf_path)
        counts = persist_result(result)
        self.stdout.write(self.style.SUCCESS(
            "[interpret] done: "
            f"claims={counts['claims']} "
            f"evidence={counts['evidence']} "
            f"signals={counts['signals']}"
        ))
