"""ft-007: SMTP sender."""
from __future__ import annotations

import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from django.conf import settings
from django.core.mail import get_connection
from django.core.mail.message import EmailMultiAlternatives

log = logging.getLogger(__name__)


def send(
    subject: str,
    html_body: str,
    plain_body: str,
    to: str | list[str],
    from_email: str | None = None,
) -> bool:
    """发一封多部分邮件。返回 True/False。"""
    recipients = [to] if isinstance(to, str) else list(to)
    sender = from_email or settings.DEFAULT_FROM_EMAIL

    try:
        # Django 的 EmailBackend 原生支持 use_ssl/use_tls，读 settings
        connection = get_connection(
            host=settings.EMAIL_HOST,
            port=settings.EMAIL_PORT,
            username=settings.EMAIL_HOST_USER,
            password=settings.EMAIL_HOST_PASSWORD,
            use_tls=settings.EMAIL_USE_TLS,
            use_ssl=settings.EMAIL_USE_SSL,
        )
        msg = EmailMultiAlternatives(
            subject=subject,
            body=plain_body,
            from_email=sender,
            to=recipients,
            connection=connection,
        )
        msg.attach_alternative(html_body, "text/html")
        sent = msg.send(fail_silently=False)
        return bool(sent)
    except Exception as exc:  # noqa: BLE001
        log.error("email send failed: %r", exc)
        return False
