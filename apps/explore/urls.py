"""Explore API URL routing."""

from __future__ import annotations

from django.urls import path

from apps.explore import views

urlpatterns = [
    path("profile/", views.profile_view, name="explore-profile"),
    path("activity/", views.activity_timeline, name="explore-activity"),
    path("gaps/", views.gaps_view, name="explore-gaps"),
    path("viewpoint/<str:viewpoint_id>/", views.viewpoint_state, name="explore-viewpoint"),
    path("events/", views.report_event, name="explore-events"),
    path("links/", views.claim_links, name="explore-links"),
    path("links/<int:link_id>/", views.claim_link_delete, name="explore-link-delete"),
    path("threads/", views.threads, name="explore-threads"),
    path("threads/<int:thread_id>/notes/", views.thread_add_note, name="explore-thread-note"),
    path("questions/", views.questions, name="explore-questions"),
    path("questions/<int:question_id>/", views.question_delete, name="explore-question-delete"),
]
