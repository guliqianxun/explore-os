"""ft-040 follow-up: SMTP 连通性自检。

用法::

    uv run python manage.py test_email                     # 用 EMAIL_TO_DEFAULT
    uv run python manage.py test_email --to user@x.com    # 显式收件人

成功 → 服务器 250 OK；失败 → 异常信息（auth / network / TLS）。
"""
from __future__ import annotations

from datetime import datetime

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Send a tiny SMTP test email."

    def add_arguments(self, parser):
        parser.add_argument("--to", default="")

    def handle(self, *args, to: str, **kw):
        recipient = (to or settings.EMAIL_TO_DEFAULT or "").strip()
        if not recipient:
            self.stderr.write("no recipient: pass --to or set EMAIL_TO_DEFAULT")
            return

        host = settings.EMAIL_HOST
        port = settings.EMAIL_PORT
        user = settings.EMAIL_HOST_USER
        if not host:
            self.stderr.write("EMAIL_HOST is empty; SMTP not configured")
            return

        self.stdout.write(
            f"sending test mail: host={host}:{port}  user={user}  -> {recipient}",
        )

        ts = datetime.now().isoformat(timespec="seconds")
        subject = f"[explore-os] SMTP self-check {ts}"
        body = (
            f"This is an SMTP connectivity self-check from explore-os.\n\n"
            f"timestamp : {ts}\n"
            f"host      : {host}:{port}\n"
            f"tls/ssl   : tls={settings.EMAIL_USE_TLS} ssl={settings.EMAIL_USE_SSL}\n"
            f"from      : {settings.DEFAULT_FROM_EMAIL}\n"
        )
        try:
            msg = EmailMultiAlternatives(
                subject=subject,
                body=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[recipient],
            )
            n = msg.send()
            self.stdout.write(self.style.SUCCESS(f"OK  send() returned {n}"))
        except Exception as exc:  # noqa: BLE001
            self.stderr.write(self.style.ERROR(f"FAIL  {type(exc).__name__}: {exc}"))
            raise
