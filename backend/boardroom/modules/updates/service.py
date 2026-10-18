"""Updates, approvals and comments (FRD chapter 6, FR-3.3, FR-3.4).

An update is a dated line: who added what, and when the data is true as of. It is made by
code when an upload is ready, waits for an approver, then reaches every investor. It can be
edited after that and then shows "Last edited". There are no draft states, no locks and no
versions: the audit log keeps who changed what, before and after.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from boardroom.config import get_settings
from boardroom.events import Event, consumer, emit
from boardroom.modules.audit import service as audit
from boardroom.modules.identity import service as identity
from boardroom.modules.intake import service as intake
from boardroom.modules.metrics import service as metrics
from boardroom.modules.setup import service as setup
from boardroom.modules.updates import pdf
from boardroom.modules.updates.models import Comment, Update, UpdateFigure, UpdatesOutbox
from boardroom.permissions import Role

CREATED = "updates.created"
SHARED = "updates.shared"
COMMENTED = "updates.comment_added"

DEPARTMENT_WORDS = {
    "finance": "financials",
    "sales": "sales figures",
    "plan": "plan",
    "delivery": "delivery figures",
    "people": "people figures",
}
ROLE_WORDS = {
    "owner": "Owner",
    "ceo": "CEO",
    "department_lead": "Department lead",
    "contributor": "Contributor",
    "investor": "Investor",
}
PHASE_2_KINDS = {"delivery": "product_delivery", "people": "people"}


class UpdatesError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _now() -> datetime:
    return datetime.now(UTC)


def day(d: date | datetime) -> str:
    """17 Oct 2026."""
    return f"{d.day} {d:%b %Y}"


def headline(u: Update) -> str:
    who = f"{ROLE_WORDS.get(u.added_by_role, u.added_by_role)} {u.added_by_name}"
    return f"{who} added new {DEPARTMENT_WORDS.get(u.department, u.department)}"


def detail(u: Update) -> str:
    return f"Data true as of {day(u.data_as_of)}. Subject to change and may be edited."


def dated_line(u: Update) -> str:
    """The line in FR-3.4."""
    return f"{headline(u)}. {detail(u)}"


# Making an update from a finished upload (FR-6.1). Runs as br_system in the dispatcher,
# so every query names the tenant.


def create_from_upload(
    session: Session, tenant_id: uuid.UUID, upload_id: uuid.UUID
) -> Update | None:
    existing = session.scalar(
        select(Update).where(Update.tenant_id == tenant_id, Update.upload_id == upload_id)
    )
    if existing is not None:
        return existing
    upload = intake.finished_upload(session, tenant_id, upload_id)
    if upload is None or upload.dataset_id is None or upload.file_kind is None:
        return None
    flag = PHASE_2_KINDS.get(upload.file_kind)
    if flag and not getattr(get_settings().flags, flag):
        return None  # these figures arrive in phase 2, so there is nothing to share yet
    run_id = metrics.run_for_upload(session, tenant_id, upload_id)
    if run_id is None:
        return None
    person = identity.contact(session, upload.uploaded_by, tenant_id)
    membership = identity.active_membership(session, upload.uploaded_by, tenant_id)
    as_of = upload.data_as_of
    if get_settings().update_as_of == "upload" or as_of is None:
        as_of = upload.created_at.date()
    update = Update(
        tenant_id=tenant_id,
        upload_id=upload_id,
        run_id=run_id,
        added_by=upload.uploaded_by,
        added_by_name=person.name if person else "A former member",
        added_by_role=membership.role.value if membership else "contributor",
        department=upload.file_kind,
        data_as_of=as_of,
        status="awaiting_approval",
    )
    session.add(update)
    session.flush()
    for position, figure_id in enumerate(
        metrics.figures_from_dataset(session, tenant_id, run_id, upload.dataset_id)
    ):
        view = metrics.figure_view(session, tenant_id, figure_id)
        assert view is not None  # noqa: S101
        session.add(
            UpdateFigure(
                tenant_id=tenant_id,
                update_id=update.id,
                figure_id=figure_id,
                metric=view.metric,
                period=view.period,
                position=position,
            )
        )
    session.flush()
    audit.record(
        session,
        "update.created",
        tenant_id=tenant_id,
        actor_user_id=None,
        target_type="update",
        target_id=update.id,
        details={"upload_id": str(upload_id)},
    )
    emit(
        session,
        UpdatesOutbox,
        CREATED,
        tenant_id,
        {"update_id": str(update.id), "added_by": str(update.added_by)},
    )
    return update


@consumer("updates.create", "intake.upload_status_changed")
def _create(session: Session, event: Event) -> None:
    if event.payload.get("status") != "ready" or event.tenant_id is None:
        return
    create_from_upload(session, event.tenant_id, uuid.UUID(event.payload["upload_id"]))


# Reading


@dataclass(frozen=True)
class FigureOut:
    figure_id: uuid.UUID
    metric: str
    label: str
    unit: str
    period: str
    display: str
    source_line: str
    risk: str | None
    # Set when a person changed the figure in this update.
    calculated_display: str | None
    edited_by_name: str | None
    edited_at: datetime | None


@dataclass(frozen=True)
class CommentOut:
    id: uuid.UUID
    author_name: str
    author_role: str
    body: str
    created_at: datetime
    mine: bool


@dataclass(frozen=True)
class UpdateOut:
    id: uuid.UUID
    headline: str
    detail: str
    department: str
    data_as_of: date
    status: str
    created_at: datetime
    approved_by_name: str | None
    approved_at: datetime | None
    last_edited_by_name: str | None
    last_edited_at: datetime | None
    figures: list[FigureOut]
    comments: list[CommentOut]
    can_edit: bool
    can_approve: bool


def can_edit(role: Role, departments: list[str], department: str) -> bool:
    """Owner and CEO edit any update, a department lead their own sections (FRD ch. 2)."""
    if role in (Role.OWNER, Role.CEO):
        return True
    return role == Role.DEPARTMENT_LEAD and department in departments


def _get(session: Session, tenant_id: uuid.UUID, role: Role, update_id: uuid.UUID) -> Update:
    query = select(Update).where(Update.tenant_id == tenant_id, Update.id == update_id)
    if role == Role.INVESTOR:
        # Row-level security hides these too. Investors see shared updates only (FR-3.3).
        query = query.where(Update.status == "shared")
    found = session.scalar(query)
    if found is None:
        raise UpdatesError(404, "That update was not found.")
    return found


def _figures(session: Session, tenant_id: uuid.UUID, update_id: uuid.UUID) -> list[FigureOut]:
    out = []
    for f in session.scalars(
        select(UpdateFigure)
        .where(UpdateFigure.tenant_id == tenant_id, UpdateFigure.update_id == update_id)
        .order_by(UpdateFigure.position)
    ):
        calculated = metrics.figure_view(session, tenant_id, f.figure_id)
        if calculated is None:
            continue
        shown = calculated
        if f.edited_value is not None:
            edited = metrics.figure_view(session, tenant_id, f.figure_id, Decimal(f.edited_value))
            assert edited is not None  # noqa: S101
            shown = edited
        out.append(
            FigureOut(
                f.figure_id,
                shown.metric,
                shown.label,
                shown.unit,
                shown.period,
                shown.display,
                calculated.source_line,
                calculated.risk,
                calculated.display if f.edited_value is not None else None,
                f.edited_by_name if f.edited_value is not None else None,
                f.edited_at if f.edited_value is not None else None,
            )
        )
    return out


def _comments(
    session: Session, tenant_id: uuid.UUID, update_id: uuid.UUID, user_id: uuid.UUID
) -> list[CommentOut]:
    return [
        CommentOut(c.id, c.author_name, c.author_role, c.body, c.created_at, c.author_id == user_id)
        for c in session.scalars(
            select(Comment)
            .where(Comment.tenant_id == tenant_id, Comment.update_id == update_id)
            .order_by(Comment.created_at, Comment.id)
        )
    ]


def _out(
    session: Session,
    u: Update,
    user_id: uuid.UUID,
    role: Role,
    departments: list[str],
    approver: bool,
) -> UpdateOut:
    return UpdateOut(
        id=u.id,
        headline=headline(u),
        detail=detail(u),
        department=u.department,
        data_as_of=u.data_as_of,
        status=u.status,
        created_at=u.created_at,
        approved_by_name=u.approved_by_name,
        approved_at=u.approved_at,
        last_edited_by_name=u.last_edited_by_name,
        last_edited_at=u.last_edited_at,
        figures=_figures(session, u.tenant_id, u.id),
        comments=_comments(session, u.tenant_id, u.id, user_id),
        can_edit=can_edit(role, departments, u.department),
        can_approve=approver and u.status == "awaiting_approval",
    )


def list_updates(
    session: Session,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    role: Role,
    departments: list[str],
    limit: int = 20,
) -> list[UpdateOut]:
    query = select(Update).where(Update.tenant_id == tenant_id)
    if role == Role.INVESTOR:
        query = query.where(Update.status == "shared")
    approver = role != Role.INVESTOR and identity.user_can_approve(session, user_id, role)
    return [
        _out(session, u, user_id, role, departments, approver)
        for u in session.scalars(query.order_by(Update.created_at.desc()).limit(limit))
    ]


def get_update(
    session: Session,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    role: Role,
    departments: list[str],
    update_id: uuid.UUID,
) -> UpdateOut:
    u = _get(session, tenant_id, role, update_id)
    approver = role != Role.INVESTOR and identity.user_can_approve(session, user_id, role)
    return _out(session, u, user_id, role, departments, approver)


def figure_trace(
    session: Session, tenant_id: uuid.UUID, role: Role, update_id: uuid.UUID, figure_id: uuid.UUID
) -> dict[str, Any]:
    """The click view for a figure in an update (FR-6.7): the same lineage as the company's
    own tiles, plus who changed it in this update, if anyone did."""
    u = _get(session, tenant_id, role, update_id)
    f = session.scalar(
        select(UpdateFigure).where(
            UpdateFigure.tenant_id == tenant_id,
            UpdateFigure.update_id == u.id,
            UpdateFigure.figure_id == figure_id,
        )
    )
    if f is None:
        raise UpdatesError(404, "That figure is not in this update.")
    trace = metrics.trace(session, tenant_id, figure_id)
    trace["edited"] = None
    if f.edited_value is not None:
        edited = metrics.figure_view(session, tenant_id, figure_id, Decimal(f.edited_value))
        assert edited is not None and f.edited_at is not None  # noqa: S101
        trace["edited"] = {
            "by": f.edited_by_name,
            "at": f.edited_at.isoformat(),
            "calculated_display": trace["display"],
            "calculated_value": trace["value"],
        }
        trace["display"], trace["value"] = edited.display, f.edited_value
    return trace


# Approving (FR-3.3, FR-6.3)


def approve(
    session: Session, tenant_id: uuid.UUID, user_id: uuid.UUID, role: Role, update_id: uuid.UUID
) -> None:
    u = _get(session, tenant_id, role, update_id)
    if not identity.user_can_approve(session, user_id, role):
        raise UpdatesError(403, "Your company's approval setting does not include you.")
    if u.status == "shared":
        raise UpdatesError(409, "This update is already shared.")
    user, _ = identity.me(session, user_id)
    u.status, u.approved_by, u.approved_by_name, u.approved_at = (
        "shared",
        user_id,
        user.name,
        _now(),
    )
    session.flush()
    audit.record(
        session,
        "update.approved",
        tenant_id=tenant_id,
        actor_user_id=user_id,
        target_type="update",
        target_id=u.id,
    )
    emit(
        session,
        UpdatesOutbox,
        SHARED,
        tenant_id,
        {"update_id": str(u.id), "upload_id": str(u.upload_id)},
    )


# Editing (FR-6.2)


def edit_figure(
    session: Session,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    role: Role,
    departments: list[str],
    update_id: uuid.UUID,
    figure_id: uuid.UUID,
    value: str | None,
) -> None:
    """A person changes a figure in this update, or puts back the calculated one with
    ``value`` None. The figure's lineage then names the person and the date."""
    u = _get(session, tenant_id, role, update_id)
    f = session.scalar(
        select(UpdateFigure).where(
            UpdateFigure.tenant_id == tenant_id,
            UpdateFigure.update_id == u.id,
            UpdateFigure.figure_id == figure_id,
        )
    )
    if f is None:
        raise UpdatesError(404, "That figure is not in this update.")
    if not can_edit(role, departments, u.department):
        raise UpdatesError(403, "You can edit updates for your own departments only.")
    calculated = metrics.figure_view(session, tenant_id, figure_id)
    assert calculated is not None and calculated.value is not None  # noqa: S101
    new: Decimal | None = None
    if value is not None:
        try:
            new = Decimal(value.replace(",", "").replace("£", "").strip())
        except InvalidOperation as exc:
            raise UpdatesError(422, "Enter the figure as a number, such as 1378000.") from exc
        if not new.is_finite() or abs(new) >= Decimal("1e15"):
            raise UpdatesError(422, "Enter the figure as a number, such as 1378000.")
        if new == Decimal(calculated.value):
            new = None  # the same as the calculation: nothing is changed by hand
    before = f.edited_value if f.edited_value is not None else calculated.value
    after = str(new) if new is not None else calculated.value
    if before == after:
        return
    user, _ = identity.me(session, user_id)
    now = _now()
    if new is None:
        f.edited_value = f.edited_from = f.edited_by = f.edited_by_name = f.edited_at = None
    else:
        f.edited_value, f.edited_from = str(new), calculated.value
        f.edited_by, f.edited_by_name, f.edited_at = user_id, user.name, now
    u.last_edited_at, u.last_edited_by_name = now, user.name
    session.flush()
    audit.record(
        session,
        "update.edited",
        tenant_id=tenant_id,
        actor_user_id=user_id,
        target_type="update",
        target_id=u.id,
        details={"metric": f.metric, "period": f.period, "before": before, "after": after},
    )


