import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr, Field

from boardroom.gateway.deps import TenantContext, UserContext, current_user, require
from boardroom.modules.audit import service as audit
from boardroom.modules.identity import service as identity
from boardroom.modules.identity.models import Invitation
from boardroom.permissions import MATRIX, Action, Department, Role, allowed

router = APIRouter()


# Schemas


class SignUpIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    company_name: str | None = Field(default=None, min_length=1, max_length=200)
    invite_token: str | None = Field(default=None, max_length=200)


class SignInIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=200)


class RefreshIn(BaseModel):
    refresh_token: str = Field(max_length=200)


class TokensOut(BaseModel):
    access_token: str
    access_expires_at: datetime
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105
    tenant_id: uuid.UUID | None = None


class MembershipOut(BaseModel):
    tenant_id: uuid.UUID
    tenant_name: str
    tenant_type: str
    role: Role
    departments: list[str]


class MeOut(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    memberships: list[MembershipOut]


class CompanyIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class CompanyOut(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime


class PersonOut(BaseModel):
    user_id: uuid.UUID
    name: str
    email: str | None
    role: Role
    departments: list[str]


class InvitationIn(BaseModel):
    email: EmailStr
    role: Role
    departments: list[Department] = Field(default_factory=list)


class InvitationOut(BaseModel):
    id: uuid.UUID
    email: str
    role: Role
    departments: list[str]
    expires_at: datetime
    created_at: datetime


class AcceptIn(BaseModel):
    token: str = Field(max_length=200)


class AcceptOut(BaseModel):
    tenant_id: uuid.UUID


class PortfolioCompanyOut(BaseModel):
    id: uuid.UUID
    name: str


class ApprovalIn(BaseModel):
    roles: list[Role]
    user_ids: list[uuid.UUID] = Field(default_factory=list)


class ApprovalOut(BaseModel):
    roles: list[str]
    user_ids: list[str]
    note: str = "The Owner can always approve."


class PermissionsOut(BaseModel):
    role: Role
    actions: list[Action]
    can_approve: bool


class AuditOut(BaseModel):
    id: uuid.UUID
    action: str
    actor_user_id: uuid.UUID | None
    target_type: str | None
    target_id: str | None
    details: dict[str, object]
    created_at: datetime


def _tokens(tokens: identity.Tokens, tenant_id: uuid.UUID | None = None) -> TokensOut:
    return TokensOut(
        access_token=tokens.access_token,
        access_expires_at=tokens.access_expires_at,
        refresh_token=tokens.refresh_token,
        tenant_id=tenant_id,
    )


# Public: sign-up and sign-in


@router.post("/auth/signup", response_model=TokensOut, status_code=201, tags=["auth"])
def sign_up(body: SignUpIn) -> TokensOut:
    tokens, tenant_id = identity.sign_up(
        body.email, body.password, body.name, body.company_name, body.invite_token
    )
    return _tokens(tokens, tenant_id)


@router.post("/auth/login", response_model=TokensOut, tags=["auth"])
def sign_in(body: SignInIn) -> TokensOut:
    return _tokens(identity.sign_in(body.email, body.password))


@router.post("/auth/refresh", response_model=TokensOut, tags=["auth"])
def refresh(body: RefreshIn) -> TokensOut:
    return _tokens(identity.refresh(body.refresh_token))


@router.post("/auth/logout", status_code=204, tags=["auth"])
def sign_out(body: RefreshIn) -> Response:
    identity.sign_out(body.refresh_token)
    return Response(status_code=204)


# Signed in, no company selected


@router.get("/me", response_model=MeOut, tags=["account"])
def me(ctx: UserContext = Depends(current_user)) -> MeOut:
    user, rows = identity.me(ctx.session, ctx.user_id)
    return MeOut(
        id=user.id,
        email=user.email,
        name=user.name,
        memberships=[
            MembershipOut(
                tenant_id=t.id,
                tenant_name=t.name,
                tenant_type=t.tenant_type,
                role=Role(m.role),
                departments=list(m.departments or []),
            )
            for m, t in rows
        ],
    )


@router.post("/companies", response_model=CompanyOut, status_code=201, tags=["account"])
def create_company(body: CompanyIn, ctx: UserContext = Depends(current_user)) -> CompanyOut:
    tenant_id = identity.create_company(ctx.session, ctx.user_id, body.name)
    tenant = identity.get_company(ctx.session, tenant_id)
    return CompanyOut(id=tenant.id, name=tenant.name, created_at=tenant.created_at)


@router.post("/invitations/accept", response_model=AcceptOut, tags=["account"])
def accept_invitation(body: AcceptIn, ctx: UserContext = Depends(current_user)) -> AcceptOut:
    # The company is not known until the token is looked up, so this runs in its own session.
    return AcceptOut(tenant_id=identity.accept_invitation(ctx.user_id, body.token))


@router.get("/portfolio", response_model=list[PortfolioCompanyOut], tags=["investor"])
def portfolio(ctx: UserContext = Depends(current_user)) -> list[PortfolioCompanyOut]:
    companies = identity.portfolio(ctx.session, ctx.user_id)
    if not companies:
        # Company roles cannot reach the overview (FR-7.7).
        raise HTTPException(status.HTTP_403_FORBIDDEN, "The portfolio is for investors.")
    return [PortfolioCompanyOut(id=t.id, name=t.name) for t in companies]


# Company endpoints. Every one names the action it performs.


@router.get("/company", response_model=CompanyOut, tags=["company"])
def get_company(
    ctx: TenantContext = Depends(require(Action.VIEW_COMPANY, audit_view=True)),
) -> CompanyOut:
    tenant = identity.get_company(ctx.session, ctx.tenant_id)
    return CompanyOut(id=tenant.id, name=tenant.name, created_at=tenant.created_at)


@router.delete("/company", status_code=204, tags=["company"])
def delete_company(ctx: TenantContext = Depends(require(Action.DELETE_WORKSPACE))) -> Response:
    identity.delete_workspace(ctx.session, ctx.tenant_id, ctx.user_id)
    return Response(status_code=204)


@router.get("/company/permissions", response_model=PermissionsOut, tags=["company"])
def my_permissions(ctx: TenantContext = Depends(require(Action.VIEW_COMPANY))) -> PermissionsOut:
    return PermissionsOut(
        role=ctx.role,
        actions=[a for a in MATRIX if allowed(ctx.role, a)],
        can_approve=identity.user_can_approve(ctx.session, ctx.user_id, ctx.role),
    )


@router.get("/company/team", response_model=list[PersonOut], tags=["company"])
def team(ctx: TenantContext = Depends(require(Action.VIEW_TEAM))) -> list[PersonOut]:
    return [
        PersonOut(
            user_id=u.id,
            name=u.name,
            email=u.email,
            role=Role(m.role),
            departments=list(m.departments or []),
        )
        for m, u in identity.list_team(ctx.session, ctx.tenant_id)
    ]


@router.get("/company/investors", response_model=list[PersonOut], tags=["company"])
def investors(ctx: TenantContext = Depends(require(Action.VIEW_INVESTORS))) -> list[PersonOut]:
    show_email = ctx.role != Role.INVESTOR
    return [
        PersonOut(
            user_id=u.id,
            name=u.name,
            email=u.email if show_email else None,
            role=Role(m.role),
            departments=[],
        )
        for m, u in identity.list_investors(ctx.session, ctx.tenant_id)
    ]


@router.delete("/company/investors/{user_id}", status_code=204, tags=["company"])
def remove_investor(
    user_id: uuid.UUID, ctx: TenantContext = Depends(require(Action.REMOVE_INVESTOR))
) -> Response:
    identity.remove_investor(ctx.session, ctx.tenant_id, ctx.user_id, user_id)
    return Response(status_code=204)


def _invitation_out(i: Invitation) -> InvitationOut:
    return InvitationOut(
        id=i.id,
        email=i.email,
        role=Role(i.role),
        departments=list(i.departments or []),
        expires_at=i.expires_at,
        created_at=i.created_at,
    )


@router.post(
    "/company/invitations", response_model=InvitationOut, status_code=201, tags=["company"]
)
def invite(
    body: InvitationIn, ctx: TenantContext = Depends(require(Action.INVITE_USERS))
) -> InvitationOut:
    invitation = identity.create_invitation(
        ctx.session, ctx.tenant_id, ctx.user_id, ctx.role, body.email, body.role, body.departments
    )
    return _invitation_out(invitation)


@router.get("/company/invitations", response_model=list[InvitationOut], tags=["company"])
def invitations(ctx: TenantContext = Depends(require(Action.INVITE_USERS))) -> list[InvitationOut]:
    return [_invitation_out(i) for i in identity.list_invitations(ctx.session)]


@router.delete("/company/invitations/{invitation_id}", status_code=204, tags=["company"])
def revoke(
    invitation_id: uuid.UUID, ctx: TenantContext = Depends(require(Action.INVITE_USERS))
) -> Response:
    identity.revoke_invitation(ctx.session, ctx.tenant_id, ctx.user_id, ctx.role, invitation_id)
    return Response(status_code=204)


@router.get("/company/settings/approval", response_model=ApprovalOut, tags=["company"])
def get_approval(ctx: TenantContext = Depends(require(Action.MANAGE_SETTINGS))) -> ApprovalOut:
    s = identity.approval_setting(ctx.session)
    return ApprovalOut(roles=list(s.approver_roles), user_ids=list(s.approver_user_ids))


@router.put("/company/settings/approval", response_model=ApprovalOut, tags=["company"])
def put_approval(
    body: ApprovalIn, ctx: TenantContext = Depends(require(Action.MANAGE_SETTINGS))
) -> ApprovalOut:
    s = identity.set_approvers(ctx.session, ctx.tenant_id, ctx.user_id, body.roles, body.user_ids)
    return ApprovalOut(roles=list(s.approver_roles), user_ids=list(s.approver_user_ids))


@router.get("/company/audit", response_model=list[AuditOut], tags=["company"])
def audit_log(ctx: TenantContext = Depends(require(Action.VIEW_AUDIT))) -> list[AuditOut]:
    return [
        AuditOut(
            id=e.id,
            action=e.action,
            actor_user_id=e.actor_user_id,
            target_type=e.target_type,
            target_id=e.target_id,
            details=e.details,
            created_at=e.created_at,
        )
        for e in audit.list_for_tenant(ctx.session)
    ]
