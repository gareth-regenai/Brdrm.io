"""Sends emails in response to events from other modules."""

import uuid

from sqlalchemy.orm import Session

from boardroom.config import get_settings
from boardroom.events import Event, consumer
from boardroom.modules.audit import service as audit
from boardroom.modules.identity import service as identity
from boardroom.modules.notify.mailer import Email, get_mailer
from boardroom.modules.updates import service as updates
from boardroom.permissions import Role

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


@consumer("notify.question_email", "intake.question_asked")
def send_question(session: Session, event: Event) -> None:
    """The one question also goes by email, so the upload does not wait unseen (FR-3.2)."""
    assert event.tenant_id is not None  # noqa: S101
    person = identity.contact(session, uuid.UUID(event.payload["user_id"]), event.tenant_id)
    if person is None:
        return
    url = f"{get_settings().web_origin}/c/{event.tenant_id}"
    body = (
        f"We have one question about a file you added to {person.company_name}.\n\n"
        f"Answer it here: {url}\n\n"
        "The rest of the file is ready. Its figures are calculated as soon as you answer."
    )
    get_mailer().send(Email(to=person.email, subject="One question about your file", body=body))


# Updates (E5)


def _company_url(tenant_id: uuid.UUID | None) -> str:
    return f"{get_settings().web_origin}/c/{tenant_id}"


def _send_all(contacts: list[identity.MemberContact], subject: str, body: str) -> None:
    mailer = get_mailer()
    for c in contacts:
        mailer.send(Email(to=c.email, subject=subject, body=body))


@consumer("notify.update_waiting", "updates.created")
def update_waiting(session: Session, event: Event) -> None:
    """Approvers hear that an update is waiting, unless they added it themselves."""
    assert event.tenant_id is not None  # noqa: S101
    notice = updates.update_notice(session, event.tenant_id, uuid.UUID(event.payload["update_id"]))
    if notice is None:
        return
    company = identity.get_company(session, event.tenant_id)
    people = [
        c for c in identity.approvers(session, event.tenant_id) if c.user_id != notice.added_by
    ]
    body = (
        f"{notice.line}\n\n"
        "Investors see it once it is approved. Check it and approve it here: "
        f"{_company_url(event.tenant_id)}"
    )
    _send_all(people, f"An update for {company.name} is waiting for approval", body)


@consumer("notify.update_shared", "updates.shared")
def update_shared(session: Session, event: Event) -> None:
    """Every investor hears about a shared update: their access is standing (FR-2.3)."""
    assert event.tenant_id is not None  # noqa: S101
    notice = updates.update_notice(session, event.tenant_id, uuid.UUID(event.payload["update_id"]))
    if notice is None:
        return
    company = identity.get_company(session, event.tenant_id)
    investors = identity.member_contacts(session, event.tenant_id, {Role.INVESTOR})
    body = (
        f"{company.name} shared an update.\n\n{notice.line}\n\n"
        f"See the figures and where each one comes from: {_company_url(event.tenant_id)}"
    )
    _send_all(investors, f"New update from {company.name}", body)


@consumer("notify.comment", "updates.comment_added")
def comment_added(session: Session, event: Event) -> None:
    """A comment tells the other side (FR-6.5): an investor's comment goes to the CEO and
    Owner, the company's reply to the company's investors."""
    assert event.tenant_id is not None  # noqa: S101
    notice = updates.comment_notice(
        session, event.tenant_id, uuid.UUID(event.payload["comment_id"])
    )
    if notice is None:
        return
    if notice.from_investor:
        people = identity.member_contacts(session, event.tenant_id, {Role.OWNER, Role.CEO})
    elif notice.shared:
        people = identity.member_contacts(session, event.tenant_id, {Role.INVESTOR})
    else:
        people = []  # investors cannot see an update that is not shared yet
    people = [c for c in people if c.user_id != notice.author_id]
    company = identity.get_company(session, event.tenant_id)
    body = (
        f'{notice.author_name} commented on "{notice.line}":\n\n{notice.body}\n\n'
        f"Reply here: {_company_url(event.tenant_id)}"
    )
    _send_all(people, f"New comment on an update from {company.name}", body)
