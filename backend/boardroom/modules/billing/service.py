"""Entitlements and payment (FRD chapter 9).

Each limit is a named key whose value lives in the plan's row, so changing it changes
behaviour with no deploy (FR-9.1). Each module checks its own key where the action happens.
What happens at a limit, warn or block, is a setting until it is decided (FR-9.4).
Approval never looks at the plan (FR-9.3).
"""

import json
import math
import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import stripe
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from boardroom.config import get_settings
from boardroom.db import system_session
from boardroom.modules.audit import service as audit
from boardroom.modules.billing.models import Plan, StripeEvent, Subscription
from boardroom.modules.billing.payments import PaymentsUnavailable, get_payments


class BillingError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Key:
    key: str
    label: str
    # How the limit reads in a sentence, for one and for any other number:
    # "Your plan includes 1 investor." and "Your plan includes 3 investors."
    one: str
    many: str

    def sentence(self, n: int) -> str:
        return (self.one if n == 1 else self.many).format(n=n)


KEYS: dict[str, Key] = {
    k.key: k
    for k in (
        Key(
            "viewers",
            "Investors, joined or invited",
            "Your plan includes {n} investor.",
            "Your plan includes {n} investors.",
        ),
        Key(
            "uploads_per_month",
            "Files added this month",
            "Your plan includes {n} file a month.",
            "Your plan includes {n} files a month.",
        ),
        Key(
            "max_file_mb",
            "Largest file",
            "Your plan accepts files up to {n} MB.",
            "Your plan accepts files up to {n} MB.",
        ),
    )
}

# Stripe statuses in which the company has the plan it pays for. Any other status, or no
# subscription, falls back to the default plan.
LIVE = frozenset({"active", "trialing", "past_due"})

MB = 1024 * 1024

STRIPE_DOWN = "Stripe did not answer as expected. Nothing was charged. Try again in a moment."


def megabytes(size_bytes: int) -> int:
    return max(1, math.ceil(size_bytes / MB))


# Plans


@dataclass(frozen=True)
class PlanView:
    key: str
    name: str
    entitlements: dict[str, int | None]
    is_default: bool
    available: bool
    can_buy: bool
    position: int
    stripe_price_id: str | None


def _view(plan: Plan) -> PlanView:
    return PlanView(
        key=plan.key,
        name=plan.name,
        entitlements={k: plan.entitlements.get(k) for k in KEYS},
        is_default=plan.is_default,
        available=plan.available,
        can_buy=plan.available and bool(plan.stripe_price_id),
        position=plan.position,
        stripe_price_id=plan.stripe_price_id,
    )


def plans(session: Session) -> list[PlanView]:
    rows = session.scalars(select(Plan).order_by(Plan.position, Plan.key)).all()
    return [_view(p) for p in rows]


def _clean(entitlements: dict[str, Any]) -> dict[str, int | None]:
    unknown = set(entitlements) - set(KEYS)
    if unknown:
        raise BillingError(422, f"Unknown keys: {', '.join(sorted(unknown))}.")
    out: dict[str, int | None] = {}
    for k, v in entitlements.items():
        if v is not None and (isinstance(v, bool) or not isinstance(v, int) or v < 0):
            raise BillingError(422, f"{k} must be a whole number of 0 or more, or empty.")
        out[k] = v
    return out


def save_plan(
    actor: uuid.UUID,
    key: str,
    name: str,
    entitlements: dict[str, Any],
    stripe_price_id: str | None,
    is_default: bool,
    available: bool,
    position: int,
) -> PlanView:
    """A platform admin sets a plan. Takes effect on the next request (FR-9.1)."""
    values = _clean(entitlements)
    with system_session() as session:
        if is_default:
            session.execute(
                update(Plan).where(Plan.is_default, Plan.key != key).values(is_default=False)
            )
        plan = session.get(Plan, key) or Plan(key=key)
        plan.name = name
        plan.entitlements = values
        plan.stripe_price_id = stripe_price_id or None
        plan.is_default = is_default
        plan.available = available
        plan.position = position
        session.add(plan)
        session.flush()
        audit.record(
            session,
            "billing.plan_saved",
            tenant_id=None,
            actor_user_id=actor,
            target_type="plan",
            target_id=key,
            details={"entitlements": values, "is_default": is_default},
        )
        return _view(plan)


