"""ft-021: ``python manage.py render_graph <arxiv_id> [--format excalidraw|svg]``.

从 interpret_* + extract_* 表组装 PaperGraphModel，写出文件并落库 RenderArtifact。
"""
from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.render.excalidraw_renderer import ExcalidrawRenderer
from apps.render.graph import build_graph
from apps.render.persist import persist_artifact
from apps.render.svg_renderer import SvgRenderer


class Command(BaseCommand):
    help = "Render a single-paper interpretation graph (Excalidraw or SVG)."

    def add_arguments(self, parser):
        parser.add_argument("arxiv_id")
        parser.add_argument(
            "--format",
            choices=["excalidraw", "svg"],
            default="excalidraw",
        )
        parser.add_argument(
            "--out-dir",
            default="",
            help="Override output dir (default: <BASE_DIR>/media/render/<arxiv_id>).",
        )

    def handle(self, *args, **opts):
        arxiv_id = opts["arxiv_id"]
        fmt = opts["format"]

        graph = build_graph(arxiv_id)
        if not graph.nodes:
            self.stdout.write(self.style.WARNING(
                f"[render] no nodes for arxiv_id={arxiv_id} — empty graph will be written"
            ))

        if opts["out_dir"]:
            out_dir = Path(opts["out_dir"])
        else:
            out_dir = Path(settings.BASE_DIR) / "media" / "render" / arxiv_id
        out_dir.mkdir(parents=True, exist_ok=True)

        renderer = ExcalidrawRenderer() if fmt == "excalidraw" else SvgRenderer()
        path = renderer.render(graph, out_dir)

        meta = {
            "n_nodes": len(graph.nodes),
            "n_edges": len(graph.edges),
            "n_claims": sum(1 for n in graph.nodes if n.kind == "claim"),
            "n_figures": sum(1 for n in graph.nodes if n.kind == "figure"),
            "n_tables": sum(1 for n in graph.nodes if n.kind == "table"),
            "n_citations": sum(1 for n in graph.nodes if n.kind == "citation"),
        }
        artifact = persist_artifact(arxiv_id, fmt, path, payload_meta=meta)
        self.stdout.write(self.style.SUCCESS(
            f"[render] done: {artifact.artifact_id} → {path} "
            f"(nodes={meta['n_nodes']}, edges={meta['n_edges']})"
        ))
