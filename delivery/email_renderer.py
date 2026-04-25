"""Backwards-compatible re-exports. New code should import from delivery.base
+ delivery.adapters.email instead.
"""
from delivery.adapters.email import render_html  # noqa: F401
from delivery.base import RenderedDeep, RenderedSkim  # noqa: F401
