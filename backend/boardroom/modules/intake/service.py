"""Uploads, questions, manual mapping and hand-entered figures for the API."""

import hashlib
import uuid
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from boardroom.config import get_settings
from boardroom.events import Event, consumer, emit
from boardroom.modules.audit import service as audit
from boardroom.modules.identity import service as identity
from boardroom.modules.intake import pipeline
from boardroom.modules.intake.models import IntakeOutbox, ManualFigure, Question, Upload
from boardroom.modules.intake.parsing import Table
from boardroom.modules.intake.profiler import profile
from boardroom.modules.intake.skill1 import SkillOutputError
from boardroom.modules.intake.storage import UploadLink, get_storage, raw_key

UPLOAD_RECEIVED = "intake.upload_received"


class IntakeError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _get(session: Session, upload_id: uuid.UUID) -> Upload:
    upload = session.get(Upload, upload_id)
    if upload is None:
        raise IntakeError(404, "That upload was not found.")
    return upload


def create_upload(
    session: Session,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    filename: str,
    size_bytes: int,
    content_type: str,
) -> tuple[Upload, UploadLink]:
    limit = get_settings().max_file_mb
    if size_bytes > limit * 1024 * 1024:
        raise IntakeError(
            413, f"Files can be up to {limit} MB. Split the file or export fewer rows."
        )
    upload = Upload(
        tenant_id=tenant_id,
        uploaded_by=user_id,
        filename=filename[:255],
        size_bytes=size_bytes,
        content_type=content_type[:100] or "application/octet-stream",
    )
    session.add(upload)
    session.flush()
    audit.record(
        session,
        "upload.started",
        tenant_id=tenant_id,
        actor_user_id=user_id,
        target_type="upload",
        target_id=upload.id,
    )
    link = get_storage().upload_link(raw_key(str(tenant_id), str(upload.id)), upload.content_type)
    return upload, link


def complete_upload(
    session: Session, tenant_id: uuid.UUID, user_id: uuid.UUID, upload_id: uuid.UUID
) -> Upload:
    upload = _get(session, upload_id)
    if upload.uploaded_by != user_id:
        raise IntakeError(403, "Only the person who added a file can finish adding it.")
    if upload.status != "created":
        return upload
    storage = get_storage()
    key = raw_key(str(tenant_id), str(upload.id))
    size = storage.size(key)
    if size is None:
        raise IntakeError(409, "The file has not arrived yet. Try adding it again.")
    if size > get_settings().max_file_mb * 1024 * 1024:
        storage.delete(key)
        pipeline.set_status(session, upload, "failed", "This file is larger than we accept.")
        return upload
    upload.size_bytes = size
    upload.sha256 = hashlib.sha256(storage.get(key)).hexdigest()
    audit.record(
        session,
        "upload.added",
        tenant_id=tenant_id,
        actor_user_id=user_id,
        target_type="upload",
        target_id=upload.id,
    )
    pipeline.set_status(session, upload, "received")
    emit(
        session,
        IntakeOutbox,
        UPLOAD_RECEIVED,
        tenant_id,
        {"upload_id": str(upload.id), "user_id": str(user_id)},
    )
    return upload


@consumer("intake.process_upload", UPLOAD_RECEIVED)
def _process(session: Session, event: Event) -> None:
    assert event.tenant_id is not None  # noqa: S101
    upload_id = uuid.UUID(event.payload["upload_id"])
    user_id = uuid.UUID(event.payload["user_id"])
    if get_settings().dispatch_inline:
        pipeline.process(upload_id, event.tenant_id, user_id)
    else:
        from boardroom.worker import process_upload

        process_upload.delay(str(upload_id), str(event.tenant_id), str(user_id))


def list_uploads(session: Session) -> list[Upload]:
    return list(
        session.scalars(
            select(Upload)
            .where(Upload.status != "created")
            .order_by(Upload.created_at.desc())
            .limit(100)
        ).all()
    )


