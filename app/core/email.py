from email.message import EmailMessage
import logging

import aiosmtplib
import certifi

from app.core.config import (
    SMTP_FROM,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_STARTTLS,
    SMTP_USER,
)

logger = logging.getLogger(__name__)


async def send_email(
    to_address: str,
    subject: str,
    text: str,
    html: str | None = None,
) -> bool:
    if not SMTP_HOST or not SMTP_FROM:
        logger.warning("SMTP is not configured; skipped email %s", subject)
        return False

    message = EmailMessage()
    message["From"] = SMTP_FROM
    message["To"] = to_address
    message["Subject"] = subject
    message.set_content(text)
    if html:
        message.add_alternative(html, subtype="html")

    try:
        await aiosmtplib.send(
            message,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            username=SMTP_USER or None,
            password=SMTP_PASSWORD or None,
            start_tls=SMTP_STARTTLS,
            cert_bundle=certifi.where(),
        )
    except (OSError, aiosmtplib.SMTPException):
        logger.exception("Failed to send email: %s", subject)
        return False
    return True
