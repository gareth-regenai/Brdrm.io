"""Recalculates a company's figures whenever its data changes, and serves them."""

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from boardroom.events import Event, consumer, emit
from boardroom.modules.audit import service as audit
from boardroom.modules.intake import service as intake
from boardroom.modules.metrics import compute, selection
from boardroom.modules.metrics.display import (
    DEFAULT_THRESHOLDS,
    Threshold,
    band_for,
    format_value,
    risk,
)
from boardroom.modules.metrics.models import (
    FigureRecord,
    MetricSetting,
    MetricsOutbox,
    RowSelection,
    Run,
)
from boardroom.modules.metrics.registry import METRICS, ROW_SETS, VARIANT_FORMULAS
from boardroom.modules.setup import service as setup

FIGURES_COMPUTED = "metrics.figures_computed"

STATUS_WORDS = {
    "not_provided": "Not provided",
    "cash_generative": "Cash-generative",
    "no_plan": "No plan set",
    "target_met": "Target met",
}


class MetricsError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# Selections, chosen once per dataset version


def _selections(
    session: Session, tenant_id: uuid.UUID, datasets: list[intake.DatasetView]
) -> dict[tuple[str, str], selection.Selection]:
    out: dict[tuple[str, str], selection.Selection] = {}
    for ds in datasets:
        stored = session.scalars(
            select(RowSelection).where(
                RowSelection.tenant_id == tenant_id, RowSelection.dataset_id == ds.id
            )
        ).all()
        if not stored and any(rs.kind == ds.kind for rs in ROW_SETS.values()):
            chosen, why = selection.choose(ds)
            client = selection.get_client()
            for s in chosen:
                session.add(
                    RowSelection(
                        tenant_id=tenant_id,
                        dataset_id=ds.id,
                        row_set=s.row_set,
                        filters=s.to_json()["filters"],
                        source=s.source,
                        reason=(why or s.reason)[:300] if s.source == "standard" else s.reason,
                        model=client.model if client and s.source == "ai" else None,
                        skill_version=selection.SKILL_VERSION if s.source == "ai" else None,
                    )
                )
            session.flush()
            stored = session.scalars(
                select(RowSelection).where(
                    RowSelection.tenant_id == tenant_id, RowSelection.dataset_id == ds.id
                )
            ).all()
        for r in stored:
            out[(str(ds.id), r.row_set)] = selection.Selection(
                r.row_set,
                tuple(selection.Filter(f["op"], f["field"], tuple(f["values"])) for f in r.filters),
                r.source,
                r.reason,
            )
    return out


# Settings


def _settings(session: Session, tenant_id: uuid.UUID) -> dict[str, MetricSetting]:
    rows = session.scalars(select(MetricSetting).where(MetricSetting.tenant_id == tenant_id)).all()
    return {r.metric: r for r in rows}


def company_threshold(metric: str, setting: MetricSetting | None) -> Threshold | None:
    default = DEFAULT_THRESHOLDS.get(metric)
    if default is None:
        return None
    if setting is None or setting.high is None or setting.medium is None:
        return default
    return Threshold(Decimal(setting.high), Decimal(setting.medium), default.direction)


# Recalculation