# What a company has


@dataclass(frozen=True)
class Entitlements:
    plan: PlanView | None
    status: str | None
    has_account: bool
    values: dict[str, int | None]
    current_period_end: datetime | None


def entitlements(session: Session, tenant_id: uuid.UUID) -> Entitlements:
    sub = session.get(Subscription, tenant_id)
    plan = None
    if sub is not None and sub.status in LIVE and sub.plan_key:
        plan = session.get(Plan, sub.plan_key)
    if plan is None:
        plan = session.scalar(select(Plan).where(Plan.is_default))
    view = _view(plan) if plan is not None else None
    return Entitlements(
        plan=view,
        status=sub.status if sub else None,
        has_account=bool(sub and sub.stripe_customer_id),
        values=view.entitlements if view else dict.fromkeys(KEYS),
        current_period_end=sub.current_period_end if sub else None,
    )


# Checking a limit at the point of use

_warnings: ContextVar[list[str] | None] = ContextVar("limit_warnings", default=None)


def start_request() -> None:
    _warnings.set([])


def take_warnings() -> list[str]:
    found = _warnings.get() or []
    _warnings.set([])
    return found


class LimitReached(BillingError):
    def __init__(self, message: str) -> None:
        super().__init__(402, message)


def check(
    session: Session, tenant_id: uuid.UUID, actor: uuid.UUID | None, key: str, wanted: int
) -> None:
    """``wanted`` is what the action would bring the key to: the fourth investor is 4."""
    limit = entitlements(session, tenant_id).values[key]
    if limit is None or wanted <= limit:
        return
    sentence = KEYS[key].sentence(limit)
    if get_settings().limit_behaviour == "block":
        raise LimitReached(f"{sentence} The Owner or CEO can change the plan in Settings.")
    audit.record(
        session,
        "billing.limit_passed",
        tenant_id=tenant_id,
        actor_user_id=actor,
        details={"key": key, "limit": limit, "wanted": wanted},
    )
    found = _warnings.get()
    if found is not None:
        found.append(f"{sentence} This went through. The Owner or CEO can change the plan.")


# Checkout and the portal (FR-9.2)


def _settings_url(tenant_id: uuid.UUID, outcome: str | None = None) -> str:
    url = f"{get_settings().web_origin}/c/{tenant_id}/settings"
    return f"{url}?billing={outcome}" if outcome else url


def checkout(
    session: Session, tenant_id: uuid.UUID, actor: uuid.UUID, email: str, plan_key: str
) -> str:
    plan = session.get(Plan, plan_key)
    if plan is None or not plan.available or not plan.stripe_price_id:
        raise BillingError(404, "That plan is not available.")
    sub = session.get(Subscription, tenant_id)
    if sub is not None and sub.status in LIVE and sub.stripe_subscription_id:
        raise BillingError(409, "This company already has a plan. Change it in Manage billing.")
    try:
        url = get_payments().checkout_url(
            tenant_id=tenant_id,
            price_id=plan.stripe_price_id,
            customer_id=sub.stripe_customer_id if sub else None,
            email=email,
            success_url=_settings_url(tenant_id, "done"),
            cancel_url=_settings_url(tenant_id, "cancelled"),
        )
    except PaymentsUnavailable as exc:
        raise BillingError(503, str(exc)) from exc
    except stripe.StripeError as exc:
        raise BillingError(502, STRIPE_DOWN) from exc
    audit.record(
        session,
        "billing.checkout_started",
        tenant_id=tenant_id,
        actor_user_id=actor,
        target_type="plan",
        target_id=plan_key,
    )
    return url


def portal(session: Session, tenant_id: uuid.UUID, actor: uuid.UUID) -> str:
    sub = session.get(Subscription, tenant_id)
    if sub is None or not sub.stripe_customer_id:
        raise BillingError(404, "There is no billing account yet. Choose a plan first.")
    try:
        url = get_payments().portal_url(
            customer_id=sub.stripe_customer_id, return_url=_settings_url(tenant_id)
        )
    except PaymentsUnavailable as exc:
        raise BillingError(503, str(exc)) from exc
    except stripe.StripeError as exc:
        raise BillingError(502, STRIPE_DOWN) from exc
    audit.record(session, "billing.portal_opened", tenant_id=tenant_id, actor_user_id=actor)
    return url


