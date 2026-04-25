"""Backwards-compatible thin wrapper. New code should use the EmailAdapter
via delivery.base.get('email')."""
from __future__ import annotations

from pathlib import Path

from delivery.adapters.email import _send_smtp


def send(
    subject: str,
    html_body: str,
    plain_body: str,
    to: str | list[str],
    from_email: str | None = None,
    inline_images: dict[str, Path] | None = None,
) -> bool:
    return _send_smtp(
        subject=subject, html_body=html_body, plain_body=plain_body,
        to=to, from_email=from_email, inline_images=inline_images,
    )
