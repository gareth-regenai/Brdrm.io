"""Email delivery: SMTP in staging and production, console or memory in development and tests.
The long-term provider is open; see OPEN.md."""

import smtplib
import ssl
import sys
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from typing import Protocol

from boardroom.config import get_settings
from boardroom.logs import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    body: str


class Mailer(Protocol):
    def send(self, email: Email) -> None: ...


class ConsoleMailer:
    """Development only: prints the email so the invite link can be followed locally.
    Writes to stdout, not the structured log, so links never reach log storage."""

    def send(self, email: Email) -> None:
        sys.stdout.write(f"\n--- email to {email.to}\n{email.subject}\n\n{email.body}\n---\n")
        sys.stdout.flush()


class MemoryMailer:
    """Tests read sent emails from here."""

    def __init__(self) -> None:
        self.sent: list[Email] = []

    def send(self, email: Email) -> None:
        self.sent.append(email)


class DisabledMailer:
    """No email provider yet. Records that an email was due, never its content."""

    def send(self, email: Email) -> None:
        log.warning("email_not_sent", reason="no email provider configured")


class SmtpMailer:
    """Sends through any SMTP server. A failure raises, so the event is retried."""

    def send(self, email: Email) -> None:
        s = get_settings()
        message = EmailMessage()
        message["From"] = formataddr((s.smtp_from_name, s.smtp_from))
        message["To"] = email.to
        message["Subject"] = email.subject
        message["Message-ID"] = make_msgid(domain=s.smtp_from.rsplit("@", 1)[-1])
        message.set_content(email.body)
        context = ssl.create_default_context()
        if s.smtp_security == "ssl":
            server: smtplib.SMTP = smtplib.SMTP_SSL(
                s.smtp_host, s.smtp_port, timeout=30, context=context
            )
        else:
            server = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=30)
        with server:
            if s.smtp_security == "starttls":
                server.starttls(context=context)
            if s.smtp_username and s.smtp_password:
                server.login(s.smtp_username, s.smtp_password)
            server.send_message(message)
        # The recipient's domain only: addresses and links stay out of the logs.
        log.info("email_sent", to_domain=email.to.rsplit("@", 1)[-1])


_memory = MemoryMailer()


def get_mailer() -> Mailer:
    mailer = get_settings().mailer
    if mailer == "memory":
        return _memory
    if mailer == "disabled":
        return DisabledMailer()
    if mailer == "smtp":
        return SmtpMailer()
    return ConsoleMailer()


def memory_mailer() -> MemoryMailer:
    return _memory
