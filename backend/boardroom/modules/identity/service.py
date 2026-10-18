"""Tenants, users, roles, invitations and sign-in (FRD chapter 2)."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from boardroom.config import get_settings
from boardroom.db import app_session, as_system, set_tenant, system_session
from boardroom.events import emit
from boardroom.modules.audit import service as audit
from boardroom.modules.identity.models import (
    CompanySettings,
    IdentityOutbox,
    Invitation,
    Membership,
    RefreshToken,
    Tenant,
    User,
)
from boardroom.permissions import (
    COMPANY_ROLES,
    DEFAULT_APPROVER_ROLES,
    Action,
    Department,
    Role,
    TenantType,
    allowed,
    can_approve,
)
from boardroom.security.tokens import (
    hash_opaque_token,
    hash_password,
    issue_access_token,
    new_opaque_token,
    verify_password,
)

INVITATION_CREATED = "identity.invitation_created"


class IdentityError(Exception):
    """A request the caller can fix. ``code`` maps to an HTTP status in the API."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class Tokens:
    access_token: str
    access_expires_at: datetime
    refresh_token: str


@dataclass
class ActiveMembership:
    role: Role
    departments: list[str]


def _now() -> datetime:
    return datetime.now(UTC)


def normalise_email(email: str) -> str:
    return email.strip().lower()


# Sign-up, sign-in and tokens


def _issue_tokens(session: Session, user_id: uuid.UUID) -> Tokens:
    access, expires = issue_access_token(user_id)
    refresh, refresh_hash = new_opaque_token()
    session.add(
        RefreshToken(
            user_id=user_id,
            token_hash=refresh_hash,
            expires_at=_now() + timedelta(days=get_settings().refresh_token_days),
        )
    )
    return Tokens(access, expires, refresh)


def sign_up(
    email: str,
    password: str,
    name: str,
    company_name: str | None = None,
    invite_token: str | None = None,
) -> tuple[Tokens, uuid.UUID | None]:
    """Create a user. With a company name they become its Owner (FR-2.1).
    With an invitation they join that company in the invited role."""
    email = normalise_email(email)
    if bool(company_name) == bool(invite_token):
        raise IdentityError(422, "Give a company name or an invitation, not both.")

    user_id = uuid.uuid4()
    try:
        with app_session(user_id=user_id) as session:
            session.add(
                User(id=user_id, email=email, name=name, password_hash=hash_password(password))
            )
            session.flush()
            audit.record(session, "user.signed_up", tenant_id=None, actor_user_id=user_id)
            if company_name:
                tenant_id = _create_company(session, user_id, company_name)
            else:
                with as_system(session):
                    tenant_id = _accept(session, user_id, email, invite_token or "")
            tokens = _issue_tokens(session, user_id)
    except IntegrityError as exc:
        raise IdentityError(
            409, "An account with this email already exists. Sign in instead."
        ) from exc
    return tokens, tenant_id


def sign_in(email: str, password: str) -> Tokens:
    email = normalise_email(email)
    with system_session() as session:
        user = session.scalar(select(User).where(User.email == email))
        if user is not None and verify_password(user.password_hash, password):
            audit.record(session, "auth.login", tenant_id=None, actor_user_id=user.id)
            return _issue_tokens(session, user.id)
        if user is None:
            verify_password(None, password)
        # Committed before refusing, so the failure stays in the audit log.
        audit.record(session, "auth.login_failed", tenant_id=None, actor_user_id=None)
    raise IdentityError(401, "That email and password do not match.")


def refresh(refresh_token: str) -> Tokens:
    """Swap a refresh token for a new pair. Each refresh token works once."""
    with system_session() as session:
        row = session.scalar(
            select(RefreshToken)
            .where(RefreshToken.token_hash == hash_opaque_token(refresh_token))
            .with_for_update()
        )
        if row is None or row.revoked_at is not None or row.expires_at <= _now():
            raise IdentityError(401, "Sign in again to continue.")
        row.revoked_at = _now()
        return _issue_tokens(session, row.user_id)


