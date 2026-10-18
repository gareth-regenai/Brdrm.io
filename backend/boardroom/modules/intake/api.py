import uuid
from datetime import date, datetime
from typing import Any, Literal

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from boardroom.config import get_settings
from boardroom.db import system_session
from boardroom.gateway.deps import TenantContext, UserContext, current_user, require
from boardroom.modules.identity import service as identity
from boardroom.modules.intake import pipeline, service
from boardroom.modules.intake.fields import KINDS
from boardroom.modules.intake.models import InterpretationLog, ManualFigure, Question, Upload
from boardroom.modules.intake.storage import LocalStorage, get_storage, verify_upload
from boardroom.permissions import Action

router = APIRouter()


class UploadIn(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(ge=0)
    content_type: str = Field(default="", max_length=100)


class UploadLinkOut(BaseModel):
    upload_id: uuid.UUID
    url: str
    method: str
    headers: dict[str, str]


class QuestionOut(BaseModel):
    id: uuid.UUID
    prompt: str
    options: list[dict[str, str]]


class UploadOut(BaseModel):
    """What company users see. What the AI understood and ignored is not here (FR-4.10)."""

    id: uuid.UUID
    filename: str
    status: str
    message: str | None
    needs_mapping: bool
    kind: str | None
    row_count: int | None
    data_as_of: date | None
    created_at: datetime
    question: QuestionOut | None = None


class AnswerIn(BaseModel):
    question_id: uuid.UUID
    answer: str = Field(max_length=300)


class MappingColumnOut(BaseModel):
    name: str
    type: str
    examples: list[str]


class MappingInfoOut(BaseModel):
    columns: list[MappingColumnOut]
    kinds: dict[str, list[dict[str, str]]]


class ColumnChoice(BaseModel):
    column: str
    field: str
    date_format: str | None = None


class MappingIn(BaseModel):
    kind: Literal["finance", "sales", "delivery", "people", "plan"]
    columns: list[ColumnChoice]


class FigureIn(BaseModel):
    metric: str
    period: str = Field(pattern=r"^\d{4}-\d{2}$")
    value: str = Field(max_length=40)
    kind: str
    note: str | None = Field(default=None, max_length=300)


class FigureOut(BaseModel):
    id: uuid.UUID
    metric: str
    period: str
    value: str
    kind: str
    note: str | None
    label: str


def _out(session: Any, upload: Upload) -> UploadOut:
    q: Question | None = service.open_question(session, upload.id)
    return UploadOut(
        id=upload.id,
        filename=upload.filename,
        status=upload.status,
        message=upload.status_message,
        needs_mapping=upload.needs_mapping,
        kind=upload.file_kind,
        row_count=upload.row_count,
        data_as_of=upload.data_as_of,
        created_at=upload.created_at,
        question=QuestionOut(id=q.id, prompt=q.prompt, options=q.options) if q else None,
    )


def _raise(exc: service.IntakeError) -> HTTPException:
    return HTTPException(exc.code, exc.message)


@router.post("/company/uploads", response_model=UploadLinkOut, status_code=201, tags=["intake"])
def start_upload(
    body: UploadIn, ctx: TenantContext = Depends(require(Action.UPLOAD_FILES))
) -> UploadLinkOut:
    try:
        upload, link = service.create_upload(
            ctx.session,
            ctx.tenant_id,
            ctx.user_id,
            body.filename,
            body.size_bytes,
            body.content_type,
        )
    except service.IntakeError as exc:
        raise _raise(exc) from exc
    return UploadLinkOut(
        upload_id=upload.id, url=link.url, method=link.method, headers=link.headers
    )


@router.post("/company/uploads/{upload_id}/complete", response_model=UploadOut, tags=["intake"])
def complete(
    upload_id: uuid.UUID, ctx: TenantContext = Depends(require(Action.UPLOAD_FILES))
) -> UploadOut:
    try:
        upload = service.complete_upload(ctx.session, ctx.tenant_id, ctx.user_id, upload_id)
    except service.IntakeError as exc:
        raise _raise(exc) from exc
    return _out(ctx.session, upload)


@router.get("/company/uploads", response_model=list[UploadOut], tags=["intake"])
def uploads(ctx: TenantContext = Depends(require(Action.UPLOAD_FILES))) -> list[UploadOut]:
    return [_out(ctx.session, u) for u in service.list_uploads(ctx.session)]


@router.get("/company/uploads/{upload_id}", response_model=UploadOut, tags=["intake"])
def upload_detail(
    upload_id: uuid.UUID, ctx: TenantContext = Depends(require(Action.UPLOAD_FILES))
) -> UploadOut:
    upload = ctx.session.get(Upload, upload_id)
    if upload is None or upload.status == "created":
        raise HTTPException(404, "That upload was not found.")
    return _out(ctx.session, upload)


@router.post("/company/uploads/{upload_id}/answer", response_model=UploadOut, tags=["intake"])
def answer(
    upload_id: uuid.UUID, body: AnswerIn, ctx: TenantContext = Depends(require(Action.UPLOAD_FILES))
) -> UploadOut:
    try:
        upload = service.answer_question(
            ctx.session, ctx.tenant_id, ctx.user_id, upload_id, body.question_id, body.answer
        )
    except service.IntakeError as exc:
        raise _raise(exc) from exc
    return _out(ctx.session, upload)


@router.get("/company/uploads/{upload_id}/mapping", response_model=MappingInfoOut, tags=["intake"])
def mapping_info(
    upload_id: uuid.UUID, ctx: TenantContext = Depends(require(Action.UPLOAD_FILES))
) -> MappingInfoOut:
    try:
        _, _, columns = service.mapping_columns(ctx.session, upload_id)
    except service.IntakeError as exc:
        raise _raise(exc) from exc
    return MappingInfoOut(
        columns=[MappingColumnOut(**c) for c in columns],
        kinds={k: pipeline.kind_fields(k) for k in KINDS},
    )


@router.put("/company/uploads/{upload_id}/mapping", response_model=UploadOut, tags=["intake"])
def save_mapping(
    upload_id: uuid.UUID,
    body: MappingIn,
    ctx: TenantContext = Depends(require(Action.UPLOAD_FILES)),
) -> UploadOut:
    """Manual mapping, for when the AI is off or unavailable (FR-4.9)."""
    raw = {
        "file_kind": body.kind,
        "layout": "rows",
        "label_column": None,
        "currency": None,
        "row_labels": [],
        "columns": [
            {
                "column": c.column,
                "field": c.field,
                "confidence": 1.0,
                "reason": "Chosen by a person",
                "transform": {
                    "type": "parse_date" if c.date_format else "rename",
                    "date_format": c.date_format,
                    "factor": None,
                    "separator": None,
                    "part": None,
                    "with_column": None,
                    "mapping": None,
                },
            }
            for c in body.columns
        ],
    }
    try:
        upload = service.save_mapping(ctx.session, ctx.user_id, upload_id, raw)
    except service.IntakeError as exc:
        raise _raise(exc) from exc
    return _out(ctx.session, upload)


def _figure_out(f: ManualFigure) -> FigureOut:
    return FigureOut(
        id=f.id,
        metric=f.metric,
        period=f.period,
        value=f.value,
        kind=f.kind,
        note=f.note,
        label=f"Entered by {f.entered_by_name}, {f.entered_at:%-d %B %Y}",
    )


@router.post("/company/figures", response_model=FigureOut, status_code=201, tags=["intake"])
def add_figure(
    body: FigureIn, ctx: TenantContext = Depends(require(Action.UPLOAD_FILES))
) -> FigureOut:
    try:
        figure = service.add_figure(
            ctx.session,
            ctx.tenant_id,
            ctx.user_id,
            body.metric,
            body.period,
            body.value,
            body.kind,
            body.note,
        )
    except service.IntakeError as exc:
        raise _raise(exc) from exc
    ctx.session.refresh(figure)
    return _figure_out(figure)


@router.get("/company/figures", response_model=list[FigureOut], tags=["intake"])
def figures(ctx: TenantContext = Depends(require(Action.UPLOAD_FILES))) -> list[FigureOut]:
    return [_figure_out(f) for f in service.list_figures(ctx.session)]


# Development storage: stands in for the S3 signed link, so the flow is the same.


@router.put("/storage/upload/{token}", status_code=204, tags=["intake"])
async def local_upload(token: str, request: Request) -> Response:
    storage = get_storage()
    if not isinstance(storage, LocalStorage):
        raise HTTPException(404, "Not found.")
    try:
        key = verify_upload(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(403, "This upload link has expired. Add the file again.") from exc
    limit = get_settings().max_file_mb * 1024 * 1024
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > limit:
            raise HTTPException(413, "This file is larger than we accept.")
    storage.put(key, bytes(body))
    return Response(status_code=204)


# Platform admins only: what the AI understood and ignored (FR-4.10).


class LogOut(BaseModel):
    source: str
    model: str | None
    skill_version: str | None
    interpretation: dict[str, Any] | None
    dropped: list[dict[str, Any]]
    error: str | None
    created_at: datetime


@router.get(
    "/admin/uploads/{upload_id}/interpretation", response_model=list[LogOut], tags=["admin"]
)
def interpretation_log(
    upload_id: uuid.UUID, ctx: UserContext = Depends(current_user)
) -> list[LogOut]:
    if not identity.is_platform_admin(ctx.session, ctx.user_id):
        raise HTTPException(403, "You do not have access to this.")
    with system_session() as session:
        rows = session.scalars(
            select(InterpretationLog)
            .where(InterpretationLog.upload_id == upload_id)
            .order_by(InterpretationLog.created_at)
        ).all()
        return [
            LogOut(
                source=r.source,
                model=r.model,
                skill_version=r.skill_version,
                interpretation=r.interpretation,
                dropped=r.dropped,
                error=r.error,
                created_at=r.created_at,
            )
            for r in rows
        ]