def open_question(session: Session, upload_id: uuid.UUID) -> Question | None:
    return session.scalar(
        select(Question)
        .where(Question.upload_id == upload_id, Question.answer.is_(None))
        .order_by(Question.created_at.desc())
    )


def answer_question(
    session: Session,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    upload_id: uuid.UUID,
    question_id: uuid.UUID,
    answer: str,
) -> Upload:
    upload = _get(session, upload_id)
    question = session.get(Question, question_id)
    if question is None or question.upload_id != upload.id or question.answer is not None:
        raise IntakeError(404, "That question has already been answered.")
    if answer not in {o["value"] for o in question.options}:
        raise IntakeError(422, "Choose one of the answers given.")
    question.answer = answer
    question.answered_by = user_id
    question.answered_at = datetime.now(UTC)
    audit.record(
        session,
        "upload.question_answered",
        tenant_id=tenant_id,
        actor_user_id=user_id,
        target_type="upload",
        target_id=upload.id,
    )
    pipeline.resume_after_answer(session, upload, question, user_id)
    return upload


def mapping_columns(
    session: Session, upload_id: uuid.UUID
) -> tuple[Upload, Table, list[dict[str, Any]]]:
    upload = _get(session, upload_id)
    if not upload.needs_mapping:
        raise IntakeError(409, "This file does not need mapping.")
    table = pipeline.load_clean_table(upload)
    columns = [
        {
            "name": p.name,
            "type": p.inferred_type,
            "examples": [r[i] for r in table.rows[:3] if r[i]][:3],
        }
        for i, p in enumerate(profile(table))
    ]
    return upload, table, columns


def save_mapping(
    session: Session, user_id: uuid.UUID, upload_id: uuid.UUID, raw: dict[str, Any]
) -> Upload:
    upload = _get(session, upload_id)
    if not upload.needs_mapping:
        raise IntakeError(409, "This file does not need mapping.")
    try:
        pipeline.apply_manual(session, upload, raw, user_id)
    except SkillOutputError as exc:
        raise IntakeError(422, "Some choices do not match this file's columns.") from exc
    audit.record(
        session,
        "upload.mapped_by_hand",
        tenant_id=upload.tenant_id,
        actor_user_id=user_id,
        target_type="upload",
        target_id=upload.id,
    )
    return upload


# Hand-entered figures (FR-4.8). Targets entered here are one source of plan (FR-4.11).

FIGURE_METRICS = (
    "revenue",
    "cost_of_sales",
    "operating_expenses",
    "cash_balance",
    "net_burn",
    "pipeline",
    "closed_won",
    "headcount",
)
FIGURE_KINDS = ("actual", "forecast", "target")


def add_figure(
    session: Session,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    metric: str,
    period: str,
    value: str,
    kind: str,
    note: str | None,
) -> ManualFigure:
    if metric not in FIGURE_METRICS or kind not in FIGURE_KINDS:
        raise IntakeError(422, "Choose a measure and whether it is an actual, forecast or target.")
    try:
        datetime.strptime(period, "%Y-%m")
        number = Decimal(value.replace(",", "").replace("£", "").strip())
    except (ValueError, InvalidOperation) as exc:
        raise IntakeError(422, "Give the month as YYYY-MM and the value as a number.") from exc
    user, _ = identity.me(session, user_id)
    figure = ManualFigure(
        tenant_id=tenant_id,
        metric=metric,
        period=period,
        value=str(number),
        kind=kind,
        note=note,
        entered_by=user_id,
        entered_by_name=user.name,
    )
    session.add(figure)
    session.flush()
    audit.record(
        session,
        "figure.entered",
        tenant_id=tenant_id,
        actor_user_id=user_id,
        target_type="figure",
        target_id=figure.id,
        details={"metric": metric, "kind": kind},
    )
    return figure


def list_figures(session: Session) -> list[ManualFigure]:
    return list(
        session.scalars(select(ManualFigure).order_by(ManualFigure.entered_at.desc())).all()
    )
