"""The intake pipeline: received, understanding, then on to calculating (FR-3.1).

Runs in the worker as the uploader, under row-level security. Calculating and describing
are E3 and E6; until then they pass straight through, each still recorded as an event.
"""

import csv
import hashlib
import io
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from boardroom.config import get_settings
from boardroom.db import app_session, as_system
from boardroom.events import emit
from boardroom.logs import get_logger
from boardroom.modules.audit import service as audit
from boardroom.modules.identity import service as identity
from boardroom.modules.intake import interpret, skill1
from boardroom.modules.intake.fields import (
    BLOCKING_FIELDS,
    FIELDS,
    QUESTION_THRESHOLD,
    field,
)
from boardroom.modules.intake.models import (
    Dataset,
    DatasetRow,
    IntakeOutbox,
    InterpretationLog,
    Layout,
    Question,
    Upload,
)
from boardroom.modules.intake.parsing import ParseError, Table, parse_sandboxed
from boardroom.modules.intake.profiler import profile
from boardroom.modules.intake.scanner import get_scanner
from boardroom.modules.intake.sensitive import Dropped, drop_sensitive
from boardroom.modules.intake.skill1 import Interpretation, SkillOutputError, SkillUnavailable
from boardroom.modules.intake.storage import clean_key, get_storage, raw_key
from boardroom.permissions import Role

log = get_logger(__name__)

STATUS_CHANGED = "intake.upload_status_changed"
QUESTION_ASKED = "intake.question_asked"
DATASET_READY = "intake.dataset_ready"
FIGURE_ENTERED = "intake.figure_entered"
KIND_WORDS = {
    "finance": "finance",
    "sales": "sales pipeline",
    "delivery": "product delivery",
    "people": "people",
    "plan": "plan or budget",
}


# Helpers


def set_status(session: Session, upload: Upload, status: str, message: str | None = None) -> None:
    upload.status = status
    upload.status_message = message
    audit.record(
        session,
        "upload.status_changed",
        tenant_id=upload.tenant_id,
        actor_user_id=None,
        target_type="upload",
        target_id=upload.id,
        details={"status": status},
    )
    emit(
        session,
        IntakeOutbox,
        STATUS_CHANGED,
        upload.tenant_id,
        {"upload_id": str(upload.id), "status": status},
    )
    session.flush()


def header_fingerprint(table: Table) -> str:
    """Month headers are normalised, so next month's P&L matches this month's layout."""
    names = ["<month>" if interpret.parse_month(h) else h.strip().lower() for h in table.headers]
    return hashlib.sha256("|".join(names).encode()).hexdigest()


def table_to_csv(table: Table) -> bytes:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(table.headers)
    writer.writerows(table.rows)
    return out.getvalue().encode()


def csv_to_table(data: bytes) -> Table:
    rows = list(csv.reader(io.StringIO(data.decode())))
    return Table(headers=rows[0], rows=rows[1:])


def interpretation_from_json(raw: dict[str, Any], table: Table) -> Interpretation:
    return skill1.validate(raw, table)


def _log(
    session: Session,
    upload: Upload,
    source: str,
    interp: Interpretation | None,
    dropped: list[Dropped] | None = None,
    error: str | None = None,
    model: str | None = None,
) -> None:
    # The app role cannot read or write this table. Only platform admins see it.
    with as_system(session):
        session.add(
            InterpretationLog(
                tenant_id=upload.tenant_id,
                upload_id=upload.id,
                source=source,
                model=model,
                skill_version=skill1.SKILL_VERSION if source == "ai" else None,
                interpretation=interp.to_json() if interp else None,
                dropped=[{"position": d.position, "reason": d.reason} for d in dropped or []],
                error=error,
            )
        )


# Step 1: scan, parse, drop pay columns, keep only the clean copy


def _prepare(upload: Upload) -> tuple[Table | None, list[Dropped], str | None]:
    storage = get_storage()
    key = raw_key(str(upload.tenant_id), str(upload.id))
    try:
        data = storage.get(key)
        threat = get_scanner().scan(data)
        if threat:
            return None, [], "The virus scan flagged this file, so it has been deleted."
        try:
            table = parse_sandboxed(data)
        except ParseError as exc:
            return None, [], str(exc)
        clean, dropped = drop_sensitive(table)
        if not clean.headers:
            return None, dropped, "This file only had pay or personal columns, which we never keep."
        storage.put(clean_key(str(upload.tenant_id), str(upload.id)), table_to_csv(clean))
        return clean, dropped, None
    finally:
        # The raw file never outlives this step, whatever happened (FR-4.4).
        storage.delete(key)


# Step 2: understand


