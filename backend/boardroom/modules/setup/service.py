"""Setup conversations and the settings they write (FR-8.1 to 8.5, FR-4.11)."""

import io
import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from boardroom.config import get_settings
from boardroom.events import emit
from boardroom.logs import get_logger
from boardroom.modules.audit import service as audit
from boardroom.modules.identity import service as identity
from boardroom.modules.intake import service as intake
from boardroom.modules.intake.storage import get_storage
from boardroom.modules.setup import chat, website
from boardroom.modules.setup.models import (
    CompanyProfile,
    Conversation,
    Message,
    SetupOutbox,
    Target,
)
from boardroom.permissions import Role

log = get_logger(__name__)
SETTINGS_CHANGED = "setup.settings_changed"
SETUP_VERSION = "setup-chat/2026-10-18.1"


class SetupError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# Settings, read by the metrics module as br_system: every call names its tenant.


def profile(session: Session, tenant_id: uuid.UUID) -> CompanyProfile:
    found = session.scalar(select(CompanyProfile).where(CompanyProfile.tenant_id == tenant_id))
    if found is None:
        found = CompanyProfile(
            tenant_id=tenant_id, reporting_currency="GBP", revenue_lines=[], voice="we"
        )
        session.add(found)
        session.flush()
    return found


@dataclass(frozen=True)
class TargetView:
    id: uuid.UUID
    metric: str
    period: str
    value: Decimal
    source: str
    set_by_name: str
    updated_at: datetime


def targets(session: Session, tenant_id: uuid.UUID) -> list[TargetView]:
    rows = session.scalars(
        select(Target).where(Target.tenant_id == tenant_id).order_by(Target.metric, Target.period)
    ).all()
    return [
        TargetView(
            t.id, t.metric, t.period, Decimal(t.value), t.source, t.set_by_name, t.updated_at
        )
        for t in rows
    ]


def _changed(
    session: Session, tenant_id: uuid.UUID, actor: uuid.UUID | None, keys: list[str]
) -> None:
    audit.record(
        session,
        "setup.settings_changed",
        tenant_id=tenant_id,
        actor_user_id=actor,
        target_type="settings",
        details={"settings": keys},
    )
    emit(session, SetupOutbox, SETTINGS_CHANGED, tenant_id, {"settings": keys})


def apply_settings(
    session: Session, tenant_id: uuid.UUID, actor: uuid.UUID | None, values: dict[str, Any]
) -> list[str]:
    p = profile(session, tenant_id)
    changed = []
    for key, value in values.items():
        if getattr(p, key) != value:
            setattr(p, key, value)
            changed.append(key)
    if changed:
        session.flush()
        _changed(session, tenant_id, actor, changed)
    return changed


def set_targets(
    session: Session,
    tenant_id: uuid.UUID,
    actor: uuid.UUID,
    items: list[tuple[str, str, Decimal]],
    source: str,
) -> int:
    if not items:
        return 0
    user, _ = identity.me(session, actor)
    for metric, period, value in items:
        t = session.scalar(
            select(Target).where(
                Target.tenant_id == tenant_id, Target.metric == metric, Target.period == period
            )
        )
        if t is None:
            t = Target(tenant_id=tenant_id, metric=metric, period=period)
            session.add(t)
        t.value, t.source, t.set_by, t.set_by_name = str(value), source, actor, user.name
    session.flush()
    _changed(session, tenant_id, actor, ["targets"])
    return len(items)


# Facts


