import re
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from boardroom.config import get_settings
from boardroom.gateway.deps import TenantContext, UserContext, current_user, require
from boardroom.modules.billing import payments, service
from boardroom.modules.identity import service as identity
from boardroom.modules.intake import service as intake
from boardroom.permissions import Action

router = APIRouter()


class Line(BaseModel):
    key: str
    label: str
    limit: int | None  # None is no limit
    used: int | None = None


class PlanOut(BaseModel):
    key: str
    name: str
    lines: list[Line]
    current: bool
    can_buy: bool


class BillingOut(BaseModel):
    plan_name: str | None
    status: str | None
    behaviour: Literal["warn", "block"]
    payment_ready: bool
    has_account: bool
    current_period_end: datetime | None
    lines: list[Line]
    plans: list[PlanOut]


class CheckoutIn(BaseModel):
    plan: str = Field(min_length=1, max_length=40)


class LinkOut(BaseModel):
    url: str


def _raise(exc: service.BillingError) -> HTTPException:
    return HTTPException(exc.code, exc.message)


def _lines(values: dict[str, int | None]) -> list[Line]:
    return [Line(key=k.key, label=k.label, limit=values[k.key]) for k in service.KEYS.values()]


@router.get("/company/billing", response_model=BillingOut, tags=["billing"])
def billing(ctx: TenantContext = Depends(require(Action.MANAGE_BILLING))) -> BillingOut:
    have = service.entitlements(ctx.session, ctx.tenant_id)
    used = {
        "viewers": identity.investor_seats(ctx.session, ctx.tenant_id),
        "uploads_per_month": intake.uploads_this_month(ctx.session, ctx.tenant_id),
    }
    lines = [line.model_copy(update={"used": used.get(line.key)}) for line in _lines(have.values)]
    current = have.plan.key if have.plan else None
    return BillingOut(
        plan_name=have.plan.name if have.plan else None,
        status=have.status,
        behaviour=get_settings().limit_behaviour,
        payment_ready=payments.ready(),
        has_account=have.has_account,
        current_period_end=have.current_period_end,
        lines=lines,
        plans=[
            PlanOut(
                key=p.key,
                name=p.name,
                lines=_lines(p.entitlements),
                current=p.key == current,
                can_buy=p.can_buy,
            )
            for p in service.plans(ctx.session)
            if p.available or p.key == current
        ],
    )


@router.post("/company/billing/checkout", response_model=LinkOut, tags=["billing"])
def checkout(
    body: CheckoutIn, ctx: TenantContext = Depends(require(Action.MANAGE_BILLING))
) -> LinkOut:
    person = identity.contact(ctx.session, ctx.user_id, ctx.tenant_id)
    if person is None:
        raise HTTPException(403, "You do not have access to this.")
    try:
        url = service.checkout(ctx.session, ctx.tenant_id, ctx.user_id, person.email, body.plan)
    except service.BillingError as exc:
        raise _raise(exc) from exc
    return LinkOut(url=url)


@router.post("/company/billing/portal", response_model=LinkOut, tags=["billing"])
def portal(ctx: TenantContext = Depends(require(Action.MANAGE_BILLING))) -> LinkOut:
    try:
        return LinkOut(url=service.portal(ctx.session, ctx.tenant_id, ctx.user_id))
    except service.BillingError as exc:
        raise _raise(exc) from exc


class WebhookOut(BaseModel):
    outcome: str


@router.post("/billing/stripe/webhook", response_model=WebhookOut, tags=["billing"])
async def stripe_webhook(request: Request) -> WebhookOut:
    """Public: Stripe signs each event, and the signature is checked before anything else."""
    payload = await request.body()
    signature = request.headers.get("Stripe-Signature")
    try:
        outcome = await run_in_threadpool(service.handle_webhook, payload, signature)
    except service.BillingError as exc:
        raise _raise(exc) from exc
    return WebhookOut(outcome=outcome)


# Platform admins only: the plans and the value of each key (FR-9.1).


class AdminPlanOut(BaseModel):
    key: str
    name: str
    entitlements: dict[str, int | None]
    stripe_price_id: str | None
    is_default: bool
    available: bool
    position: int


class AdminPlanIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    entitlements: dict[str, int | None] = Field(default_factory=dict)
    stripe_price_id: str | None = Field(default=None, max_length=100)
    is_default: bool = False
    available: bool = True
    position: int = 0


PLAN_KEY = re.compile(r"[a-z0-9_]{1,40}")


def _admin(ctx: UserContext) -> None:
    if not identity.is_platform_admin(ctx.session, ctx.user_id):
        raise HTTPException(403, "You do not have access to this.")


def _admin_out(p: service.PlanView) -> AdminPlanOut:
    return AdminPlanOut(
        key=p.key,
        name=p.name,
        entitlements=p.entitlements,
        stripe_price_id=p.stripe_price_id,
        is_default=p.is_default,
        available=p.available,
        position=p.position,
    )


@router.get("/admin/billing/plans", response_model=list[AdminPlanOut], tags=["admin"])
def admin_plans(ctx: UserContext = Depends(current_user)) -> list[AdminPlanOut]:
    _admin(ctx)
    return [_admin_out(p) for p in service.plans(ctx.session)]


@router.put("/admin/billing/plans/{key}", response_model=AdminPlanOut, tags=["admin"])
def admin_save_plan(
    key: str, body: AdminPlanIn, ctx: UserContext = Depends(current_user)
) -> AdminPlanOut:
    _admin(ctx)
    if not PLAN_KEY.fullmatch(key):
        raise HTTPException(422, "A plan key is lower-case letters, digits and underscores.")
    try:
        plan = service.save_plan(
            ctx.user_id,
            key,
            body.name,
            body.entitlements,
            body.stripe_price_id,
            body.is_default,
            body.available,
            body.position,
        )
    except service.BillingError as exc:
        raise _raise(exc) from exc
    return _admin_out(plan)