def _understand(
    table: Table, upload: Upload
) -> tuple[Interpretation | None, str, str | None, str | None]:
    """Returns (interpretation, source, model, error). None means manual mapping."""
    client = skill1.get_client()
    if client is None:
        return None, "fallback", None, "AI switched off"
    payload = skill1.build_payload(table, profile(table), upload.filename)
    try:
        raw = client.interpret(payload)
        return skill1.validate(raw, table), "ai", client.model, None
    except (SkillUnavailable, SkillOutputError) as exc:
        return None, "fallback", client.model, f"{type(exc).__name__}: {exc}"


def _question_for(interp: Interpretation, table: Table) -> tuple[str, str, float] | None:
    """The single least certain mapping that blocks a figure, if any (FR-4.6)."""
    blocking = BLOCKING_FIELDS.get(interp.file_kind, frozenset())
    candidates: list[tuple[str, str, float]] = [
        (m.column, m.field, m.confidence)
        for m in interp.columns
        if m.field in blocking and m.confidence < QUESTION_THRESHOLD
    ] + [
        (r.label, r.field, r.confidence)
        for r in interp.row_labels
        if r.field in blocking and r.confidence < QUESTION_THRESHOLD
    ]
    return min(candidates, key=lambda c: c[2]) if candidates else None


def _ask(
    session: Session, upload: Upload, interp: Interpretation, subject: str, field_key: str
) -> None:
    f = field(interp.file_kind, field_key)
    label = f.label if f else field_key
    if interp.layout == "periods_as_columns":
        prompt = f'Is the line "{subject}" your {label}?'
    else:
        prompt = f'Is the column "{subject}" your {label}?'
    options = [
        {"value": "yes", "label": f"Yes, it is the {label}"},
        {"value": "no", "label": f"No, this file has no {label}"},
    ]
    session.add(
        Question(
            tenant_id=upload.tenant_id,
            upload_id=upload.id,
            subject=subject,
            field=field_key,
            prompt=prompt,
            options=options,
        )
    )
    session.flush()
    emit(
        session,
        IntakeOutbox,
        QUESTION_ASKED,
        upload.tenant_id,
        {"upload_id": str(upload.id), "user_id": str(upload.uploaded_by)},
    )


# Step 3: build the dataset


def _finish(
    session: Session,
    upload: Upload,
    table: Table,
    interp: Interpretation,
    confirmed: set[str],
    layout_source: str,
    user_id: uuid.UUID | None,
) -> None:
    if interp.file_kind == "unknown":
        upload.needs_mapping = True
        set_status(
            session,
            upload,
            "understanding",
            "We could not tell what this file holds. Choose what each column is.",
        )
        return

    membership = identity.active_membership(session, upload.uploaded_by, upload.tenant_id)
    scoped = membership and membership.role in (Role.DEPARTMENT_LEAD, Role.CONTRIBUTOR)
    if scoped and membership and interp.file_kind not in membership.departments:
        set_status(
            session,
            upload,
            "failed",
            f"This looks like a {KIND_WORDS[interp.file_kind]} file. "
            "Ask the CEO or that department's lead to add it.",
        )
        return

    fingerprint = upload.header_fingerprint or header_fingerprint(table)
    layout = session.scalar(
        select(Layout).where(
            Layout.tenant_id == upload.tenant_id, Layout.fingerprint == fingerprint
        )
    )
    if layout is None:
        layout = Layout(
            tenant_id=upload.tenant_id,
            fingerprint=fingerprint,
            interpretation=interp.to_json(),
            confirmed=sorted(confirmed),
            source=layout_source,
            updated_by=user_id,
        )
        session.add(layout)
    else:
        layout.interpretation = interp.to_json()
        layout.confirmed = sorted(confirmed)
        layout.source = layout_source
        layout.updated_by = user_id
    session.flush()

    ds = interpret.apply(table, interp, confirmed)
    version = (
        session.scalar(
            select(func.max(Dataset.version)).where(
                Dataset.tenant_id == upload.tenant_id, Dataset.kind == interp.file_kind
            )
        )
        or 0
    ) + 1
    dataset = Dataset(
        tenant_id=upload.tenant_id,
        upload_id=upload.id,
        kind=interp.file_kind,
        version=version,
        layout_id=layout.id,
        interpretation=interp.to_json(),
        fields=ds.fields,
        row_count=len(ds.rows),
        invalid_cells=ds.invalid_cells,
        data_as_of=ds.data_as_of,
        fingerprint=ds.fingerprint(),
    )
    session.add(dataset)
    session.flush()
    session.add_all(
        DatasetRow(dataset_id=dataset.id, row_number=i, tenant_id=upload.tenant_id, data=row)
        for i, row in enumerate(ds.rows)
    )
    upload.file_kind = interp.file_kind
    upload.dataset_id = dataset.id
    upload.row_count = len(ds.rows)
    upload.data_as_of = ds.data_as_of
    upload.needs_mapping = False
    upload.proposal = None
    # The metrics module calculates, then tells intake to move on (figures_computed).
    set_status(session, upload, "calculating")
    emit(
        session,
        IntakeOutbox,
        DATASET_READY,
        upload.tenant_id,
        {"upload_id": str(upload.id), "dataset_id": str(dataset.id)},
    )


