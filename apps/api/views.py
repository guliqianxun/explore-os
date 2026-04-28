"""ft-022: DRF views — health + paper read views + extract/interpret/render trigger."""
from __future__ import annotations

import logging
import re
from pathlib import Path

from django.db.models import Count
from django.http import FileResponse, Http404, HttpResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api import jobs
from apps.api.serializers import (
    ClaimSerializer,
    FigureSerializer,
    JobSerializer,
    PaperListItemSerializer,
    SectionSerializer,
    TableSerializer,
)
from apps.core import paths
from apps.extract.models import Equation, Figure, Section, Table
from apps.interpret.models import Claim

log = logging.getLogger(__name__)


# ---------------- helpers ----------------

def _default_pdf_path(arxiv_id: str) -> Path:
    """与 4 个 CLI 默认 PDF 位置保持一致：``<DATA_DIR>/media/pdf/<arxiv_id>.pdf``。"""
    return paths.pdf_legacy_dir() / f"{arxiv_id}.pdf"


# ---------------- health ----------------

class HealthView(APIView):
    """sidecar 健康检查（Electron 启动用）。"""

    def get(self, request):
        from apps.core.scheduler import get_scheduler
        s = get_scheduler()
        return Response({
            "status": "ok",
            "scheduler_running": s.running,
            "data_dir": str(paths.data_dir()),
        })


# ---------------- papers ----------------

class PaperListView(APIView):
    """列出所有已抽取 paper（distinct from extract_sections）。"""

    def get(self, request):
        # distinct paper_arxiv_id + counts via aggregations
        section_counts = dict(
            Section.objects.values_list("paper_arxiv_id")
            .annotate(n=Count("material_id"))
            .values_list("paper_arxiv_id", "n")
        )
        figure_counts = dict(
            Figure.objects.values_list("paper_arxiv_id")
            .annotate(n=Count("material_id"))
            .values_list("paper_arxiv_id", "n")
        )
        table_counts = dict(
            Table.objects.values_list("paper_arxiv_id")
            .annotate(n=Count("material_id"))
            .values_list("paper_arxiv_id", "n")
        )
        claim_counts = dict(
            Claim.objects.values_list("paper_arxiv_id")
            .annotate(n=Count("claim_id"))
            .values_list("paper_arxiv_id", "n")
        )
        all_ids = (
            set(section_counts) | set(figure_counts)
            | set(table_counts) | set(claim_counts)
        )
        items = [
            {
                "arxiv_id": aid,
                "n_sections": section_counts.get(aid, 0),
                "n_figures": figure_counts.get(aid, 0),
                "n_tables": table_counts.get(aid, 0),
                "n_claims": claim_counts.get(aid, 0),
            }
            for aid in sorted(all_ids)
        ]
        return Response(PaperListItemSerializer(items, many=True).data)


class PaperDetailView(APIView):
    """单篇精读视图：sections + figures + tables + claims。"""

    def get(self, request, arxiv_id: str):
        sections = Section.objects.filter(paper_arxiv_id=arxiv_id).order_by("seq")
        figures = Figure.objects.filter(paper_arxiv_id=arxiv_id).order_by("seq")
        tables = Table.objects.filter(paper_arxiv_id=arxiv_id).order_by("seq")
        equations_qs = Equation.objects.filter(paper_arxiv_id=arxiv_id).order_by("seq")
        claims = (
            Claim.objects.filter(paper_arxiv_id=arxiv_id)
            .prefetch_related("evidences", "counter_signals")
            .order_by("claim_id")
        )
        data = {
            "arxiv_id": arxiv_id,
            "sections": SectionSerializer(sections, many=True).data,
            "figures": FigureSerializer(figures, many=True).data,
            "tables": TableSerializer(tables, many=True).data,
            "equations": [
                {
                    "material_id": e.material_id,
                    "seq": e.seq,
                    "page": e.page,
                    "latex_or_text": e.latex_or_text,
                    "inline_or_display": e.inline_or_display,
                }
                for e in equations_qs
            ],
            "claims": ClaimSerializer(claims, many=True).data,
        }
        if not (sections or figures or tables or claims):
            return Response(
                {"detail": f"no extract / interpret data for {arxiv_id}"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(data)


_TOKEN_RE = re.compile(r"[a-zA-Z]{3,}")


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text or "")}


