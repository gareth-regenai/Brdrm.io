import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from boardroom.gateway.deps import TenantContext, require
from boardroom.modules.setup import chat, service
from boardroom.permissions import Action

router = APIRouter()


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    applied: dict[str, Any]
    created_at: datetime


class SummaryRow(BaseModel):
    label: str
    value: str


class SetupOut(BaseModel):
    status: str | None
    messages: list[MessageOut]
    pending_invites: list[str]
    # The "Set up for you" card beside the interview.
    summary: list[SummaryRow]
    has_files: bool


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class ProfileOut(BaseModel):
    reporting_currency: str
    business_description: str | None
    website: str | None
    revenue_lines: list[str]
    display_band: int | None
    voice: str


class ProfileIn(BaseModel):
    reporting_currency: str | None = None
    business_description: str | None = Field(default=None, max_length=300)
    website: str | None = Field(default=None, max_length=200)
    display_band: int | None = Field(default=None, ge=0, le=4)
    follow_revenue: bool = False
    voice: Literal["we", "third_person"] | None = None


class TargetIn(BaseModel):
    metric: Literal["revenue", "closed_won"]
    period: str = Field(pattern=r"^20\d\d-(0[1-9]|1[0-2])$")
    value: Decimal = Field(gt=0)


class TargetOut(BaseModel):
    metric: str
    period: str
    value: str
    source: str
    set_by_name: str


def _out(ctx: TenantContext) -> SetupOut:
    conv = service.conversation(ctx.session, ctx.tenant_id)
    found, has_files = service.summary(ctx.session, ctx.tenant_id, ctx.user_id)
    rows = [SummaryRow(label=k, value=v) for k, v in found]
    if conv is None:
        return SetupOut(
            status=None, messages=[], pending_invites=[], summary=rows, has_files=has_files
        )
    return SetupOut(
        status=conv.status,
        messages=[
            MessageOut(
                id=m.id, role=m.role, content=m.content, applied=m.applied, created_at=m.created_at
            )
            for m in service.messages(ctx.session, conv)
        ],
        pending_invites=list(conv.pending_invites or []),
        summary=rows,
        has_files=has_files,
    )


@router.get("/company/setup", response_model=SetupOut, tags=["setup"])
def get_setup(ctx: TenantContext = Depends(require(Action.MANAGE_SETTINGS))) -> SetupOut:
    return _out(ctx)


@router.post("/company/setup/start", response_model=SetupOut, tags=["setup"])
def start(ctx: TenantContext = Depends(require(Action.MANAGE_SETTINGS))) -> SetupOut:
    service.start(ctx.session, ctx.tenant_id, ctx.user_id)
    return _out(ctx)


@router.post("/company/setup/messages", response_model=SetupOut, tags=["setup"])
def send(
    body: MessageIn, ctx: TenantContext = Depends(require(Action.MANAGE_SETTINGS))
) -> SetupOut:
    service.send(ctx.session, ctx.tenant_id, ctx.user_id, body.text.strip())
    return _out(ctx)


@router.post("/company/setup/skip", response_model=SetupOut, tags=["setup"])
def skip(ctx: TenantContext = Depends(require(Action.MANAGE_SETTINGS))) -> SetupOut:
    service.skip(ctx.session, ctx.tenant_id, ctx.user_id)
    return _out(ctx)


@router.post("/company/setup/invites", response_model=SetupOut, tags=["setup"])
def send_invites(ctx: TenantContext = Depends(require(Action.INVITE_INVESTORS))) -> SetupOut:
    try:
        service.send_invites(ctx.session, ctx.tenant_id, ctx.user_id, ctx.role)
    except service.SetupError as exc:
        raise HTTPException(exc.code, exc.message) from exc
    return _out(ctx)


@router.delete("/company/setup/invites", response_model=SetupOut, tags=["setup"])
def discard_invites(ctx: TenantContext = Depends(require(Action.INVITE_INVESTORS))) -> SetupOut:
    service.discard_invites(ctx.session, ctx.tenant_id, ctx.user_id)
    return _out(ctx)


def _profile_out(ctx: TenantContext) -> ProfileOut:
    p = service.profile(ctx.session, ctx.tenant_id)
    return ProfileOut(
        reporting_currency=p.reporting_currency,
        business_description=p.business_description,
        website=p.website,
        revenue_lines=list(p.revenue_lines or []),
        display_band=p.display_band,
        voice=p.voice,
    )


@router.get("/company/settings/profile", response_model=ProfileOut, tags=["setup"])
def get_profile(ctx: TenantContext = Depends(require(Action.VIEW_FIGURES))) -> ProfileOut:
    return _profile_out(ctx)


@router.put("/company/settings/profile", response_model=ProfileOut, tags=["setup"])
def put_profile(
    body: ProfileIn, ctx: TenantContext = Depends(require(Action.MANAGE_SETTINGS))
) -> ProfileOut:
    """The same settings the chat writes, changed directly (FR-4.11, FR-8.4)."""
    values: dict[str, Any] = {}
    if body.reporting_currency is not None:
        if body.reporting_currency not in chat.CURRENCIES:
            raise HTTPException(422, "Use a three-letter currency code such as GBP or EUR.")
        values["reporting_currency"] = body.reporting_currency
    if body.business_description is not None:
        values["business_description"] = body.business_description.strip() or None
    if body.website is not None:
        try:
            values["website"] = (
                service.website.normalise(body.website) if body.website.strip() else None
            )
        except service.website.WebsiteError as exc:
            raise HTTPException(422, str(exc)) from exc
    if body.follow_revenue:
        values["display_band"] = None
    elif body.display_band is not None:
        values["display_band"] = body.display_band
    if body.voice is not None:
        values["voice"] = body.voice
    service.apply_settings(ctx.session, ctx.tenant_id, ctx.user_id, values)
    return _profile_out(ctx)


@router.get("/company/settings/targets", response_model=list[TargetOut], tags=["setup"])
def get_targets(ctx: TenantContext = Depends(require(Action.VIEW_FIGURES))) -> list[TargetOut]:
    return [
        TargetOut(
            metric=t.metric,
            period=t.period,
            value=str(t.value),
            source=t.source,
            set_by_name=t.set_by_name,
        )
        for t in service.targets(ctx.session, ctx.tenant_id)
    ]


@router.put("/company/settings/targets", response_model=list[TargetOut], tags=["setup"])
def put_targets(
    body: list[TargetIn], ctx: TenantContext = Depends(require(Action.MANAGE_SETTINGS))
) -> list[TargetOut]:
    service.set_targets(
        ctx.session,
        ctx.tenant_id,
        ctx.user_id,
        [(t.metric, t.period, t.value) for t in body],
        "settings",
    )
    return get_targets(ctx)
