"""Global pytest config.

Tests that don't explicitly override ``SUBSCRIPTIONS_YAML`` should see a
non-existent path so ``_resolve_perspective`` falls back to "researcher"
(prevents real-repo ``subscriptions.yaml`` from leaking into perspective
fixtures across the suite).
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_subscriptions_yaml(settings, tmp_path_factory):
    """Default to a unique non-existent yaml unless test overrides."""
    settings.SUBSCRIPTIONS_YAML = str(
        tmp_path_factory.mktemp("subs") / "missing.yaml",
    )
    yield