def gather_facts(
    session: Session,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    pending: list[str],
    read_site: bool = True,
) -> chat.Facts:
    from boardroom.modules.metrics import service as metrics  # metrics also reads setup

    p = profile(session, tenant_id)
    company = identity.get_company(session, tenant_id)
    seen = intake.currencies_seen(session, tenant_id)
    currency, currency_from = p.reporting_currency, "set by the company"
    untouched = p.reporting_currency == "GBP"
    if seen and untouched:
        currency, currency_from = (
            max(seen, key=lambda c: seen[c]),
            "most common currency in your files",
        )
    elif untouched:
        currency_from = "default, no currency in your files yet"

    site, text, error = p.website, None, None
    if site is None:
        user, _ = identity.me(session, user_id)
        site = website.guess_from_email(user.email)
    if site and read_site:
        try:
            text = website.fetch(site)
        except Exception as exc:  # a website is a nice-to-have: never let it stop setup
            error = str(exc)[:200] if isinstance(exc, website.WebsiteError) else "could not be read"
            log.info("website_not_read", reason=type(exc).__name__)

    run = metrics.latest_run(session, tenant_id)
    datasets = intake.datasets_for_metrics(session, tenant_id)
    budget = [
        {
            "metric": str(r.get("metric")),
            "period": str(r.get("period")),
            "value": str(r.get("target_value")),
        }
        for d in datasets
        if d.kind == "plan"
        for _, r in d.rows
    ][:60]
    settings_targets = [
        {"metric": t.metric, "period": t.period, "value": str(t.value)}
        for t in targets(session, tenant_id)
    ]
    settings_targets += [
        {"metric": m.metric, "period": m.period, "value": str(m.value)}
        for m in intake.manual_figures_for(session, tenant_id)
        if m.kind == "target"
    ]
    facts = chat.Facts(
        company_name=company.name,
        currency=currency,
        currency_from=currency_from,
        currencies_seen=seen,
        website=site,
        website_text=text,
        website_error=error,
        description=p.business_description,
        revenue_lines=list(p.revenue_lines or []),
        pnl_line_items=intake.pnl_labels(session, tenant_id),
        annual_revenue=run.annual_revenue if run else None,
        band=p.display_band if p.display_band is not None else (run.band if run else 0),
        band_fixed=p.display_band is not None,
        budget_targets=budget,
        settings_targets=settings_targets,
        file_kinds=sorted({d.kind for d in datasets}),
        investor_count=len(identity.investor_emails(session, tenant_id)),
        pending_invites=pending,
    )
    facts.questions = chat.needed_questions(facts)
    return facts


# The conversation


class Client:
    model: str

    def interpret(self, payload: dict[str, Any]) -> Any: ...


_override: Any = None


def set_client(client: Any) -> None:
    global _override
    _override = client


def get_client() -> Any:
    if _override is not None:
        return _override
    s = get_settings()
    if not s.ai_enabled or not s.anthropic_api_key or s.skill1_replay_dir:
        return None
    from boardroom.modules.intake.skill1 import AnthropicClient

    return AnthropicClient(schema=chat.OUTPUT_SCHEMA, model=s.setup_model)


def conversation(session: Session, tenant_id: uuid.UUID) -> Conversation | None:
    return session.scalar(
        select(Conversation)
        .where(Conversation.tenant_id == tenant_id)
        .order_by(Conversation.created_at.desc())
        .limit(1)
    )


def messages(session: Session, conv: Conversation) -> list[Message]:
    return list(
        session.scalars(
            select(Message)
            .where(Message.conversation_id == conv.id, Message.tenant_id == conv.tenant_id)
            .order_by(Message.seq)
        ).all()
    )


def _ask_model(
    facts: chat.Facts, history: list[tuple[str, str]], ceo_text: str | None, all_ceo_text: str
) -> tuple[chat.Proposal | None, str]:
    client = get_client()
    if client is None:
        return None, "AI switched off"
    from boardroom.modules.intake.skill1 import SkillOutputError, SkillUnavailable

    try:
        raw = client.interpret(chat.build_payload(facts, history, ceo_text))
        return chat.validate(raw, facts, all_ceo_text, first=ceo_text is None), ""
    except (SkillUnavailable, SkillOutputError, chat.SetupOutputError) as exc:
        return None, f"{type(exc).__name__}: {exc}"


