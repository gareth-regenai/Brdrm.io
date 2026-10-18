import uuid
from datetime import date, datetime
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from boardroom.gateway.deps import TenantContext, UserContext, current_user, require
from boardroom.modules.updates import service
from boardroom.permissions import Action

router = APIRouter()


class FigureOut(BaseModel):
    figure_id: uuid.UUID
    metric: str
    label: str
    unit: str
    period: str
    display: str
    source_line: str
    risk: str | None
    calculated_display: str | None
    edited_by_name: str | None
    edited_at: datetime | None


class SectionOut(BaseModel):
    id: uuid.UUID
    kind: str
    department: str | None
    text: str | None
    status: str
    label: str
    reason: str | None
    unmatched: list[str]


class CommentOut(BaseModel):
    id: uuid.UUID
    author_name: str
    author_role: str
    body: str
    created_at: datetime
    mine: bool


class UpdateOut(BaseModel):
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
    sections: list[SectionOut]
    comments: list[CommentOut]
    can_edit: bool
    can_approve: bool


class FigureEdit(BaseModel):
    # None puts back the calculated figure.
    value: str | None = Field(max_length=40)


class SectionEdit(BaseModel):
    # "" leaves the section out of the update.
    text: str = Field(max_length=4000)


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


def _raise(exc: service.UpdatesError) -> HTTPException:
    return HTTPException(exc.code, exc.message)


def _one(ctx: TenantContext, update_id: uuid.UUID) -> UpdateOut:
    view = service.get_update(
        ctx.session, ctx.tenant_id, ctx.user_id, ctx.role, ctx.departments, update_id
    )
    return UpdateOut.model_validate(view, from_attributes=True)


@router.get("/company/updates", response_model=list[UpdateOut], tags=["updates"])
def list_updates(ctx: TenantContext = Depends(require(Action.VIEW_COMPANY))) -> list[UpdateOut]:
    """Company users see every update; investors see shared ones (FR-3.3)."""
    return [
        UpdateOut.model_validate(u, from_attributes=True)
        for u in service.list_updates(
            ctx.session, ctx.tenant_id, ctx.user_id, ctx.role, ctx.departments
        )
    ]


@router.post("/company/updates/{update_id}/approve", response_model=UpdateOut, tags=["updates"])
def approve(
    update_id: uuid.UUID, ctx: TenantContext = Depends(require(Action.APPROVE_UPDATE))
) -> UpdateOut:
    try:
        service.approve(ctx.session, ctx.tenant_id, ctx.user_id, ctx.role, update_id)
        return _one(ctx, update_id)
    except service.UpdatesError as exc:
        raise _raise(exc) from exc


@router.put(
    "/company/updates/{update_id}/figures/{figure_id}", response_model=UpdateOut, tags=["updates"]
)
def edit_figure(
    update_id: uuid.UUID,
    figure_id: uuid.UUID,
    body: FigureEdit,
    ctx: TenantContext = Depends(require(Action.EDIT_UPDATE)),
) -> UpdateOut:
    """Change a figure in this update. The update then shows "Last edited" (FR-6.2)."""
    try:
        service.edit_figure(
            ctx.session,
            ctx.tenant_id,
            ctx.user_id,
            ctx.role,
            ctx.departments,
            update_id,
            figure_id,
            body.value,
        )
        return _one(ctx, update_id)
    except service.UpdatesError as exc:
        raise _raise(exc) from exc


@router.put(
    "/company/updates/{update_id}/sections/{section_id}", response_model=UpdateOut, tags=["updates"]
)
def edit_section(
    update_id: uuid.UUID,
    section_id: uuid.UUID,
    body: SectionEdit,
    ctx: TenantContext = Depends(require(Action.EDIT_UPDATE)),
) -> UpdateOut:
    """Edit Claude's draft, or write a section yourself (FR-5.5, FR-6.4)."""
    try:
        service.edit_section(
            ctx.session,
            ctx.tenant_id,
            ctx.user_id,
            ctx.role,
            ctx.departments,
            update_id,
            section_id,
            body.text,
        )
        return _one(ctx, update_id)
    except service.UpdatesError as exc:
        raise _raise(exc) from exc


@router.post("/company/updates/{update_id}/redraft", response_model=UpdateOut, tags=["updates"])
def redraft(
    update_id: uuid.UUID, ctx: TenantContext = Depends(require(Action.EDIT_UPDATE))
) -> UpdateOut:
    """Claude drafts the commentary again, in the company's current voice."""
    try:
        service.redraft(
            ctx.session, ctx.tenant_id, ctx.user_id, ctx.role, ctx.departments, update_id
        )
        return _one(ctx, update_id)
    except service.UpdatesError as exc:
        raise _raise(exc) from exc


@router.get("/company/updates/{update_id}/figures/{figure_id}", tags=["updates"])
def figure_trace(
    update_id: uuid.UUID,
    figure_id: uuid.UUID,
    ctx: TenantContext = Depends(require(Action.VIEW_COMPANY)),
) -> dict[str, Any]:
    """Where a figure in the update came from (FR-6.7)."""
    try:
        return service.figure_trace(ctx.session, ctx.tenant_id, ctx.role, update_id, figure_id)
    except service.UpdatesError as exc:
        raise _raise(exc) from exc


@router.post("/company/updates/{update_id}/comments", response_model=UpdateOut, tags=["updates"])
def comment(
    update_id: uuid.UUID,
    body: CommentIn,
    ctx: TenantContext = Depends(require(Action.COMMENT)),
) -> UpdateOut:
    try:
        service.add_comment(
            ctx.session, ctx.tenant_id, ctx.user_id, ctx.role, update_id, body.body.strip()
        )
        return _one(ctx, update_id)
    except service.UpdatesError as exc:
        raise _raise(exc) from exc


@router.get(
    "/company/updates/{update_id}/pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
    tags=["updates"],
)
def export_pdf(
    update_id: uuid.UUID, ctx: TenantContext = Depends(require(Action.VIEW_COMPANY))
) -> Response:
    try:
        data, name = service.export_pdf(
            ctx.session, ctx.tenant_id, ctx.user_id, ctx.role, ctx.departments, update_id
        )
    except service.UpdatesError as exc:
        raise _raise(exc) from exc
    return Response(
        data,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"},
    )


# The investor's portfolio overview (FRD chapter 7)


class MeasureOut(BaseModel):
    key: str
    label: str
    display: str
    risk: str | None
    period: str | None
    available: bool


class CardOut(BaseModel):
    tenant_id: uuid.UUID
    name: str
    risk: str | None
    measures: list[MeasureOut]
    latest_update_id: uuid.UUID | None


@router.get("/portfolio/overview", response_model=list[CardOut], tags=["investor"])
def overview(ctx: UserContext = Depends(current_user)) -> list[CardOut]:
    """One card per company the investor backs, highest risk first. Company users are
    refused (FR-7.7)."""
    try:
        cards = service.overview(ctx.session, ctx.user_id)
    except service.UpdatesError as exc:
        raise _raise(exc) from exc
    return [CardOut.model_validate(c, from_attributes=True) for c in cards]
