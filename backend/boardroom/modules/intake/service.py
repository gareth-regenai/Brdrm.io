"""Uploads, questions, manual mapping and hand-entered figures for the API."""

import hashlib
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
from boardroom.modules.intake import pipeline
from boardroom.modules.intake.models import (
    Dataset,
    DatasetRow,
    IntakeOutbox,
    ManualFigure,
    Question,
    Upload,
)
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
    emit(session, IntakeOutbox, pipeline.FIGURE_ENTERED, tenant_id, {"figure_id": str(figure.id)})
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


# Read access for the metrics module, which runs as br_system: every call names its tenant.


@dataclass(frozen=True)
class DatasetView:
    id: uuid.UUID
    kind: str
    version: int
    upload_id: uuid.UUID
    filename: str
    fields: tuple[str, ...]
    data_as_of: date | None
    created_at: datetime
    rows: tuple[tuple[int, dict[str, Any]], ...]


def datasets_for_metrics(
    session: Session, tenant_id: uuid.UUID, per_kind: int = 5
) -> list[DatasetView]:
    """The newest datasets of each kind, newest first, with their rows."""
    found = session.execute(
        select(Dataset, Upload.filename)
        .join(Upload, Upload.id == Dataset.upload_id)
        .where(Dataset.tenant_id == tenant_id, Upload.tenant_id == tenant_id)
        .order_by(Dataset.created_at.desc())
    ).all()
    counts: dict[str, int] = {}
    views = []
    for ds, filename in found:
        counts[ds.kind] = counts.get(ds.kind, 0) + 1
        if counts[ds.kind] > per_kind:
            continue
        rows = session.execute(
            select(DatasetRow.row_number, DatasetRow.data)
            .where(DatasetRow.tenant_id == tenant_id, DatasetRow.dataset_id == ds.id)
            .order_by(DatasetRow.row_number)
        ).all()
        views.append(
            DatasetView(
                ds.id,
                ds.kind,
                ds.version,
                ds.upload_id,
                filename,
                tuple(ds.fields),
                ds.data_as_of,
                ds.created_at,
                tuple((n, d) for n, d in rows),
            )
        )
    return views


def dataset_rows(
    session: Session, tenant_id: uuid.UUID, dataset_id: uuid.UUID, numbers: list[int]
) -> list[tuple[int, dict[str, Any]]]:
    rows = session.execute(
        select(DatasetRow.row_number, DatasetRow.data)
        .where(
            DatasetRow.tenant_id == tenant_id,
            DatasetRow.dataset_id == dataset_id,
            DatasetRow.row_number.in_(numbers),
        )
        .order_by(DatasetRow.row_number)
    ).all()
    return [(n, d) for n, d in rows]


@dataclass(frozen=True)
class ManualFigureView:
    id: uuid.UUID
    metric: str
    period: str
    value: Decimal
    kind: str
    entered_by_name: str
    entered_at: datetime


def manual_figures_for(session: Session, tenant_id: uuid.UUID) -> list[ManualFigureView]:
    rows = session.scalars(
        select(ManualFigure)
        .where(ManualFigure.tenant_id == tenant_id)
        .order_by(ManualFigure.entered_at)
    ).all()
    return [
        ManualFigureView(
            f.id, f.metric, f.period, Decimal(f.value), f.kind, f.entered_by_name, f.entered_at
        )
        for f in rows
    ]


@consumer("intake.after_figures", "metrics.figures_computed")
def _after_figures(session: Session, event: Event) -> None:
    upload_id = event.payload.get("upload_id")
    if not upload_id or event.tenant_id is None:
        return
    upload = session.scalar(
        select(Upload).where(Upload.id == uuid.UUID(upload_id), Upload.tenant_id == event.tenant_id)
    )
    if upload is not None:
        pipeline.finish_after_figures(session, upload)


def currencies_seen(session: Session, tenant_id: uuid.UUID) -> dict[str, int]:
    """How often each currency appears in the company's data, for the setup chat."""
    counts: dict[str, int] = {}
    for ds in session.scalars(select(Dataset).where(Dataset.tenant_id == tenant_id)).all():
        code = (ds.interpretation or {}).get("currency")
        if code:
            counts[code] = counts.get(code, 0) + ds.row_count
    rows = session.execute(
        select(DatasetRow.data["currency"].astext).where(
            DatasetRow.tenant_id == tenant_id, DatasetRow.data.has_key("currency")
        )
    ).all()
    for (code,) in rows:
        if code:
            counts[code] = counts.get(code, 0) + 1
    return counts


def pnl_labels(session: Session, tenant_id: uuid.UUID, limit: int = 100) -> list[str]:
    """Line items down the side of the newest profit and loss report, such as "Sales"."""
    ds = session.scalar(
        select(Dataset)
        .where(Dataset.tenant_id == tenant_id, Dataset.kind == "finance")
        .order_by(Dataset.created_at.desc())
        .limit(1)
    )
    if ds is None or ds.interpretation.get("layout") != "periods_as_columns":
        return []
    upload = session.scalar(
        select(Upload).where(Upload.tenant_id == tenant_id, Upload.id == ds.upload_id)
    )
    if upload is None:
        return []
    table = pipeline.load_clean_table(upload)
    column = ds.interpretation["label_column"]
    if column not in table.headers:
        return []
    i = table.headers.index(column)
    labels: list[str] = []
    for row in table.rows:
        label = row[i].strip()
        if label and len(label) <= 60 and label not in labels:
            labels.append(label)
    return labels[:limit]