def recalculate(session: Session, tenant_id: uuid.UUID, upload_id: uuid.UUID | None) -> Run:
    """Calculates every figure from the company's current data. Every query names the
    tenant, because this runs as br_system inside the event dispatcher."""
    datasets = intake.datasets_for_metrics(session, tenant_id)
    profile = setup.profile(session, tenant_id)
    # Targets set in the chat or settings come last, so they win over a hand-entered target.
    manual = intake.manual_figures_for(session, tenant_id) + [
        intake.ManualFigureView(
            t.id,
            t.metric,
            t.period,
            t.value,
            "target",
            f"{t.set_by_name} ({'setup chat' if t.source == 'chat' else 'settings'})",
            t.updated_at,
        )
        for t in setup.targets(session, tenant_id)
    ]
    currency = profile.reporting_currency
    ctx = compute.Context(datasets, _selections(session, tenant_id, datasets), manual, currency)
    figures = compute.compute_all(ctx)
    annual = compute.annual_revenue(figures)
    run = Run(
        tenant_id=tenant_id,
        upload_id=upload_id,
        annual_revenue=str(annual) if annual is not None else None,
        band=profile.display_band if profile.display_band is not None else band_for(annual),
        currency=currency,
    )
    session.add(run)
    session.flush()
    settings = _settings(session, tenant_id)
    for f in figures:
        measure = f.risk_measure if f.risk_measure is not None else f.value
        session.add(
            FigureRecord(
                tenant_id=tenant_id,
                run_id=run.id,
                metric=f.metric,
                period=f.period,
                value=str(f.value) if f.value is not None else None,
                status=f.status,
                formula_version=f.formula_version,
                method=f.method,
                custom=f.custom,
                inputs=f.inputs,
                lineage=f.lineage.to_json(),
                extra=f.extra,
                risk_measure=str(measure) if measure is not None else None,
                risk_common=risk(measure, DEFAULT_THRESHOLDS.get(f.metric)),
                risk_company=risk(measure, company_threshold(f.metric, settings.get(f.metric))),
            )
        )
    session.flush()
    emit(
        session,
        MetricsOutbox,
        FIGURES_COMPUTED,
        tenant_id,
        {"upload_id": str(upload_id) if upload_id else None, "run_id": str(run.id)},
    )
    return run


@consumer(
    "metrics.recalculate", "intake.dataset_ready", "intake.figure_entered", "setup.settings_changed"
)
def _recalculate(session: Session, event: Event) -> None:
    assert event.tenant_id is not None  # noqa: S101
    upload = event.payload.get("upload_id")
    recalculate(session, event.tenant_id, uuid.UUID(upload) if upload else None)


# Reading


def latest_run(session: Session, tenant_id: uuid.UUID) -> Run | None:
    return session.scalar(
        select(Run).where(Run.tenant_id == tenant_id).order_by(Run.created_at.desc()).limit(1)
    )


@dataclass
class Tile:
    figure: FigureRecord
    display: str
    previous: FigureRecord | None
    previous_display: str | None
    source_line: str
    risk: str | None


def _display(f: FigureRecord, band: int, currency: str, settings: dict[str, MetricSetting]) -> str:
    if f.value is None:
        return STATUS_WORDS.get(f.status, "Not provided")
    offset = settings[f.metric].band_offset if f.metric in settings else 0
    return format_value(Decimal(f.value), f.metric, band + offset, currency)


def source_line(f: FigureRecord) -> str:
    """The minimised source line under a tile (MetricTile guideline)."""
    parts = []
    for d in f.lineage.get("datasets", []):
        rows = len(d["rows"])
        parts.append(f"{d['filename']}, {rows} row{'s' if rows != 1 else ''}")
    for m in f.lineage.get("manual", []):
        parts.append(f"Entered by {m['entered_by']}, {m['entered_at'][:10]}")
    if not parts:
        return {
            "no_plan": "Enter a target to compare against plan",
            "not_provided": "Not in your files yet",
        }.get(f.status, "Not in your files yet")
    text = "; ".join(parts)
    return f"{text}. Custom method" if f.custom else text


def tiles(
    session: Session, tenant_id: uuid.UUID, include_hidden: bool = False
) -> tuple[Run | None, list[Tile]]:
    run = latest_run(session, tenant_id)
    if run is None:
        return None, []
    settings = _settings(session, tenant_id)
    figures = session.scalars(
        select(FigureRecord).where(
            FigureRecord.tenant_id == tenant_id, FigureRecord.run_id == run.id
        )
    ).all()
    by_metric: dict[str, list[FigureRecord]] = {}
    for f in figures:
        by_metric.setdefault(f.metric, []).append(f)
    out = []
    for key in METRICS:
        if key not in by_metric or (
            not include_hidden and key in settings and settings[key].hidden
        ):
            continue
        history = sorted(by_metric[key], key=lambda f: f.period)
        latest = history[-1]
        previous = history[-2] if len(history) > 1 else None
        out.append(
            Tile(
                latest,
                _display(latest, run.band, run.currency, settings),
                previous,
                _display(previous, run.band, run.currency, settings) if previous else None,
                source_line(latest),
                latest.risk_company,
            )
        )
    return run, out


