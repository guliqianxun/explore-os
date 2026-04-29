"""Material views: paper-level markdown + figure PNG serving.

ft-022 base. PaperMarkdownView interleaves figures into sections by caption-
similarity (caption-side coverage with 0.30 threshold)。
"""
from __future__ import annotations

import re
from pathlib import Path

from django.http import FileResponse, Http404, HttpResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.extract.models import Figure, Section
from apps.interpret.models import Claim


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
