"""
Delivery layer.
send_email(subject, html_body) → Gmail via SMTP + App Password
send_gchat(text)               → Google Chat incoming webhook
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

from config import (
    GMAIL_USER, GMAIL_APP_PASSWORD,
    GMAIL_TO, GMAIL_CC,
    GCHAT_WEBHOOK,
)

log = logging.getLogger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def send_email(subject: str, html_body: str) -> None:
    """Send a full HTML report via Gmail SMTP using an App Password."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_USER
    msg["To"]      = ", ".join(GMAIL_TO)
    if GMAIL_CC:
        msg["Cc"] = ", ".join(GMAIL_CC)

    msg.attach(MIMEText(html_body, "html", "utf-8"))

    all_recipients = GMAIL_TO + GMAIL_CC
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, all_recipients, msg.as_string())
        log.info("Email sent to %s", all_recipients)
    except Exception:
        log.exception("Failed to send email")
        raise


def send_gchat(text: str) -> None:
    """Post a plain-text message to a Google Chat space via incoming webhook."""
    payload = {"text": text}
    try:
        resp = requests.post(GCHAT_WEBHOOK, json=payload, timeout=15)
        resp.raise_for_status()
        log.info("Google Chat message sent (status %d)", resp.status_code)
    except Exception:
        log.exception("Failed to send Google Chat message")
        raise