# Comments (FR-6.5)


def add_comment(
    session: Session,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    role: Role,
    update_id: uuid.UUID,
    body: str,
) -> None:
    u = _get(session, tenant_id, role, update_id)
    if not body:
        raise UpdatesError(422, "Write a comment first.")
    user, _ = identity.me(session, user_id)
    comment = Comment(
        tenant_id=tenant_id,
        update_id=u.id,
        author_id=user_id,
        author_name=user.name,
        author_role=role.value,
        body=body,
        created_at=_now(),
    )
    session.add(comment)
    session.flush()
    audit.record(
        session,
        "update.commented",
        tenant_id=tenant_id,
        actor_user_id=user_id,
        target_type="update",
        target_id=u.id,
    )
    emit(
        session,
        UpdatesOutbox,
        COMMENTED,
        tenant_id,
        {"comment_id": str(comment.id), "update_id": str(u.id)},
    )


@dataclass(frozen=True)
class CommentNotice:
    """What notify needs to tell the other side about a comment."""

    author_id: uuid.UUID
    author_name: str
    from_investor: bool
    body: str
    line: str
    shared: bool


def comment_notice(
    session: Session, tenant_id: uuid.UUID, comment_id: uuid.UUID
) -> CommentNotice | None:
    c = session.scalar(
        select(Comment).where(Comment.tenant_id == tenant_id, Comment.id == comment_id)
    )
    if c is None:
        return None
    u = session.scalar(
        select(Update).where(Update.tenant_id == tenant_id, Update.id == c.update_id)
    )
    assert u is not None  # noqa: S101
    return CommentNotice(
        c.author_id,
        c.author_name,
        c.author_role == Role.INVESTOR.value,
        c.body,
        headline(u),
        u.status == "shared",
    )