def finish_after_figures(session: Session, upload: Upload) -> None:
    """Describing passes straight through until E6 writes commentary."""
    if upload.status != "calculating":
        return
    set_status(session, upload, "describing")
    message = None
    if upload.file_kind in ("delivery", "people") and not get_settings().flags.people:
        message = "Saved. Figures from this kind of file arrive in phase 2."
    set_status(session, upload, "ready", message)


# Entry points


def process(upload_id: uuid.UUID, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
    with app_session(user_id=user_id, tenant_id=tenant_id) as session:
        upload = session.get(Upload, upload_id)
        if upload is None or upload.status != "received":
            return  # already processed: the event was delivered twice
        set_status(session, upload, "understanding")
        snapshot = Upload(id=upload.id, tenant_id=upload.tenant_id, filename=upload.filename)

    table, dropped, error = _prepare(snapshot)

    with app_session(user_id=user_id, tenant_id=tenant_id) as session:
        upload = session.get(Upload, upload_id)
        assert upload is not None  # noqa: S101
        if table is None:
            _log(session, upload, "fallback", None, dropped, error)
            set_status(session, upload, "failed", error)
            return
        upload.header_fingerprint = header_fingerprint(table)
        layout = session.scalar(
            select(Layout).where(
                Layout.tenant_id == tenant_id, Layout.fingerprint == upload.header_fingerprint
            )
        )
        if layout is not None:
            # Seen before: reuse the confirmed layout and ask nothing (FR-4.7).
            try:
                interp = interpretation_from_json(layout.interpretation, table)
            except SkillOutputError:
                interp = None
            if interp is not None:
                _log(session, upload, "layout", interp, dropped)
                _finish(session, upload, table, interp, set(layout.confirmed), layout.source, None)
                return

    interp, source, model, error = _understand(table, snapshot)

    with app_session(user_id=user_id, tenant_id=tenant_id) as session:
        upload = session.get(Upload, upload_id)
        assert upload is not None  # noqa: S101
        _log(session, upload, source, interp, dropped, error, model)
        if interp is None:
            upload.needs_mapping = True
            set_status(session, upload, "understanding", "Choose what each column is to continue.")
            return
        upload.file_kind = interp.file_kind
        question = _question_for(interp, table)
        if question is not None:
            upload.proposal = interp.to_json()
            _ask(session, upload, interp, question[0], question[1])
            set_status(session, upload, "understanding", "One question before we can continue.")
            return
        _finish(session, upload, table, interp, set(), "ai", None)


def load_clean_table(upload: Upload) -> Table:
    return csv_to_table(get_storage().get(clean_key(str(upload.tenant_id), str(upload.id))))


def resume_after_answer(
    session: Session, upload: Upload, question: Question, user_id: uuid.UUID
) -> None:
    """Apply the person's answer, save it to the layout, and carry on (FR-4.6)."""
    assert upload.proposal is not None  # noqa: S101
    table = load_clean_table(upload)
    raw = dict(upload.proposal)
    if question.answer == "no":
        for key, name in (("columns", "column"), ("row_labels", "label")):
            raw[key] = [
                {**m, "field": "ignore"} if m[name] == question.subject else m for m in raw[key]
            ]
    interp = interpretation_from_json(raw, table)
    confirmed = {question.subject} if question.answer == "yes" else set()
    # Other uncertain mappings that do not block a figure keep the AI's best guess.
    _finish(session, upload, table, interp, confirmed, "answer", user_id)


def apply_manual(session: Session, upload: Upload, raw: dict[str, Any], user_id: uuid.UUID) -> None:
    table = load_clean_table(upload)
    interp = interpretation_from_json(raw, table)
    confirmed = {m.column for m in interp.columns} | {r.label for r in interp.row_labels}
    _log(session, upload, "manual", interp)
    upload.header_fingerprint = upload.header_fingerprint or header_fingerprint(table)
    _finish(session, upload, table, interp, confirmed, "manual", user_id)


def kind_fields(kind: str) -> list[dict[str, str]]:
    return [{"key": f.key, "label": f.label, "type": f.type.value} for f in FIELDS.get(kind, ())]