def sign_out(refresh_token: str) -> None:
    with system_session() as session:
        row = session.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == hash_opaque_token(refresh_token))
        )
        if row is not None and row.revoked_at is None:
            row.revoked_at = _now()
            audit.record(session, "auth.logout", tenant_id=None, actor_user_id=row.user_id)


# Membership lookups used by the gateway


def is_platform_admin(session: Session, user_id: uuid.UUID) -> bool:
    user = session.get(User, user_id)
    return bool(user and user.is_platform_admin)


@dataclass
class Contact:
    email: str
    name: str
    company_name: str


def contact(session: Session, user_id: uuid.UUID, tenant_id: uuid.UUID) -> Contact | None:
    """For emails sent by notify, which runs as br_system."""
    user = session.get(User, user_id)
    tenant = session.get(Tenant, tenant_id)
    if user is None or tenant is None:
        return None
    return Contact(user.email, user.name, tenant.name)


def user_exists(session: Session, user_id: uuid.UUID) -> bool:
    return session.get(User, user_id) is not None


def active_membership(
    session: Session, user_id: uuid.UUID, tenant_id: uuid.UUID
) -> ActiveMembership | None:
    row = session.execute(
        select(Membership.role, Membership.departments)
        .join(Tenant, Tenant.id == Membership.tenant_id)
        .where(
            Membership.user_id == user_id,
            Membership.tenant_id == tenant_id,
            Membership.status == "active",
            Tenant.deleted_at.is_(None),
        )
    ).first()
    if row is None:
        return None
    return ActiveMembership(Role(row.role), list(row.departments or []))


def me(session: Session, user_id: uuid.UUID) -> tuple[User, list[tuple[Membership, Tenant]]]:
    user = session.get(User, user_id)
    assert user is not None  # noqa: S101
    rows = session.execute(
        select(Membership, Tenant)
        .join(Tenant, Tenant.id == Membership.tenant_id)
        .where(
            Membership.user_id == user_id,
            Membership.status == "active",
            Tenant.deleted_at.is_(None),
        )
        .order_by(Tenant.name)
    ).all()
    return user, [(m, t) for m, t in rows]


# Companies


def _create_company(session: Session, user_id: uuid.UUID, name: str) -> uuid.UUID:
    tenant_id = uuid.uuid4()
    set_tenant(session, user_id, tenant_id)
    session.add(Tenant(id=tenant_id, tenant_type=TenantType.COMPANY.value, name=name.strip()))
    session.flush()
    session.add(Membership(tenant_id=tenant_id, user_id=user_id, role=Role.OWNER.value))
    # The Owner's membership comes first: the rest of the company is only writable by members.
    session.flush()
    session.add(
        CompanySettings(
            tenant_id=tenant_id,
            approver_roles=[r.value for r in DEFAULT_APPROVER_ROLES],
            approver_user_ids=[],
        )
    )
    audit.record(
        session,
        "company.created",
        tenant_id=tenant_id,
        actor_user_id=user_id,
        target_type="tenant",
        target_id=tenant_id,
    )
    session.flush()
    return tenant_id


def create_company(session: Session, user_id: uuid.UUID, name: str) -> uuid.UUID:
    return _create_company(session, user_id, name)


def get_company(session: Session, tenant_id: uuid.UUID) -> Tenant:
    tenant = session.get(Tenant, tenant_id)
    assert tenant is not None  # noqa: S101
    return tenant


def delete_workspace(session: Session, tenant_id: uuid.UUID, actor: uuid.UUID) -> None:
    """Closes the workspace at once. Purging every store follows in E10 (30 days)."""
    tenant = get_company(session, tenant_id)
    tenant.deleted_at = _now()
    audit.record(
        session,
        "company.deleted",
        tenant_id=tenant_id,
        actor_user_id=actor,
        target_type="tenant",
        target_id=tenant_id,
    )


