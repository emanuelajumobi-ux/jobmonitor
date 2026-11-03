"""Versand des Berichts an DICH selbst (nie an Firmen). Zugangsdaten nur aus Umgebungsvariablen."""
from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

import markdown

log = logging.getLogger(__name__)
REQUIRED = ["SMTP_USER", "SMTP_PASSWORD", "MAIL_TO"]


def mail_configured() -> bool:
    return all(os.environ.get(k) for k in REQUIRED)


def send_report(subject: str, body_md: str) -> None:
    host = os.environ.get("SMTP_HOST") or "smtp.mail.me.com"   # iCloud-Standard
    port = int(os.environ.get("SMTP_PORT") or "587")
    user = os.environ["SMTP_USER"]
    sender = os.environ.get("MAIL_FROM") or user
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = os.environ["MAIL_TO"]
    msg.set_content(body_md)
    msg.add_alternative(markdown.markdown(body_md), subtype="html")
    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(user, os.environ["SMTP_PASSWORD"])
        smtp.send_message(msg)
    log.info("Bericht per Mail verschickt an %s", msg["To"])