def _record(
    session: Session,
    conv: Conversation,
    role: str,
    content: str,
    author: uuid.UUID | None,
    applied: dict[str, Any] | None = None,
    source: str = "ai",
) -> Message:
    last = session.scalar(select(func.max(Message.seq)).where(Message.conversation_id == conv.id))
    m = Message(
        tenant_id=conv.tenant_id,
        conversation_id=conv.id,
        seq=(last or 0) + 1,
        role=role,
        content=content,
        author_id=author,
        applied=applied or {},
        source=source,
    )
    session.add(m)
    session.flush()
    return m


def _first_name(session: Session, user_id: uuid.UUID) -> str:
    user, _ = identity.me(session, user_id)
    return (user.name or "").split(" ")[0]


def _interview(facts: chat.Facts, remaining: list[str]) -> None:
    facts.ask_now = remaining[0] if remaining else None
    facts.ask_next = remaining[1] if len(remaining) > 1 else None


def start(session: Session, tenant_id: uuid.UUID, user_id: uuid.UUID) -> Conversation:
    """Opens the interview: a greeting and the first question, with the rest worked out
    from the files and shown in the summary card (FR-8.1, FR-8.2, FR-8.3)."""
    conv = conversation(session, tenant_id)
    if conv is not None and conv.status == "open":
        return conv
    returning = conv is not None and bool(messages(session, conv))
    if conv is None:
        conv = Conversation(tenant_id=tenant_id, status="open", pending_invites=[])
        session.add(conv)
    conv.status = "open"
    facts = gather_facts(session, tenant_id, user_id, list(conv.pending_invites or []))
    facts.first_name = _first_name(session, user_id)
    conv.questions, conv.answered = list(facts.questions), []
    session.flush()
    if returning:
        _record(session, conv, "assistant", chat.welcome_back(facts), None, {}, "template")
        audit.record(session, "setup.reopened", tenant_id=tenant_id, actor_user_id=user_id)
        return conv

    if not facts.description and facts.website_text:
        # A first guess at what the business does, from the website, until the CEO says otherwise.
        facts.description = facts.website_text[:200].rsplit(" ", 1)[0]
    _interview(facts, facts.questions)
    proposal, why = _ask_model(facts, [], None, "")
    values: dict[str, Any]
    if proposal is not None:
        reply, values, source = proposal.reply, proposal.settings, "ai"
    else:
        reply, values, source = chat.opening(facts), {}, "template"
        if facts.description:
            values["business_description"] = facts.description
        log.info("setup_template", reason=why[:100])
    if facts.currency != profile(session, tenant_id).reporting_currency:
        values.setdefault("reporting_currency", facts.currency)
    changed = apply_settings(session, tenant_id, user_id, values)
    if not facts.questions:
        conv.status = "done"
    _record(
        session,
        conv,
        "assistant",
        reply,
        None,
        {"settings": changed, "asked": facts.ask_now},
        source,
    )
    audit.record(session, "setup.started", tenant_id=tenant_id, actor_user_id=user_id)
    return conv


SKIP = {"skip", "skip this", "skip for now", "skip it"}