def _members(
    session: Session, tenant_id: uuid.UUID, roles: set[Role]
) -> list[tuple[Membership, User]]:
    rows = session.execute(
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(
            Membership.tenant_id == tenant_id,
            Membership.status == "active",
            Membership.role.in_([r.value for r in roles]),
        )
        .order_by(User.name)
    ).all()
    return [(m, u) for m, u in rows]


def list_team(session: Session, tenant_id: uuid.UUID) -> list[tuple[Membership, User]]:
    return _members(session, tenant_id, set(COMPANY_ROLES))


def list_investors(session: Session, tenant_id: uuid.UUID) -> list[tuple[Membership, User]]:
    """Co-investors in the same company can see each other (FR-2.5)."""
    return _members(session, tenant_id, {Role.INVESTOR})


def remove_investor(
    session: Session, tenant_id: uuid.UUID, actor: uuid.UUID, user_id: uuid.UUID
) -> None:
    """Stops access on the investor's next request (FR-2.8)."""
    membership = session.scalar(
        select(Membership).where(
            Membership.tenant_id == tenant_id,
            Membership.user_id == user_id,
            Membership.role == Role.INVESTOR.value,
            Membership.status == "active",
        )
    )
    if membership is None:
        raise IdentityError(404, "That investor is not in this company.")
    membership.status = "removed"
    membership.removed_at = _now()
    audit.record(
        session,
        "investor.removed",
        tenant_id=tenant_id,
        actor_user_id=actor,
        target_type="user",
        target_id=user_id,
        details={"keeps": get_settings().removed_investor_keeps},
    )


def investor_emails(session: Session, tenant_id: uuid.UUID) -> list[str]:
    """Investors in the company and those invited, for the setup chat."""
    members = session.scalars(
        select(User.email)
        .join(Membership, Membership.user_id == User.id)
        .where(
            Membership.tenant_id == tenant_id,
            Membership.role == Role.INVESTOR.value,
            Membership.status == "active",
        )
    ).all()
    invited = session.scalars(
        select(Invitation.email).where(
            Invitation.tenant_id == tenant_id,
            Invitation.role == Role.INVESTOR.value,
            Invitation.accepted_at.is_(None),
            Invitation.revoked_at.is_(None),
        )
    ).all()
    return sorted(set(members) | set(invited))


def portfolio(session: Session, user_id: uuid.UUID) -> list[Tenant]:
    """Every company that has invited this user as an investor (FR-2.4)."""
    return list(
        session.scalars(
            select(Tenant)
            .join(Membership, Membership.tenant_id == Tenant.id)
            .where(
                Membership.user_id == user_id,
                Membership.role == Role.INVESTOR.value,
                Membership.status == "active",
                Tenant.deleted_at.is_(None),
            )
            .order_by(Tenant.name)
        ).all()
    )


# Invitations


def create_invitation(
    session: Session,
    tenant_id: uuid.UUID,
    actor: uuid.UUID,
    actor_role: Role,
    email: str,
    role: Role,
    departments: list[Department],
) -> Invitation:
    email = normalise_email(email)
    if role == Role.OWNER:
        raise IdentityError(422, "A company has one Owner. Invite this person as CEO instead.")
    needed = Action.INVITE_INVESTORS if role == Role.INVESTOR else Action.INVITE_USERS
    if not allowed(actor_role, needed):
        raise IdentityError(403, "You do not have access to this.")
    if role == Role.DEPARTMENT_LEAD and not departments:
        raise IdentityError(422, "Choose at least one department for a department lead.")
    if role == Role.CONTRIBUTOR and len(departments) != 1:
        raise IdentityError(422, "Choose one department for a contributor.")
    if role not in (Role.DEPARTMENT_LEAD, Role.CONTRIBUTOR):
        departments = []

    already_member = session.scalar(
        select(func.count())
        .select_from(Membership)
        .join(User, User.id == Membership.user_id)
        .where(
            Membership.tenant_id == tenant_id,
            Membership.status == "active",
            User.email == email,
        )
    )
    if already_member:
        raise IdentityError(409, "This person is already in the company.")

    invitation = Invitation(
        tenant_id=tenant_id,
        email=email,
        role=role.value,
        departments=[d.value for d in departments],
        invited_by=actor,
        expires_at=_now() + timedelta(days=get_settings().invitation_days),
    )
    session.add(invitation)
    session.flush()
    audit.record(
        session,
        "invitation.created",
        tenant_id=tenant_id,
        actor_user_id=actor,
        target_type="invitation",
        target_id=invitation.id,
        details={"role": role.value},
    )
    emit(
        session,
        IdentityOutbox,
        INVITATION_CREATED,
        tenant_id,
        {"invitation_id": str(invitation.id)},
    )
    return invitation


