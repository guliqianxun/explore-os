from __future__ import annotations

from django.apps import AppConfig


class ExploreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.explore"
    label = "explore"
    verbose_name = "Explore"

    def ready(self):
        import apps.explore.signals  # noqa: F401
