"""ft-022: DRF URL routes — mounted at /api/."""
from __future__ import annotations

from django.urls import path

from apps.api.views import (
    ClaimsView,
    ExtractTriggerView,
    FigureView,
    HealthView,
    InterpretTriggerView,
    JobStatusView,
    PaperDetailView,
    PaperListView,
    PaperMarkdownView,
    RenderTriggerView,
)

urlpatterns = [
    path("health/", HealthView.as_view(), name="api-health"),
    path("papers/", PaperListView.as_view(), name="api-paper-list"),
    path("papers/<str:arxiv_id>/", PaperDetailView.as_view(), name="api-paper-detail"),
    path(
        "papers/<str:arxiv_id>/markdown/",
        PaperMarkdownView.as_view(),
        name="api-paper-markdown",
    ),
    path(
        "papers/<str:arxiv_id>/figure/<int:seq>.png",
        FigureView.as_view(),
        name="api-paper-figure",
    ),
    path(
        "papers/<str:arxiv_id>/claims/",
        ClaimsView.as_view(),
        name="api-paper-claims",
    ),
    path(
        "papers/<str:arxiv_id>/extract/",
        ExtractTriggerView.as_view(),
        name="api-paper-extract",
    ),
    path(
        "papers/<str:arxiv_id>/interpret/",
        InterpretTriggerView.as_view(),
        name="api-paper-interpret",
    ),
    path(
        "papers/<str:arxiv_id>/render/",
        RenderTriggerView.as_view(),
        name="api-paper-render",
    ),
    path("jobs/<str:job_id>/", JobStatusView.as_view(), name="api-job-status"),
]