def list_invitations(session: Session) -> list[Invitation]:
    return list(
        session.scalars(
            select(Invitation)
            .where(Invitation.accepted_at.is_(None), Invitation.revoked_at.is_(None))
            .order_by(Invitation.created_at.desc())
        ).all()
    )


def revoke_invitation(
    session: Session,
    tenant_id: uuid.UUID,
    actor: uuid.UUID,
    actor_role: Role,
    invitation_id: uuid.UUID,
) -> None:
    invitation = session.get(Invitation, invitation_id)
    if invitation is None or invitation.accepted_at or invitation.revoked_at:
        raise IdentityError(404, "That invitation is not open.")
    needed = Action.INVITE_INVESTORS if invitation.role == Role.INVESTOR else Action.INVITE_USERS
    if not allowed(actor_role, needed):
        raise IdentityError(403, "You do not have access to this.")
    invitation.revoked_at = _now()
    invitation.token_hash = None
    audit.record(
        session,
        "invitation.revoked",
        tenant_id=tenant_id,
        actor_user_id=actor,
        target_type="invitation",
        target_id=invitation.id,
    )


@dataclass
class InvitationLink:
    email: str
    token: str
    role: str
    company_name: str
    invited_by_name: str


def issue_invitation_link(session: Session, invitation_id: uuid.UUID) -> InvitationLink | None:
    """Mint the token for an invitation email. Called by notify in a system session.
    Only the hash is stored, so each email carries a fresh token."""
    invitation = session.get(Invitation, invitation_id)
    if invitation is None or invitation.accepted_at or invitation.revoked_at:
        return None
    token, token_hash = new_opaque_token()
    invitation.token_hash = token_hash
    tenant = session.get(Tenant, invitation.tenant_id)
    inviter = session.get(User, invitation.invited_by)
    assert tenant is not None and inviter is not None  # noqa: S101
    return InvitationLink(invitation.email, token, invitation.role, tenant.name, inviter.name)


def _accept(session: Session, user_id: uuid.UUID, user_email: str, token: str) -> uuid.UUID:
    """Runs as br_system: the user is not yet a member, so the app role cannot see
    the invitation."""
    invitation = session.scalar(
        select(Invitation)
        .where(Invitation.token_hash == hash_opaque_token(token))
        .with_for_update()
    )
    if invitation is None or invitation.revoked_at or invitation.accepted_at:
        raise IdentityError(404, "This invitation link is not valid. Ask for a new one.")
    if invitation.expires_at <= _now():
        raise IdentityError(410, "This invitation has expired. Ask for a new one.")
    if normalise_email(user_email) != invitation.email:
        raise IdentityError(403, "This invitation was sent to a different email address.")

    membership = session.scalar(
        select(Membership).where(
            Membership.user_id == user_id, Membership.tenant_id == invitation.tenant_id
        )
    )
    if membership is not None and membership.status == "active":
        raise IdentityError(409, "You are already in this company.")
    if membership is None:
        membership = Membership(tenant_id=invitation.tenant_id, user_id=user_id)
        session.add(membership)
    membership.role = invitation.role
    membership.departments = list(invitation.departments)
    membership.status = "active"
    membership.removed_at = None

    invitation.accepted_at = _now()
    invitation.token_hash = None
    audit.record(
        session,
        "invitation.accepted",
        tenant_id=invitation.tenant_id,
        actor_user_id=user_id,
        target_type="invitation",
        target_id=invitation.id,
        details={"role": invitation.role},
    )
    session.flush()
    return invitation.tenant_id