def trace(session: Session, tenant_id: uuid.UUID, figure_id: uuid.UUID) -> dict[str, Any]:
    """Everything the click view shows (FR-5.4): exact value, source, what it moves, risk."""
    f = session.scalar(
        select(FigureRecord).where(
            FigureRecord.tenant_id == tenant_id, FigureRecord.id == figure_id
        )
    )
    if f is None:
        raise MetricsError(404, "That figure was not found.")
    run = session.get(Run, f.run_id)
    assert run is not None  # noqa: S101
    settings = _settings(session, tenant_id)
    metric = METRICS[f.metric]
    sources = []
    for d in f.lineage.get("datasets", []):
        rows = intake.dataset_rows(session, tenant_id, uuid.UUID(d["dataset_id"]), d["rows"][:50])
        sources.append(
            {
                "filename": d["filename"],
                "kind": d["kind"],
                "dataset_version": d["version"],
                "fields": d["fields"],
                "row_count": len(d["rows"]),
                "selections": d["selections"],
                "rows": [
                    {"row": n + 1, **{k: v for k, v in data.items() if k != "_source"}}
                    for n, data in rows
                ],
            }
        )
    threshold = company_threshold(f.metric, settings.get(f.metric))
    return {
        "id": str(f.id),
        "metric": f.metric,
        "label": metric.label,
        "period": f.period,
        "value": f.value,
        "status": f.status,
        "display": _display(f, run.band, run.currency, settings),
        "formula": metric.formula,
        "formula_version": f.formula_version,
        "method": f.method,
        "custom": f.custom,
        "method_note": (
            f"Company-specific method: {VARIANT_FORMULAS[f.method]}. Used because the standard "
            "formula cannot work with this company's data."
        )
        if f.custom
        else None,
        "inputs": f.inputs,
        "extra": f.extra,
        "sources": sources,
        "entered_by_hand": f.lineage.get("manual", []),
        "moves": [METRICS[m].label for m in metric.moves],
        "risk": f.risk_company,
        "thresholds": None
        if threshold is None
        else {
            "high": str(threshold.high),
            "medium": str(threshold.medium),
            "direction": threshold.direction,
        },
        "check": "The number check tests this figure wherever an update's commentary writes it.",
    }


def get_settings_view(session: Session, tenant_id: uuid.UUID) -> list[dict[str, Any]]:
    settings = _settings(session, tenant_id)
    out = []
    for key, m in METRICS.items():
        if m.phase != 1:
            continue
        s = settings.get(key)
        default = DEFAULT_THRESHOLDS.get(key)
        own = company_threshold(key, s)
        out.append(
            {
                "metric": key,
                "label": m.label,
                "hidden": bool(s and s.hidden),
                "band_offset": s.band_offset if s else 0,
                "default_thresholds": None
                if default is None
                else {
                    "high": str(default.high),
                    "medium": str(default.medium),
                    "direction": default.direction,
                },
                "thresholds": None
                if own is None
                else {"high": str(own.high), "medium": str(own.medium), "direction": own.direction},
            }
        )
    return out