@dataclass(frozen=True)
class UpdateNotice:
    added_by: uuid.UUID
    line: str


def update_notice(
    session: Session, tenant_id: uuid.UUID, update_id: uuid.UUID
) -> UpdateNotice | None:
    u = session.scalar(select(Update).where(Update.tenant_id == tenant_id, Update.id == update_id))
    return UpdateNotice(u.added_by, dated_line(u)) if u else None


# Export (FR-6.6)


def export_pdf(
    session: Session,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    role: Role,
    departments: list[str],
    update_id: uuid.UUID,
) -> tuple[bytes, str]:
    view = get_update(session, tenant_id, user_id, role, departments, update_id)
    company = identity.get_company(session, tenant_id)
    colour, logo = setup.branding(session, tenant_id)
    labels = []
    if view.approved_by_name and view.approved_at:
        labels.append(f"Approved by {view.approved_by_name}, {day(view.approved_at)}")
    else:
        labels.append("Awaiting approval. Not yet shared with investors.")
    if view.last_edited_at:
        labels.append(f"Last edited {day(view.last_edited_at)} by {view.last_edited_by_name}")
    document = pdf.UpdateDocument(
        company_name=company.name,
        colour=colour,
        logo=logo,
        headline=view.headline,
        detail=view.detail,
        labels=labels,
        figures=[
            pdf.FigureLine(
                f.label,
                f.period,
                f.display,
                f.source_line,
                f"Changed by {f.edited_by_name}, calculated {f.calculated_display}"
                if f.calculated_display
                else None,
            )
            for f in view.figures
        ],
    )
    audit.record(
        session,
        "update.exported",
        tenant_id=tenant_id,
        actor_user_id=user_id,
        target_type="update",
        target_id=view.id,
    )
    name = f"{company.name} update {view.data_as_of.isoformat()}.pdf"
    return pdf.render(document), name
