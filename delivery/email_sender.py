"""ft-007 + ft-012: SMTP sender（支持内嵌图 CID）."""
from __future__ import annotations

import logging
from email.mime.image import MIMEImage
from pathlib import Path

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
    inline_images: dict[str, Path] | None = None,  # cid → 文件路径
) -> bool:
    """发一封 multipart/related 邮件；html 内 <img src=cid:xxx> 引用 inline_images。"""
    recipients = [to] if isinstance(to, str) else list(to)
    sender = from_email or settings.DEFAULT_FROM_EMAIL

    try:
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
        # 切到 multipart/related 使 HTML alt + 内嵌图并存
        if inline_images:
            msg.mixed_subtype = "related"
            for cid, img_path in inline_images.items():
                if not img_path or not img_path.exists():
                    continue
                with img_path.open("rb") as f:
                    data = f.read()
                subtype = img_path.suffix.lstrip(".").lower() or "png"
                if subtype == "jpg":
                    subtype = "jpeg"
                image = MIMEImage(data, _subtype=subtype)
                image.add_header("Content-ID", f"<{cid}>")
                image.add_header("Content-Disposition", "inline", filename=img_path.name)
                msg.attach(image)
        sent = msg.send(fail_silently=False)
        return bool(sent)
    except Exception as exc:  # noqa: BLE001
        log.error("email send failed: %r", exc)
        return False
