"""ft-022 + ft-028: DRF views.

ft-022 base: health + paper read views + extract/interpret/render trigger.
ft-028 adds: paper-key resolver + status / comment / tag / backlink endpoints,
plus query-param filtering on PaperListView and Paper-centric fields on
detail/list responses.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api import jobs
from apps.api.serializers import (
    BacklinkSerializer,
    ClaimSerializer,
    CommentSerializer,
    FigureSerializer,
    JobSerializer,
    PaperListItemSerializer,
    SectionSerializer,
    TableSerializer,
)
from apps.core import paths
from apps.extract.models import Equation, Figure, Section, Table
from apps.interpret.models import Claim
from apps.papers.models import (
    Paper,
    PaperBrief,
    PaperStatus,
    UserBacklink,
    UserComment,
    UserPaperStatus,
    UserTag,
    is_legal_transition,
)
from apps.papers.paths import resolve_pdf_path


# ---------------- ft-028 paper id resolver ----------------

PAPER_KEY_RE = re.compile(r"^[A-Z2-9]{8}$")


def resolve_paper(id_or_key: str) -> Paper:
    """ft-028 § "URL 解析": ``[A-Z2-9]{8}`` → key 查；否则 arxiv_id 查。

    404 走 ORM 而非 shape mismatch — DRF Http404 自动转 404 响应。
    """
    if PAPER_KEY_RE.match(id_or_key):
        return get_object_or_404(Paper, key=id_or_key)
    return get_object_or_404(Paper, arxiv_id=id_or_key)

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

_VALID_STATUS_FILTERS = {s.value for s in PaperStatus}


class PaperListView(APIView):
    """ft-028: list papers with optional ``status`` / ``tag`` / ``q`` filters.

    Iterates over Paper rows (FT-028 schema) and counts material/claim/comment
    rows per paper. Filters operate on Paper / UserTag / UserComment without
    PG-specific FTS — KISS until ft-030 lands FTS5 (CLAUDE.md long-term-form
    SQLite-friendly constraint).
    """

    def get(self, request):
        status_q = request.query_params.get("status", "").strip()
        tag_q = request.query_params.get("tag", "").strip()
        q = request.query_params.get("q", "").strip()

        papers = Paper.objects.all().order_by("created_at")

        if status_q:
            if status_q not in _VALID_STATUS_FILTERS:
                return Response(
                    {"detail": f"invalid status: {status_q}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            papers = papers.filter(user_status__status=status_q)

        if tag_q:
            papers = papers.filter(tags__tag=tag_q)

        if q:
            # icontains on Paper.title OR UserComment.text — duplicates removed
            # via .distinct() since the JOIN to user_comment may multiply rows.
            papers = papers.filter(
                Q(title__icontains=q) | Q(comments__text__icontains=q),
            ).distinct()

        # Materialize once; small N and we need multiple counts per paper.
        paper_list = list(papers)
        arxiv_ids = [p.arxiv_id for p in paper_list if p.arxiv_id]
        paper_ids = [p.id for p in paper_list]

        section_counts = dict(
            Section.objects.filter(paper_arxiv_id__in=arxiv_ids)
            .values_list("paper_arxiv_id")
            .annotate(n=Count("material_id"))
            .values_list("paper_arxiv_id", "n")
        )
        figure_counts = dict(
            Figure.objects.filter(paper_arxiv_id__in=arxiv_ids)
            .values_list("paper_arxiv_id")
            .annotate(n=Count("material_id"))
            .values_list("paper_arxiv_id", "n")
        )
        table_counts = dict(
            Table.objects.filter(paper_arxiv_id__in=arxiv_ids)
            .values_list("paper_arxiv_id")
            .annotate(n=Count("material_id"))
            .values_list("paper_arxiv_id", "n")
        )
        claim_counts = dict(
            Claim.objects.filter(paper_arxiv_id__in=arxiv_ids)
            .values_list("paper_arxiv_id")
            .annotate(n=Count("claim_id"))
            .values_list("paper_arxiv_id", "n")
        )
        comment_counts = dict(
            UserComment.objects.filter(paper_id__in=paper_ids)
            .values_list("paper_id")
            .annotate(n=Count("id"))
            .values_list("paper_id", "n")
        )
        # Tags grouped per paper in one query (avoid N+1).
        tags_by_paper: dict[int, list[str]] = {}
        for paper_id, tag in UserTag.objects.filter(paper_id__in=paper_ids).values_list(
            "paper_id", "tag",
        ):
            tags_by_paper.setdefault(paper_id, []).append(tag)
        statuses = {
            paper_id: status_value
            for paper_id, status_value in UserPaperStatus.objects.filter(
                paper_id__in=paper_ids,
            ).values_list("paper_id", "status")
        }

        # ft-033: brief 字段（list 仅取 tldr/keywords 短版，避 N+1 用一次 in 查）
        briefs_by_paper = {
            b.paper_id: b
            for b in PaperBrief.objects.filter(paper_id__in=paper_ids)
        }

        items = []
        for p in paper_list:
            aid = p.arxiv_id or ""
            brief = briefs_by_paper.get(p.id)
            items.append({
                "arxiv_id": p.arxiv_id,
                "paper_key": p.key,
                "title": p.title or aid,
                "status": statuses.get(p.id, PaperStatus.NEW.value),
                "tags": tags_by_paper.get(p.id, []),
                "n_comments": comment_counts.get(p.id, 0),
                "n_sections": section_counts.get(aid, 0),
                "n_figures": figure_counts.get(aid, 0),
                "n_tables": table_counts.get(aid, 0),
                "n_claims": claim_counts.get(aid, 0),
                # ft-033 brief short fields (None when absent)
                "tldr_zh": brief.tldr_zh if brief else "",
                "keywords": list(brief.keywords)[:3] if brief else [],
                "has_brief": brief is not None and bool(brief.abstract_zh),
                "abstract_en": p.abstract or "",
            })
        return Response(PaperListItemSerializer(items, many=True).data)


class PaperDetailView(APIView):
    """ft-022 base + ft-028 fields: sections + figures + tables + claims.

    ``arxiv_id`` URL param now accepts an 8-char paper_key as well — see
    :func:`resolve_paper`. To keep zero-regression on the legacy
    ``no extract / interpret data for ...`` 404 (covered by tests_views
    ``test_paper_detail_404``), unknown id_or_key still returns 404 — the
    response just goes through ``Paper`` lookup if it matches a known paper,
    otherwise falls through to the legacy "no data" 404.
    """

    def get(self, request, arxiv_id: str):
        # Try to resolve to a Paper row (ft-028 schema). If neither key nor
        # arxiv_id matches, fall back to the legacy arxiv_id-string flow so
        # papers extracted before ft-028 (or detail probes pre-Paper-creation)
        # still produce a 404 with the same shape.
        paper: Paper | None = None
        if PAPER_KEY_RE.match(arxiv_id):
            paper = Paper.objects.filter(key=arxiv_id).first()
        else:
            paper = Paper.objects.filter(arxiv_id=arxiv_id).first()

        # Legacy material lookups still key off the string column. When we did
        # resolve a Paper, prefer its arxiv_id (the URL might have been a key).
        material_arxiv_id = paper.arxiv_id if (paper and paper.arxiv_id) else arxiv_id

        sections = Section.objects.filter(
            paper_arxiv_id=material_arxiv_id,
        ).order_by("seq")
        figures = Figure.objects.filter(
            paper_arxiv_id=material_arxiv_id,
        ).order_by("seq")
        tables = Table.objects.filter(
            paper_arxiv_id=material_arxiv_id,
        ).order_by("seq")
        equations_qs = Equation.objects.filter(
            paper_arxiv_id=material_arxiv_id,
        ).order_by("seq")
        claims = (
            Claim.objects.filter(paper_arxiv_id=material_arxiv_id)
            .prefetch_related("evidences", "counter_signals")
            .order_by("claim_id")
        )

        if not (sections or figures or tables or claims):
            return Response(
                {"detail": f"no extract / interpret data for {arxiv_id}"},
                status=status.HTTP_404_NOT_FOUND,
            )

        data = {
            "arxiv_id": material_arxiv_id,
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
        if paper is not None:
            data["paper_key"] = paper.key
            data["title"] = paper.title or (paper.arxiv_id or "")
            status_row = UserPaperStatus.objects.filter(paper=paper).first()
            data["status"] = (
                status_row.status if status_row else PaperStatus.NEW.value
            )
            data["tags"] = list(
                paper.tags.order_by("created_at").values_list("tag", flat=True),
            )
            data["n_comments"] = paper.comments.count()
            # ft-029: PDF 可用性 + 访问 URL（前端用 paper_key 拼）
            data["has_pdf"] = resolve_pdf_path(paper) is not None
            data["pdf_url"] = f"/api/papers/{paper.key}/pdf/"
            # ft-033: brief nested（None 表示未生成）+ abstract 原文
            data["abstract"] = paper.abstract or ""
            brief_row = PaperBrief.objects.filter(paper=paper).first()
            data["brief"] = _serialize_brief(brief_row) if brief_row else None
        else:
            # 无 Paper 行（legacy material-only 路径），保底 has_pdf=False
            data["has_pdf"] = False
            data["pdf_url"] = None
            data["abstract"] = ""
            data["brief"] = None
        return Response(data)


def _serialize_brief(b: "PaperBrief") -> dict:
    return {
        "abstract_zh": b.abstract_zh,
        "keywords": list(b.keywords or []),
        "method_summary_zh": b.method_summary_zh,
        "key_innovation": list(b.key_innovation or []),
        "limitations": list(b.limitations or []),
        "for_you": b.for_you,
        "tldr_zh": b.tldr_zh,
        "perspective_used": b.perspective_used,
        "model_used": b.model_used,
        "generated_at": b.generated_at.isoformat() if b.generated_at else None,
    }


class PaperBriefView(APIView):
    """ft-033: ``GET /api/papers/<id>/brief/`` + ``POST .../brief/regenerate/``.

    GET 返回当前 brief（无则 404）；POST 同步触发 LLM 跑老 pipeline 生成。
    LLM 失败仍落空行（abstract_zh="")，前端按 ``has_brief`` 区分。
    """

    def get(self, request, id_or_key: str):
        paper = resolve_paper(id_or_key)
        b = PaperBrief.objects.filter(paper=paper).first()
        if b is None:
            return Response({"detail": "no brief"}, status=status.HTTP_404_NOT_FOUND)
        return Response(_serialize_brief(b))


class PaperBriefRegenerateView(APIView):
    """``POST /api/papers/<id>/brief/regenerate/`` — 同步阻塞触发生成."""

    def post(self, request, id_or_key: str):
        paper = resolve_paper(id_or_key)
        # 惰性 import 避开 settings/migration 阶段拉 LLM client
        from apps.papers.brief_generator import generate_brief

        try:
            brief = generate_brief(paper, regenerate=True)
        except Exception as exc:  # noqa: BLE001
            logging.getLogger(__name__).warning(
                "regenerate brief failed for %s: %r", paper.key, exc,
            )
            return Response(
                {"detail": f"generation failed: {exc}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response(_serialize_brief(brief))


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


# ====================================================================
# ft-028: user_* layer endpoints (status / comment / tag / backlink)
# ====================================================================


class PaperStatusView(APIView):
    """``POST /api/papers/<id>/status/`` body ``{status}`` → write user_status.

    Validates the destination against ``is_legal_transition()``; illegal jumps
    return 400 with the offending pair so the UI can surface a toast.
    """

    def post(self, request, id_or_key: str):
        paper = resolve_paper(id_or_key)
        new_status = (request.data or {}).get("status", "").strip()
        if not new_status:
            return Response(
                {"detail": "status is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if new_status not in _VALID_STATUS_FILTERS:
            return Response(
                {"detail": f"invalid status: {new_status}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        row, _created = UserPaperStatus.objects.get_or_create(
            paper=paper, defaults={"status": PaperStatus.NEW.value},
        )
        if not is_legal_transition(row.status, new_status):
            return Response(
                {
                    "detail": (
                        f"illegal status transition: "
                        f"{row.status} → {new_status}"
                    ),
                    "from": row.status,
                    "to": new_status,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        row.status = new_status
        row.save(update_fields=["status", "updated_at"])
        return Response({"status": row.status, "paper_key": paper.key})


def _serialize_comment(c: UserComment) -> dict:
    return {
        "id": c.id,
        "text": c.text,
        "created_at": c.created_at,
        "hidden": c.hidden,
    }


class PaperCommentListView(APIView):
    """``GET`` (chronological) + ``POST`` (append-only) at ``/api/papers/<id>/comments/``.

    GET respects optional ``?hidden=true`` to include hidden rows; default
    excludes them so the UI doesn't accidentally surface soft-deleted notes.
    """

    def get(self, request, id_or_key: str):
        paper = resolve_paper(id_or_key)
        include_hidden = request.query_params.get("hidden", "").lower() in {
            "1", "true", "yes",
        }
        qs = paper.comments.all().order_by("created_at")
        if not include_hidden:
            qs = qs.filter(hidden=False)
        items = [_serialize_comment(c) for c in qs]
        return Response(CommentSerializer(items, many=True).data)

    def post(self, request, id_or_key: str):
        paper = resolve_paper(id_or_key)
        text = (request.data or {}).get("text", "")
        if not isinstance(text, str) or not text.strip():
            return Response(
                {"detail": "text is required and must be a non-empty string"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        comment = UserComment.objects.create(paper=paper, text=text)
        return Response(
            CommentSerializer(_serialize_comment(comment)).data,
            status=status.HTTP_201_CREATED,
        )


class PaperCommentDetailView(APIView):
    """``PATCH /api/papers/<id>/comments/<cid>/`` — only ``hidden`` is mutable.

    Per ft-028 § "comment append-only"，``text`` 不可改、不可删；任何带其它键
    的 PATCH 直接 400。
    """

    _ALLOWED_FIELDS = {"hidden"}

    def patch(self, request, id_or_key: str, cid: int):
        paper = resolve_paper(id_or_key)
        comment = get_object_or_404(UserComment, pk=cid, paper=paper)
        data = request.data or {}
        bad = set(data.keys()) - self._ALLOWED_FIELDS
        if bad:
            return Response(
                {"detail": f"only 'hidden' is mutable; got extra keys: {sorted(bad)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if "hidden" not in data:
            return Response(
                {"detail": "'hidden' field is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        hidden = data["hidden"]
        if not isinstance(hidden, bool):
            return Response(
                {"detail": "'hidden' must be boolean"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        comment.hidden = hidden
        comment.save(update_fields=["hidden"])
        return Response(CommentSerializer(_serialize_comment(comment)).data)


class PaperTagListView(APIView):
    """``GET`` (list of strings) + ``POST`` (add) at ``/api/papers/<id>/tags/``."""

    def get(self, request, id_or_key: str):
        paper = resolve_paper(id_or_key)
        tags = list(
            paper.tags.order_by("created_at").values_list("tag", flat=True),
        )
        return Response(tags)

    def post(self, request, id_or_key: str):
        paper = resolve_paper(id_or_key)
        tag = (request.data or {}).get("tag", "")
        if not isinstance(tag, str) or not tag.strip():
            return Response(
                {"detail": "tag is required and must be a non-empty string"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        tag = tag.strip()
        if len(tag) > 64:
            return Response(
                {"detail": "tag must be ≤ 64 chars"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            with transaction.atomic():
                UserTag.objects.create(paper=paper, tag=tag)
        except IntegrityError:
            # Idempotent: already-present tag → 200 with no-op semantics.
            # `atomic()` 块隔离 IntegrityError，避免把外层 transaction
            # 标记成 broken（pytest 测试上下文里 ATOMIC_REQUESTS / 测试自带
            # transaction 都会因此 TransactionManagementError）。
            return Response({"tag": tag, "duplicate": True})
        return Response({"tag": tag}, status=status.HTTP_201_CREATED)


class PaperTagDetailView(APIView):
    """``DELETE /api/papers/<id>/tags/<tag>/`` — remove a single tag."""

    def delete(self, request, id_or_key: str, tag: str):
        paper = resolve_paper(id_or_key)
        deleted, _ = UserTag.objects.filter(paper=paper, tag=tag).delete()
        if not deleted:
            raise Http404(f"tag {tag!r} not found on paper {paper.key}")
        return Response(status=status.HTTP_204_NO_CONTENT)


def _serialize_backlink_out(bl: UserBacklink) -> dict:
    return {
        "id": bl.id,
        "dst_key": bl.dst.key,
        "dst_title": bl.dst.title or (bl.dst.arxiv_id or ""),
        "relation": bl.relation,
        "note": bl.note,
        "created_at": bl.created_at,
    }


def _serialize_backlink_in(bl: UserBacklink) -> dict:
    return {
        "id": bl.id,
        "src_key": bl.src.key,
        "src_title": bl.src.title or (bl.src.arxiv_id or ""),
        "relation": bl.relation,
        "note": bl.note,
        "created_at": bl.created_at,
    }


class PaperBacklinkView(APIView):
    """``GET`` ({outgoing,incoming}) + ``POST`` ({dst,relation?,note?})
    at ``/api/papers/<id>/backlinks/``.
    """

    def get(self, request, id_or_key: str):
        paper = resolve_paper(id_or_key)
        outgoing = [
            _serialize_backlink_out(bl)
            for bl in paper.backlinks_out.select_related("dst").order_by("created_at")
        ]
        incoming = [
            _serialize_backlink_in(bl)
            for bl in paper.backlinks_in.select_related("src").order_by("created_at")
        ]
        return Response(
            BacklinkSerializer({"outgoing": outgoing, "incoming": incoming}).data,
        )

    def post(self, request, id_or_key: str):
        paper = resolve_paper(id_or_key)
        data = request.data or {}
        dst_ref = data.get("dst_key") or data.get("dst")
        if not isinstance(dst_ref, str) or not dst_ref.strip():
            return Response(
                {"detail": "dst (or dst_key) is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Resolve the destination paper the same way ``id_or_key`` is resolved.
        try:
            dst_paper = resolve_paper(dst_ref.strip())
        except Http404:
            return Response(
                {"detail": f"destination paper not found: {dst_ref!r}"},
                status=status.HTTP_404_NOT_FOUND,
            )
        if dst_paper.id == paper.id:
            return Response(
                {"detail": "cannot link a paper to itself"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        relation = data.get("relation", "") or ""
        note = data.get("note", "") or ""
        if not isinstance(relation, str) or not isinstance(note, str):
            return Response(
                {"detail": "relation and note must be strings"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        bl, created = UserBacklink.objects.get_or_create(
            src=paper, dst=dst_paper, relation=relation,
            defaults={"note": note},
        )
        if not created and note and bl.note != note:
            # Update note if caller supplied a non-empty new value.
            bl.note = note
            bl.save(update_fields=["note"])
        return Response(
            _serialize_backlink_out(bl),
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class PaperPdfView(APIView):
    """ft-029: ``GET / HEAD /api/papers/<id_or_key>/pdf/``.

    GET 返回 ``application/pdf`` 全文（无 Range 支持，论文 < 10MB 全量可接受；
    Range 留 ft-030 优化）。HEAD 仅探测 200/404（前端 ``useHasPdf`` 用）。
    解析顺序见 :func:`resolve_pdf_path`。
    """

    def get(self, request, id_or_key: str):
        paper = resolve_paper(id_or_key)
        path = resolve_pdf_path(paper)
        if path is None:
            return Response(
                {"detail": "pdf not available"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return FileResponse(open(path, "rb"), content_type="application/pdf")

    def head(self, request, id_or_key: str):
        paper = resolve_paper(id_or_key)
        path = resolve_pdf_path(paper)
        return HttpResponse(status=200 if path else 404)


class PaperBacklinkDetailView(APIView):
    """``DELETE /api/papers/<id>/backlinks/<bid>/``."""

    def delete(self, request, id_or_key: str, bid: int):
        paper = resolve_paper(id_or_key)
        # Allow either side (out or in) to delete its own edge.
        bl = (
            UserBacklink.objects.filter(pk=bid)
            .filter(Q(src=paper) | Q(dst=paper))
            .first()
        )
        if bl is None:
            raise Http404(f"backlink {bid} not found for paper {paper.key}")
        bl.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