def _caption_coverage(caption: str, section_text: str) -> float:
    """How many of the caption's content words also appear in ``section_text``.

    Asymmetric ratio (caption-side), because captions are short queries and
    sections are long docs — Jaccard over union under-rates good matches.
    Range [0, 1]; 0 when either side has no content tokens.
    """
    cap = _tokens(caption)
    if not cap:
        return 0.0
    sec = _tokens(section_text)
    if not sec:
        return 0.0
    return len(cap & sec) / len(cap)


# Minimum caption-coverage for a figure to attach to a section.
# 0.30 ≈ "at least 30% of caption content words appear in the section";
# below this the match is mostly noise → drop figure into the trailing
# Figures bucket so it still renders.
_FIGURE_MATCH_THRESHOLD = 0.30


def _emit_figure_md(lines: list[str], fig: Figure) -> None:
    """Append a single figure as markdown image + italic caption.

    Path stays relative ``figures/<seq>.png`` — the frontend MarkdownView
    rewrites it to the API URL via regex.
    """
    label = fig.fig_label or f"Figure {fig.seq}"
    cap = (fig.caption or "").strip()
    alt = f"{label}. {cap}" if cap else label
    lines.append("")
    lines.append(f"![{alt}](figures/{fig.seq}.png)")
    if cap:
        lines.append(f"*{cap}*")


class PaperMarkdownView(APIView):
    """Markdown view: sections (with figures interleaved by caption similarity) + claims.

    Figures are matched to the section whose ``raw_text`` shares the most
    content words with the figure's ``caption`` (caption-side coverage,
    threshold 0.30). Unmatched figures fall into a trailing ``## Figures``
    bucket so they still render.
    """

    def get(self, request, arxiv_id: str):
        sections = list(Section.objects.filter(paper_arxiv_id=arxiv_id).order_by("seq"))
        figures = list(Figure.objects.filter(paper_arxiv_id=arxiv_id).order_by("seq"))
        claims = list(Claim.objects.filter(paper_arxiv_id=arxiv_id).order_by("claim_id"))
        if not sections and not figures and not claims:
            return Response(
                {"detail": f"no extract / interpret data for {arxiv_id}"},
                status=status.HTTP_404_NOT_FOUND,
            )

        figs_by_section: dict[str, list[Figure]] = {}
        orphans: list[Figure] = []
        for fig in figures:
            best_section: Section | None = None
            best_score = 0.0
            for s in sections:
                # Match caption against title + body, so legacy extractions
                # without raw_text still get partial signal from the heading.
                hay = f"{s.path}\n{s.raw_text}"
                score = _caption_coverage(fig.caption, hay)
                if score > best_score:
                    best_section, best_score = s, score
            if best_section is not None and best_score >= _FIGURE_MATCH_THRESHOLD:
                figs_by_section.setdefault(best_section.material_id, []).append(fig)
            else:
                orphans.append(fig)

        lines = [f"# {arxiv_id}", ""]
        if sections:
            lines.append("## Sections")
            for s in sections:
                hdr = "#" * max(1, min(6, (s.level or 1) + 1))
                lines.append(f"{hdr} {s.path}")
                if s.raw_text:
                    lines.append(s.raw_text)
                for fig in figs_by_section.get(s.material_id, []):
                    _emit_figure_md(lines, fig)
                lines.append("")
        if orphans:
            lines.append("## Figures")
            for fig in orphans:
                _emit_figure_md(lines, fig)
            lines.append("")
        if claims:
            lines.append("## Claims")
            for c in claims:
                lines.append(f"- **[{c.claim_type}]** {c.text}")
        body = "\n".join(lines)
        return HttpResponse(body, content_type="text/markdown; charset=utf-8")


class FigureView(APIView):
    """返回 figure PNG 二进制。路径通过 Figure.image_path 取。"""

    def get(self, request, arxiv_id: str, seq: int):
        fig = Figure.objects.filter(paper_arxiv_id=arxiv_id, seq=seq).first()
        if fig is None or not fig.image_path:
            raise Http404("figure not found")
        p = Path(fig.image_path)
        if not p.exists():
            raise Http404("figure file missing on disk")
        return FileResponse(p.open("rb"), content_type="image/png")


class ClaimsView(APIView):
    def get(self, request, arxiv_id: str):
        claims = (
            Claim.objects.filter(paper_arxiv_id=arxiv_id)
            .prefetch_related("evidences", "counter_signals")
            .order_by("claim_id")
        )
        return Response(ClaimSerializer(claims, many=True).data)


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