def send(session: Session, tenant_id: uuid.UUID, user_id: uuid.UUID, text: str) -> Conversation:
    """One answer in, one acknowledgement and at most one question out."""
    conv = conversation(session, tenant_id)
    if conv is None or not messages(session, conv):
        conv = start(session, tenant_id, user_id)
    conv.status = "open"
    history = [(m.role, m.content) for m in messages(session, conv)]
    _record(session, conv, "user", text, user_id)
    audit.record(session, "setup.message_sent", tenant_id=tenant_id, actor_user_id=user_id)
    all_ceo = "\n".join([t for r, t in history if r == "user"] + [text])
    # The website is read when the chat opens, or again when the CEO gives a new one.
    read_site = "http" in text or "www." in text or ".co" in text
    facts = gather_facts(session, tenant_id, user_id, list(conv.pending_invites or []), read_site)
    facts.first_name = _first_name(session, user_id)
    # Questions still to ask: planned when the interview opened, not yet answered, and
    # still needed (a target set in settings meanwhile ends the targets question).
    remaining = [
        q for q in conv.questions or [] if q not in (conv.answered or []) and q in facts.questions
    ]
    current = remaining[0] if remaining else None
    _interview(facts, remaining)

    # Skip is a button, so it never needs the model.
    proposal, why = (
        (None, "skipped") if text.lower() in SKIP else _ask_model(facts, history, text, all_ceo)
    )
    if proposal is not None:
        settings, targets, emails = proposal.settings, proposal.targets, proposal.investor_emails
        answered, reply, source = proposal.answered, proposal.reply, "ai"
    else:
        reading = chat.read_answer(text, current, facts.currency)
        if text.lower() in SKIP:
            reading = chat.Reading(True, "No problem.")
        settings, targets, emails = reading.settings, reading.targets, reading.emails
        answered, source = reading.answered, "template"
        left = remaining[1:] if answered else remaining
        if answered:
            reply = f"{reading.ack} {chat.next_line(left)}"
        elif reading.ack:
            reply = f"{reading.ack} {chat.QUESTIONS[current]}" if current else reading.ack
        elif current:
            reply = f"Sorry, I didn't follow that. {chat.QUESTIONS[current]}"
        else:
            reply = "Sorry, I didn't follow that. Try saying it another way, or use Settings."
        if why not in ("AI switched off", "skipped"):
            log.info("setup_template", reason=why[:100])

    changed = apply_settings(session, tenant_id, user_id, settings)
    count = set_targets(session, tenant_id, user_id, targets, "chat")
    known = set(identity.investor_emails(session, tenant_id))
    new_invites = [e for e in emails if e not in known]
    if new_invites:
        conv.pending_invites = sorted(set(conv.pending_invites or []) | set(new_invites))
    if answered and current:
        conv.answered = [*(conv.answered or []), current]
        remaining = remaining[1:]
    if not remaining:
        conv.status = "done"
    _record(
        session,
        conv,
        "assistant",
        reply,
        None,
        {
            "settings": changed,
            "targets": count,
            "invites_waiting": new_invites,
            "answered": current if answered else None,
            **({"error": why[:200]} if proposal is None and why else {}),
        },
        source,
    )
    return conv


def summary(
    session: Session, tenant_id: uuid.UUID, user_id: uuid.UUID
) -> tuple[list[tuple[str, str]], bool]:
    """The "Set up for you" card: what setup worked out or was told, in plain words, and
    whether any file has been added yet."""
    conv = conversation(session, tenant_id)
    pending = list(conv.pending_invites or []) if conv else []
    facts = gather_facts(session, tenant_id, user_id, pending, read_site=False)
    p = profile(session, tenant_id)
    rows = [
        ("Reporting currency", p.reporting_currency),
        ("What you do", p.business_description or "Not known yet"),
        ("Revenue lines", ", ".join(p.revenue_lines or []) or "Revenue"),
    ]
    revenue = [t for t in targets(session, tenant_id) if t.metric == "revenue"]
    if revenue:
        values = {t.value for t in revenue}
        span = chat.month_span(revenue[0].period, revenue[-1].period)
        target = (
            f"{chat.short(revenue[0].value, p.reporting_currency)} a month, {span}"
            if len(values) == 1
            else f"{len(revenue)} months set, {span}"
        )
    elif facts.budget_targets:
        target = f"From your budget file, {len(facts.budget_targets)} lines"
    else:
        target = "None yet"
    rows.append(("Revenue target", target))
    if pending:
        investors = f"{len(pending)} waiting for you to confirm"
    elif facts.investor_count:
        investors = f"{facts.investor_count} invited"
    else:
        investors = "None yet"
    rows.append(("Investors", investors))
    # The band's example amount is left out of the card, where it could read as a figure.
    band = chat.BAND_WORDS[facts.band].split(" (")[0]
    rows.append(("Money shown in", band[0].upper() + band[1:]))
    return rows, bool(facts.file_kinds)