def update_setting(
    session: Session,
    tenant_id: uuid.UUID,
    actor: uuid.UUID,
    metric: str,
    hidden: bool | None,
    band_offset: int | None,
    high: Decimal | None,
    medium: Decimal | None,
    reset_thresholds: bool = False,
) -> None:
    if metric not in METRICS or METRICS[metric].phase != 1:
        raise MetricsError(404, "That measure was not found.")
    if (high is not None or medium is not None) and metric not in DEFAULT_THRESHOLDS:
        raise MetricsError(422, "This measure has no warning lines.")
    if (high is None) != (medium is None):
        raise MetricsError(422, "Give both warning lines.")
    if high is not None and medium is not None:
        direction = DEFAULT_THRESHOLDS[metric].direction
        if (direction == "below" and high > medium) or (direction == "above" and high < medium):
            raise MetricsError(422, "The high-risk line must be beyond the medium-risk line.")
    s = session.get(MetricSetting, (tenant_id, metric)) or MetricSetting(
        tenant_id=tenant_id, metric=metric, hidden=False, band_offset=0
    )
    session.add(s)
    if hidden is not None:
        s.hidden = hidden
    if band_offset is not None:
        if band_offset not in (-1, 0, 1):
            raise MetricsError(422, "Move the display up or down one step at most.")
        s.band_offset = band_offset
    if reset_thresholds:
        s.high = s.medium = None
    elif high is not None and medium is not None:
        s.high, s.medium = str(high), str(medium)
    session.flush()
    audit.record(
        session,
        "metrics.setting_changed",
        tenant_id=tenant_id,
        actor_user_id=actor,
        target_type="metric",
        target_id=metric,
    )
    # The company's own risk levels follow its warning lines straight away.
    run = latest_run(session, tenant_id)
    if run is not None:
        threshold = company_threshold(metric, s)
        for f in session.scalars(
            select(FigureRecord).where(
                FigureRecord.tenant_id == tenant_id,
                FigureRecord.run_id == run.id,
                FigureRecord.metric == metric,
            )
        ).all():
            measure = Decimal(f.risk_measure) if f.risk_measure is not None else None
            f.risk_company = risk(measure, threshold)


# For the updates module (E5). Every query names the tenant: update creation runs as
# br_system inside the event dispatcher.


@dataclass(frozen=True)
class FigureView:
    id: uuid.UUID
    metric: str
    label: str
    unit: str
    period: str
    value: str | None
    status: str
    display: str
    source_line: str
    risk: str | None


def run_for_upload(
    session: Session, tenant_id: uuid.UUID, upload_id: uuid.UUID
) -> uuid.UUID | None:
    """The calculation made when this upload's data arrived."""
    return session.scalar(
        select(Run.id)
        .where(Run.tenant_id == tenant_id, Run.upload_id == upload_id)
        .order_by(Run.created_at.desc())
        .limit(1)
    )


def figures_from_dataset(
    session: Session, tenant_id: uuid.UUID, run_id: uuid.UUID, dataset_id: uuid.UUID
) -> list[uuid.UUID]:
    """The latest figure of each measure in the run that uses rows of this dataset, in
    registry order, leaving out measures the company has hidden."""
    settings = _settings(session, tenant_id)
    latest: dict[str, FigureRecord] = {}
    for f in session.scalars(
        select(FigureRecord).where(
            FigureRecord.tenant_id == tenant_id, FigureRecord.run_id == run_id
        )
    ):
        used = {d["dataset_id"] for d in f.lineage.get("datasets", [])}
        hidden = f.metric in settings and settings[f.metric].hidden
        wanted = str(dataset_id) in used and not hidden and f.value is not None
        if wanted and (f.metric not in latest or f.period > latest[f.metric].period):
            latest[f.metric] = f
    return [latest[k].id for k in METRICS if k in latest]


def figure_view(
    session: Session, tenant_id: uuid.UUID, figure_id: uuid.UUID, override: Decimal | None = None
) -> FigureView | None:
    """A figure as an update shows it. With ``override``, the value a person entered in the
    update, formatted by the same code at the same precision."""
    f = session.scalar(
        select(FigureRecord).where(
            FigureRecord.tenant_id == tenant_id, FigureRecord.id == figure_id
        )
    )
    if f is None:
        return None
    run = session.get(Run, f.run_id)
    assert run is not None  # noqa: S101
    settings = _settings(session, tenant_id)
    metric = METRICS[f.metric]
    if override is None:
        display = _display(f, run.band, run.currency, settings)
    else:
        offset = settings[f.metric].band_offset if f.metric in settings else 0
        display = format_value(override, f.metric, run.band + offset, run.currency)
    return FigureView(
        f.id,
        f.metric,
        metric.label,
        metric.unit.value,
        f.period,
        str(override) if override is not None else f.value,
        f.status,
        display,
        source_line(f),
        f.risk_company,
    )


