"""Job triggers (extract / interpret / render) + JobStatusView.

ft-022 base. The actual in-memory job queue lives in ``apps.api.jobs``;
these views are thin wrappers that enqueue + return JobInfo via JobSerializer.
"""
from __future__ import annotations

from pathlib import Path

from django.http import Http404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api import jobs
from apps.api.serializers import JobSerializer
from apps.core import paths


def _default_pdf_path(arxiv_id: str) -> Path:
    """与 4 个 CLI 默认 PDF 位置保持一致：``<DATA_DIR>/media/pdf/<arxiv_id>.pdf``。"""
    return paths.pdf_legacy_dir() / f"{arxiv_id}.pdf"


# ---------------- triggers ----------------

def _do_extract(arxiv_id: str, pdf_path: str) -> dict:
    from apps.extract.extractor import extract, persist_result
    result = extract(Path(pdf_path), arxiv_id)
    counts = persist_result(result)
    return {"arxiv_id": arxiv_id, "counts": counts}


def _do_interpret(arxiv_id: str, pdf_path: str) -> dict:
    from apps.interpret.interpreter import DefaultInterpreter
    from apps.interpret.persist import persist_result
    result = DefaultInterpreter().interpret(arxiv_id, Path(pdf_path))
    counts = persist_result(result)
    return {"arxiv_id": arxiv_id, "counts": counts}


def _do_render(arxiv_id: str, fmt: str = "excalidraw") -> dict:
    from apps.render.excalidraw_renderer import ExcalidrawRenderer
    from apps.render.graph import build_graph
    from apps.render.persist import persist_artifact
    from apps.render.svg_renderer import SvgRenderer

    graph = build_graph(arxiv_id)
    out_dir = paths.render_dir(arxiv_id)
    renderer = ExcalidrawRenderer() if fmt == "excalidraw" else SvgRenderer()
    path = renderer.render(graph, out_dir)
    artifact = persist_artifact(arxiv_id, fmt, path, payload_meta={
        "n_nodes": len(graph.nodes), "n_edges": len(graph.edges),
    })
    return {
        "arxiv_id": arxiv_id, "fmt": fmt,
        "artifact_id": artifact.artifact_id, "path": str(path),
    }


class ExtractTriggerView(APIView):
    def post(self, request, arxiv_id: str):
        pdf_path = request.data.get("pdf_path") or str(_default_pdf_path(arxiv_id))
        info = jobs.enqueue(
            _do_extract, arxiv_id, pdf_path,
            name=f"extract:{arxiv_id}",
        )
        return Response(
            {"job_id": info.job_id, "status": info.status},
            status=status.HTTP_202_ACCEPTED,
        )


class InterpretTriggerView(APIView):
    def post(self, request, arxiv_id: str):
        pdf_path = request.data.get("pdf_path") or str(_default_pdf_path(arxiv_id))
        info = jobs.enqueue(
            _do_interpret, arxiv_id, pdf_path,
            name=f"interpret:{arxiv_id}",
        )
        return Response(
            {"job_id": info.job_id, "status": info.status},
            status=status.HTTP_202_ACCEPTED,
        )


class RenderTriggerView(APIView):
    def post(self, request, arxiv_id: str):
        fmt = request.data.get("format", "excalidraw")
        if fmt not in ("excalidraw", "svg"):
            return Response(
                {"detail": "format must be excalidraw or svg"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        info = jobs.enqueue(
            _do_render, arxiv_id, fmt,
            name=f"render:{arxiv_id}:{fmt}",
        )
        return Response(
            {"job_id": info.job_id, "status": info.status},
            status=status.HTTP_202_ACCEPTED,
        )


class JobStatusView(APIView):
    def get(self, request, job_id: str):
        info = jobs.get_job(job_id)
        if info is None:
            raise Http404("job not found")
        return Response(JobSerializer(info.to_dict()).data)