# The webhook (FR-9.2): signed by Stripe, applied once per event id.

SUBSCRIPTION_EVENTS = frozenset(
    {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }
)


def handle_webhook(payload: bytes, signature: str | None) -> str:
    secret = get_settings().stripe_webhook_secret
    if not secret:
        raise BillingError(503, "Payment is not set up yet.")
    try:
        stripe.WebhookSignature.verify_header(payload.decode(), signature, secret, tolerance=300)
    except (stripe.SignatureVerificationError, UnicodeDecodeError) as exc:
        raise BillingError(400, "The signature does not match.") from exc
    event = json.loads(payload)
    with system_session() as session:
        # Taking the id first makes a replay, or two deliveries at once, a no-op.
        taken = session.execute(
            insert(StripeEvent)
            .values(id=event["id"], event_type=event["type"], outcome="received")
            .on_conflict_do_nothing(index_elements=["id"])
            .returning(StripeEvent.id)
        ).first()
        if taken is None:
            return "duplicate"
        tenant_id, outcome = _apply(session, event)
        session.execute(
            update(StripeEvent)
            .where(StripeEvent.id == event["id"])
            .values(tenant_id=tenant_id, outcome=outcome)
        )
        return outcome


def _tenant(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


def _apply(session: Session, event: dict[str, Any]) -> tuple[uuid.UUID | None, str]:
    obj = event["data"]["object"]
    if event["type"] == "checkout.session.completed" and obj.get("mode") == "subscription":
        tenant_id = _tenant(obj.get("client_reference_id"))
        if tenant_id is None:
            return None, "ignored"
        ids = session.get(Subscription, tenant_id) or Subscription(
            tenant_id=tenant_id, status="incomplete"
        )
        # Only the ids: the subscription events carry the plan and status, in any order.
        ids.stripe_customer_id = obj.get("customer") or ids.stripe_customer_id
        ids.stripe_subscription_id = obj.get("subscription") or ids.stripe_subscription_id
        session.add(ids)
        return tenant_id, "applied"
    if event["type"] not in SUBSCRIPTION_EVENTS:
        return None, "ignored"

    sub = _find(session, obj)
    if sub is None:
        return None, "ignored"
    created = datetime.fromtimestamp(event["created"], UTC)
    if sub.last_event_at is not None and created < sub.last_event_at:
        return sub.tenant_id, "stale"
    items = (obj.get("items") or {}).get("data") or [{}]
    price_id = (items[0].get("price") or {}).get("id")
    plan = session.scalar(select(Plan).where(Plan.stripe_price_id == price_id))
    period_end = items[0].get("current_period_end") or obj.get("current_period_end")
    sub.plan_key = plan.key if plan else None
    sub.status = "canceled" if event["type"].endswith(".deleted") else obj["status"]
    sub.stripe_subscription_id = obj["id"]
    sub.stripe_customer_id = obj.get("customer") or sub.stripe_customer_id
    sub.current_period_end = datetime.fromtimestamp(period_end, UTC) if period_end else None
    sub.last_event_at = created
    session.add(sub)
    audit.record(
        session,
        "billing.subscription_changed",
        tenant_id=sub.tenant_id,
        actor_user_id=None,
        target_type="subscription",
        target_id=obj["id"],
        details={"plan": sub.plan_key, "status": sub.status},
    )
    return sub.tenant_id, "applied"


def _find(session: Session, obj: dict[str, Any]) -> Subscription | None:
    tenant_id = _tenant((obj.get("metadata") or {}).get("tenant_id"))
    if tenant_id is not None:
        return session.get(Subscription, tenant_id) or Subscription(
            tenant_id=tenant_id, status="incomplete"
        )
    return session.scalar(
        select(Subscription).where(Subscription.stripe_subscription_id == obj["id"])
    )