# For commentary (E6): what skill 3 may see about a figure. Calculated values only.

COUNT_INPUTS = {"open_deals", "won", "lost", "won_count", "stalled"}
SHARE_METRICS = {"revenue_vs_plan", "stalled_deals"}
NO_MEASURE = Decimal(999)  # the risk measure used when runway is unlimited


@dataclass(frozen=True)
class CommentaryFigure:
    key: str
    label: str
    unit: str
    period: str
    value: Decimal
    shown_as: str
    previous_period: str | None
    previous_value: Decimal | None
    previous_shown_as: str | None
    risk: str | None
    inputs: dict[str, Decimal]
    share_of_target: Decimal | None


def commentary_figure(
    session: Session, tenant_id: uuid.UUID, figure_id: uuid.UUID
) -> CommentaryFigure | None:
    f = session.scalar(
        select(FigureRecord).where(
            FigureRecord.tenant_id == tenant_id, FigureRecord.id == figure_id
        )
    )
    if f is None or f.value is None:
        return None
    run = session.get(Run, f.run_id)
    assert run is not None  # noqa: S101
    settings = _settings(session, tenant_id)
    previous = session.scalar(
        select(FigureRecord)
        .where(
            FigureRecord.tenant_id == tenant_id,
            FigureRecord.run_id == f.run_id,
            FigureRecord.metric == f.metric,
            FigureRecord.period < f.period,
            FigureRecord.value.is_not(None),
        )
        .order_by(FigureRecord.period.desc())
        .limit(1)
    )
    inputs = {}
    for name, amount in f.inputs.items():
        if name in COUNT_INPUTS or name == f.metric:
            continue
        try:
            inputs[name] = Decimal(amount)
        except (ArithmeticError, ValueError):
            continue
    share = None
    if f.metric in SHARE_METRICS and f.risk_measure is not None:
        measure = Decimal(f.risk_measure)
        share = None if measure == NO_MEASURE else measure
    return CommentaryFigure(
        f.metric,
        METRICS[f.metric].label,
        METRICS[f.metric].unit.value,
        f.period,
        Decimal(f.value),
        _display(f, run.band, run.currency, settings),
        previous.period if previous else None,
        Decimal(previous.value) if previous and previous.value is not None else None,
        _display(previous, run.band, run.currency, settings) if previous else None,
        f.risk_company,
        inputs,
        share,
    )


def run_currency(session: Session, tenant_id: uuid.UUID, run_id: uuid.UUID) -> str:
    """The currency a run's figures are in."""
    found = session.scalar(select(Run.currency).where(Run.tenant_id == tenant_id, Run.id == run_id))
    return found or "GBP"


# For the investor overview (E7). Levels there use the common lines only (FR-7.2): a
# company's own lines apply on its own pages.

# Placeholder lines for days since the last shared update, an open decision (OPEN.md).
LAST_UPDATE_DAYS = Threshold(Decimal(35), Decimal(20), "above")


def common_risk(
    session: Session, tenant_id: uuid.UUID, figure_id: uuid.UUID, override: Decimal | None = None
) -> str | None:
    """The level on the common lines, also for a figure a person changed in an update."""
    f = session.scalar(
        select(FigureRecord).where(
            FigureRecord.tenant_id == tenant_id, FigureRecord.id == figure_id
        )
    )
    if f is None:
        return None
    if override is None:
        return f.risk_common
    measure: Decimal | None = override
    if f.metric == "revenue_vs_plan":
        # The level is on revenue as a share of target, and the figure is revenue less target.
        target = Decimal(f.inputs["target"]) if f.inputs.get("target") else None
        measure = (target + override) / target if target else None
    elif f.metric in SHARE_METRICS:
        return f.risk_common
    return risk(measure, DEFAULT_THRESHOLDS.get(f.metric))


def last_update_risk(days: int) -> str | None:
    return risk(Decimal(days), LAST_UPDATE_DAYS)
