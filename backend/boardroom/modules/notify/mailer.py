"""Email delivery. The provider is chosen with the email provider decision; see OPEN.md."""

import sys
from dataclasses import dataclass
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


_memory = MemoryMailer()


def get_mailer() -> Mailer:
    mailer = get_settings().mailer
    if mailer == "memory":
        return _memory
    if mailer == "disabled":
        return DisabledMailer()
    return ConsoleMailer()


def memory_mailer() -> MemoryMailer:
    return _memory