def skip(session: Session, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Defaults stay in place, and the chat can be reopened later (FR-8.4)."""
    conv = conversation(session, tenant_id)
    if conv is None:
        conv = Conversation(tenant_id=tenant_id, status="skipped", pending_invites=[])
        session.add(conv)
    conv.status = "skipped"
    session.flush()
    audit.record(session, "setup.skipped", tenant_id=tenant_id, actor_user_id=user_id)


def send_invites(
    session: Session, tenant_id: uuid.UUID, user_id: uuid.UUID, role: Role
) -> list[str]:
    """The CEO confirms before anyone is emailed."""
    conv = conversation(session, tenant_id)
    if conv is None or not conv.pending_invites:
        raise SetupError(409, "There are no invitations waiting.")
    sent = []
    for email in conv.pending_invites:
        try:
            identity.create_invitation(session, tenant_id, user_id, role, email, Role.INVESTOR, [])
            sent.append(email)
        except identity.IdentityError:
            continue
    conv.pending_invites = []
    session.flush()
    audit.record(
        session,
        "setup.invites_sent",
        tenant_id=tenant_id,
        actor_user_id=user_id,
        details={"count": len(sent)},
    )
    return sent


def discard_invites(session: Session, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
    conv = conversation(session, tenant_id)
    if conv is not None:
        conv.pending_invites = []
        session.flush()
    audit.record(session, "setup.invites_discarded", tenant_id=tenant_id, actor_user_id=user_id)


# The company's logo and colour, for exports (FR-6.6)

LOGO_MAX_BYTES = 512 * 1024
LOGO_MAX_PIXELS = 4096 * 4096
LOGO_SIDE = 600


def _logo_key(tenant_id: uuid.UUID) -> str:
    return f"tenants/{tenant_id}/branding/logo.png"


def set_logo(session: Session, tenant_id: uuid.UUID, actor: uuid.UUID, data: bytes) -> None:
    """A PNG or JPEG, checked and redrawn as a small PNG, so nothing else in the file
    (metadata, a second image, a script) is kept."""
    from PIL import Image, UnidentifiedImageError

    if len(data) > LOGO_MAX_BYTES:
        raise SetupError(422, "Use a logo under 512 KB.")
    try:
        with Image.open(io.BytesIO(data)) as probe:
            if probe.format not in ("PNG", "JPEG"):
                raise SetupError(422, "Use a PNG or JPEG logo.")
            if probe.width * probe.height > LOGO_MAX_PIXELS:
                raise SetupError(422, "Use a smaller logo, at most 4096 pixels a side.")
            probe.verify()
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            clean = image.convert("RGBA")
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise SetupError(422, "That file is not a logo we can read. Use a PNG or JPEG.") from exc
    clean.thumbnail((LOGO_SIDE, LOGO_SIDE))
    out = io.BytesIO()
    clean.save(out, format="PNG", optimize=True)
    get_storage().put(_logo_key(tenant_id), out.getvalue())
    p = profile(session, tenant_id)
    p.logo_key = _logo_key(tenant_id)
    session.flush()
    audit.record(session, "setup.logo_changed", tenant_id=tenant_id, actor_user_id=actor)


def delete_logo(session: Session, tenant_id: uuid.UUID, actor: uuid.UUID) -> None:
    p = profile(session, tenant_id)
    if p.logo_key:
        get_storage().delete(p.logo_key)
        p.logo_key = None
        session.flush()
    audit.record(session, "setup.logo_removed", tenant_id=tenant_id, actor_user_id=actor)


def branding(session: Session, tenant_id: uuid.UUID) -> tuple[str | None, bytes | None]:
    """The colour and logo. Read only: an investor exporting an update creates nothing."""
    row = session.execute(
        select(CompanyProfile.brand_colour, CompanyProfile.logo_key).where(
            CompanyProfile.tenant_id == tenant_id
        )
    ).first()
    if row is None:
        return None, None
    return row.brand_colour, get_storage().get(row.logo_key) if row.logo_key else None
