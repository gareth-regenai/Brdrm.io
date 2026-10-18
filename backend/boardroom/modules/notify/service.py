"""Sends emails in response to events from other modules."""

import uuid

from sqlalchemy.orm import Session

from boardroom.config import get_settings
from boardroom.events import Event, consumer
from boardroom.modules.audit import service as audit
from boardroom.modules.identity import service as identity
from boardroom.modules.notify.mailer import Email, get_mailer

ROLE_WORDS = {
    "ceo": "CEO",
    "department_lead": "department lead",
    "contributor": "contributor",
    "investor": "investor",
}


@consumer("notify.invitation_email", identity.INVITATION_CREATED)
def send_invitation(session: Session, event: Event) -> None:
    link = identity.issue_invitation_link(session, uuid.UUID(event.payload["invitation_id"]))
    if link is None:
        return
    settings = get_settings()
    url = f"{settings.web_origin}/invite?token={link.token}"
    expiry = f"The link works once and expires in {settings.invitation_days} days."
    if link.role == "investor":
        body = (
            f"{link.invited_by_name} has invited you to follow {link.company_name} "
            "on BoardRoom.io.\n\n"
            "You will see every update the company shares with its investors, and can comment.\n\n"
            f"Accept the invitation: {url}\n\n{expiry}"
        )
    else:
        body = (
            f"{link.invited_by_name} has invited you to join {link.company_name} on BoardRoom.io "
            f"as {ROLE_WORDS.get(link.role, link.role)}.\n\n"
            f"Accept the invitation: {url}\n\n{expiry}"
        )
    get_mailer().send(
        Email(to=link.email, subject=f"Join {link.company_name} on BoardRoom.io", body=body)
    )
    audit.record(
        session,
        "invitation.sent",
        tenant_id=event.tenant_id,
        actor_user_id=None,
        target_type="invitation",
        target_id=event.payload["invitation_id"],
    )