def accept_invitation(user_id: uuid.UUID, token: str) -> uuid.UUID:
    """An existing user accepts, for example an investor joining a second company."""
    with app_session(user_id=user_id) as session:
        user = session.get(User, user_id)
        assert user is not None  # noqa: S101
        with as_system(session):
            return _accept(session, user_id, user.email, token)


# Settings


def approval_setting(session: Session) -> CompanySettings:
    settings = session.scalar(select(CompanySettings))
    assert settings is not None  # noqa: S101
    return settings


def set_approvers(
    session: Session,
    tenant_id: uuid.UUID,
    actor: uuid.UUID,
    roles: list[Role],
    user_ids: list[uuid.UUID],
) -> CompanySettings:
    """Who can approve an update, per company (FR-2.7). The Owner always can."""
    for role in roles:
        if role not in (Role.CEO, Role.DEPARTMENT_LEAD):
            raise IdentityError(422, "Only the CEO and department leads can be given approval.")
    if user_ids:
        eligible = set(
            session.scalars(
                select(Membership.user_id).where(
                    Membership.tenant_id == tenant_id,
                    Membership.status == "active",
                    Membership.user_id.in_(user_ids),
                    Membership.role.in_([Role.CEO.value, Role.DEPARTMENT_LEAD.value]),
                )
            ).all()
        )
        if eligible != set(user_ids):
            raise IdentityError(
                422, "Approval can only go to the CEO or a department lead in this company."
            )
    settings = approval_setting(session)
    before = {"roles": list(settings.approver_roles), "user_ids": list(settings.approver_user_ids)}
    settings.approver_roles = sorted({r.value for r in roles})
    settings.approver_user_ids = sorted({str(u) for u in user_ids})
    audit.record(
        session,
        "settings.approval_changed",
        tenant_id=tenant_id,
        actor_user_id=actor,
        target_type="company_settings",
        target_id=tenant_id,
        details={
            "before": before,
            "after": {"roles": settings.approver_roles, "user_ids": settings.approver_user_ids},
        },
    )
    session.flush()
    return settings


def user_can_approve(session: Session, user_id: uuid.UUID, role: Role) -> bool:
    settings = approval_setting(session)
    return can_approve(role, str(user_id), settings.approver_roles, settings.approver_user_ids)


# People to notify about updates (E5). Every query names the tenant, because these are
# also read by event consumers running as br_system.


@dataclass(frozen=True)
class MemberContact:
    user_id: uuid.UUID
    email: str
    name: str
    role: Role


def member_contacts(
    session: Session, tenant_id: uuid.UUID, roles: set[Role]
) -> list[MemberContact]:
    return [
        MemberContact(u.id, u.email, u.name, Role(m.role))
        for m, u in _members(session, tenant_id, roles)
    ]


def approvers(session: Session, tenant_id: uuid.UUID) -> list[MemberContact]:
    """Everyone who can approve this company's updates under its setting (FR-2.7)."""
    settings = session.scalar(select(CompanySettings).where(CompanySettings.tenant_id == tenant_id))
    if settings is None:
        return []
    return [
        c
        for c in member_contacts(session, tenant_id, set(COMPANY_ROLES))
        if can_approve(c.role, str(c.user_id), settings.approver_roles, settings.approver_user_ids)
    ]


def mentionable(session: Session, tenant_id: uuid.UUID, role: Role) -> list[MemberContact]:
    """Who a person can tag with @ in a comment. The company can tag anyone in it. An
    investor can tag the company's Owner, CEO and department leads, and the other
    investors, whom they can already see (FR-2.5), never the whole team."""
    if role == Role.INVESTOR:
        roles = {Role.OWNER, Role.CEO, Role.DEPARTMENT_LEAD, Role.INVESTOR}
    else:
        roles = set(Role)
    return member_contacts(session, tenant_id, roles)
