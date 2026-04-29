"""ft-034 P0-7: views package — split from 859-line ``apps/api/views.py``.

Per ft-034 P0-7 spec, ``apps/api/views.py`` was carved into 5 sub-modules
（papers / materials / claims / jobs / subscriptions）by domain. This module
re-exports every concrete view class so existing imports keep working:

    from apps.api.views import PaperListView, JobStatusView, ...

``urls.py`` does not need to change.
"""
from __future__ import annotations

from apps.api.views.claims import ClaimsView
from apps.api.views.health import HealthView
from apps.api.views.jobs import (
    ExtractTriggerView,
    InterpretTriggerView,
    JobStatusView,
    RenderTriggerView,
    _do_extract,
    _do_interpret,
    _do_render,
)
from apps.api.views.materials import FigureView, PaperMarkdownView
from apps.api.views.papers import (
    PaperBacklinkDetailView,
    PaperBacklinkView,
    PaperBriefRegenerateView,
    PaperBriefView,
    PaperCommentDetailView,
    PaperCommentListView,
    PaperDetailView,
    PaperListView,
    PaperPdfView,
    PaperStatusView,
    PaperTagDetailView,
    PaperTagListView,
    resolve_paper,
)

__all__ = [
    "HealthView",
    # papers
    "PaperListView",
    "PaperDetailView",
    "PaperStatusView",
    "PaperCommentListView",
    "PaperCommentDetailView",
    "PaperTagListView",
    "PaperTagDetailView",
    "PaperBacklinkView",
    "PaperBacklinkDetailView",
    "PaperPdfView",
    "PaperBriefView",
    "PaperBriefRegenerateView",
    "resolve_paper",
    # materials
    "PaperMarkdownView",
    "FigureView",
    # claims
    "ClaimsView",
    # jobs / triggers
    "ExtractTriggerView",
    "InterpretTriggerView",
    "RenderTriggerView",
    "JobStatusView",
]
