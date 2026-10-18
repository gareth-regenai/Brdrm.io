"""Every figure is calculated here, by code, from stored rows (FR-1.1). Nothing in this file
reads an AI response: skill 2 only decides which rows each row set holds.

Each figure carries its lineage (FR-1.2): the formula version, the method, and for every
input either the dataset version and row numbers it came from, or the person and date of a
hand-entered figure.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from boardroom.modules.intake.service import DatasetView, ManualFigureView
from boardroom.modules.metrics.registry import METRICS, STALLED_AFTER_DAYS
from boardroom.modules.metrics.selection import Selection

ZERO = Decimal(0)
REVENUE_TARGET_NAMES = frozenset({"revenue", "sales", "income", "turnover", "total revenue"})
BOOKINGS_TARGET_NAMES = frozenset(
    {"closed won", "closed_won", "bookings", "new business", "sales target"}
)


# Lineage


@dataclass
class Lineage:
    datasets: dict[str, dict[str, Any]] = field(default_factory=dict)
    manual: list[dict[str, str]] = field(default_factory=list)

    def add_rows(
        self, ds: DatasetView, rows: list[int], fields: set[str], selection: Selection | None
    ) -> None:
        entry = self.datasets.setdefault(
            str(ds.id),
            {
                "dataset_id": str(ds.id),
                "kind": ds.kind,
                "version": ds.version,
                "upload_id": str(ds.upload_id),
                "filename": ds.filename,
                "rows": [],
                "fields": [],
                "selections": [],
            },
        )
        entry["rows"] = sorted(set(entry["rows"]) | set(rows))
        entry["fields"] = sorted(set(entry["fields"]) | fields)
        if selection is not None and selection.to_json() not in entry["selections"]:
            entry["selections"].append(selection.to_json())

    def add_manual(self, m: ManualFigureView) -> None:
        item = {
            "figure_id": str(m.id),
            "metric": m.metric,
            "period": m.period,
            "kind": m.kind,
            "entered_by": m.entered_by_name,
            "entered_at": m.entered_at.isoformat(),
        }
        if item not in self.manual:
            self.manual.append(item)

    def merge(self, other: "Lineage") -> None:
        for key, entry in other.datasets.items():
            mine = self.datasets.setdefault(
                key, {**entry, "rows": [], "fields": [], "selections": []}
            )
            mine["rows"] = sorted(set(mine["rows"]) | set(entry["rows"]))
            mine["fields"] = sorted(set(mine["fields"]) | set(entry["fields"]))
            for s in entry["selections"]:
                if s not in mine["selections"]:
                    mine["selections"].append(s)
        for m in other.manual:
            if m not in self.manual:
                self.manual.append(m)

    def to_json(self) -> dict[str, Any]:
        return {"datasets": list(self.datasets.values()), "manual": self.manual}

    def empty(self) -> bool:
        return not self.datasets and not self.manual


@dataclass
class Value:
    amount: Decimal
    lineage: Lineage
    custom: bool = False


@dataclass
class Figure:
    metric: str
    period: str
    value: Decimal | None
    status: str  # ok, not_provided, cash_generative, no_plan, target_met
    lineage: Lineage = field(default_factory=Lineage)
    method: str = "standard"
    inputs: dict[str, str] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)
    # What the risk level is read from, when it is not the value itself.
    risk_measure: Decimal | None = None

    @property
    def custom(self) -> bool:
        return self.method != "standard"

    @property
    def formula_version(self) -> str:
        return METRICS[self.metric].version


# Helpers


def dec(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def present(pairs: Iterable[tuple[int, Decimal | None]]) -> list[tuple[int, Decimal]]:
    """Keeps the rows that have a value, so a blank cell is never read as zero."""
    return [(n, v) for n, v in pairs if v is not None]


def month_add(period: str, months: int) -> str:
    y, m = (int(x) for x in period.split("-"))
    index = y * 12 + (m - 1) + months
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def month_of(d: str | date | None) -> str | None:
    if d is None:
        return None
    return str(d)[:7]


class Context:
    def __init__(
        self,
        datasets: list[DatasetView],
        selections: dict[tuple[str, str], Selection],
        manual: list[ManualFigureView],
        currency: str = "GBP",
        today: date | None = None,
    ) -> None:
        self.datasets = datasets  # newest first
        self.selections = selections
        self.manual = manual
        self.currency = currency
        self.today = today or date.today()

    def rows(
        self, ds: DatasetView, row_set: str
    ) -> tuple[Selection | None, list[tuple[int, dict[str, Any]]]]:
        selection = self.selections.get((str(ds.id), row_set))
        if selection is None:
            return None, list(ds.rows)
        return selection, selection.apply(ds.rows)

    def newest(self, kind: str, *fields: str) -> DatasetView | None:
        for ds in self.datasets:
            if ds.kind == kind and all(f in ds.fields for f in fields):
                return ds
        return None

    def manual_value(self, metric: str, period: str, kind: str) -> ManualFigureView | None:
        found = [
            m for m in self.manual if m.metric == metric and m.period == period and m.kind == kind
        ]
        return found[-1] if found else None

    # Finance values by month

    def finance(self, fld: str, period: str) -> Value | None:
        ds = self.newest("finance", fld, "period")
        if ds is not None:
            selection, rows = self.rows(ds, "finance_actuals")
            used = present((n, dec(r.get(fld))) for n, r in rows if r.get("period") == period)
            if used:
                lineage = Lineage()
                lineage.add_rows(ds, [n for n, _ in used], {fld, "period"}, selection)
                return Value(sum((v for _, v in used), ZERO), lineage)
        m = self.manual_value(fld, period, "actual")
        if m is not None:
            lineage = Lineage()
            lineage.add_manual(m)
            return Value(m.value, lineage)
        return None

    def finance_periods(self) -> list[str]:
        periods: set[str] = set()
        for ds in self.datasets:
            if ds.kind == "finance" and "period" in ds.fields:
                _, rows = self.rows(ds, "finance_actuals")
                periods |= {r["period"] for _, r in rows if r.get("period")}
        periods |= {
            m.period
            for m in self.manual
            if m.kind == "actual"
            and m.metric in ("revenue", "cost_of_sales", "operating_expenses", "cash_balance")
        }
        return sorted(periods)

    def target(self, names: frozenset[str], manual_metric: str, period: str) -> Value | None:
        m = self.manual_value(manual_metric, period, "target")
        if m is not None:
            lineage = Lineage()
            lineage.add_manual(m)
            return Value(m.value, lineage)
        ds = self.newest("plan", "metric", "period", "target_value")
        if ds is None:
            return None
        used = present(
            (n, dec(r["target_value"]))
            for n, r in ds.rows
            if str(r.get("metric", "")).strip().lower() in names and r.get("period") == period
        )
        if not used:
            return None
        lineage = Lineage()
        lineage.add_rows(ds, [n for n, _ in used], {"metric", "period", "target_value"}, None)
        return Value(sum((v for _, v in used), ZERO), lineage)

    # Sales

    def sales(
        self, row_set: str, *fields: str
    ) -> tuple[DatasetView, list[tuple[int, dict[str, Any]]], Selection | None, int] | None:
        """Rows of a sales row set, in this company's currency. Returns how many were left out
        for being in another currency, since conversion arrives in phase 2."""
        ds = self.newest("sales", *fields)
        if ds is None:
            return None
        selection, rows = self.rows(ds, row_set)
        same = [(n, r) for n, r in rows if r.get("currency") in (None, "", self.currency)]
        return ds, same, selection, len(rows) - len(same)

    def sales_as_of(self) -> date:
        dates = [d.data_as_of for d in self.datasets if d.kind == "sales" and d.data_as_of]
        return max(dates) if dates else self.today


# Formulas: finance, per month


def _finance_simple(ctx: Context, metric: str, period: str) -> Figure:
    v = ctx.finance(metric, period)
    if v is None:
        return Figure(metric, period, None, "not_provided")
    return Figure(metric, period, v.amount, "ok", v.lineage, inputs={metric: str(v.amount)})


def revenue(ctx: Context, period: str) -> Figure:
    return _finance_simple(ctx, "revenue", period)


def cash_balance(ctx: Context, period: str) -> Figure:
    return _finance_simple(ctx, "cash_balance", period)


def revenue_growth(ctx: Context, period: str) -> Figure:
    now, before = ctx.finance("revenue", period), ctx.finance("revenue", month_add(period, -1))
    if now is None or before is None or before.amount == 0:
        return Figure("revenue_growth", period, None, "not_provided")
    lineage = Lineage()
    lineage.merge(now.lineage)
    lineage.merge(before.lineage)
    value = (now.amount - before.amount) / before.amount
    return Figure(
        "revenue_growth",
        period,
        value,
        "ok",
        lineage,
        inputs={"revenue": str(now.amount), "revenue_last_month": str(before.amount)},
    )


def gross_margin(ctx: Context, period: str) -> Figure:
    rev, cos = ctx.finance("revenue", period), ctx.finance("cost_of_sales", period)
    if rev is None or cos is None or rev.amount == 0:
        return Figure("gross_margin", period, None, "not_provided")
    lineage = Lineage()
    lineage.merge(rev.lineage)
    lineage.merge(cos.lineage)
    return Figure(
        "gross_margin",
        period,
        (rev.amount - cos.amount) / rev.amount,
        "ok",
        lineage,
        inputs={"revenue": str(rev.amount), "cost_of_sales": str(cos.amount)},
    )


def net_burn(ctx: Context, period: str) -> Figure:
    rev = ctx.finance("revenue", period)
    cos = ctx.finance("cost_of_sales", period)
    opex = ctx.finance("operating_expenses", period)
    if rev and cos and opex:
        lineage = Lineage()
        for v in (rev, cos, opex):
            lineage.merge(v.lineage)
        value = cos.amount + opex.amount - rev.amount
        return Figure(
            "net_burn",
            period,
            value,
            "ok",
            lineage,
            inputs={
                "revenue": str(rev.amount),
                "cost_of_sales": str(cos.amount),
                "operating_expenses": str(opex.amount),
            },
        )
    manual = ctx.manual_value("net_burn", period, "actual")
    if manual is not None:
        lineage = Lineage()
        lineage.add_manual(manual)
        return Figure(
            "net_burn", period, manual.value, "ok", lineage, inputs={"net_burn": str(manual.value)}
        )
    # The standard formula cannot work: fall back to the change in cash, flagged (FR-5.3).
    start, end = (
        ctx.finance("cash_balance", month_add(period, -1)),
        ctx.finance("cash_balance", period),
    )
    if start and end:
        lineage = Lineage()
        lineage.merge(start.lineage)
        lineage.merge(end.lineage)
        return Figure(
            "net_burn",
            period,
            start.amount - end.amount,
            "ok",
            lineage,
            method="cash_movement",
            inputs={"cash_at_start": str(start.amount), "cash_at_end": str(end.amount)},
        )
    return Figure("net_burn", period, None, "not_provided")


def runway(ctx: Context, period: str) -> Figure:
    cash = ctx.finance("cash_balance", period)
    burns = [net_burn(ctx, month_add(period, -i)) for i in range(3)]
    if cash is None or any(b.value is None for b in burns):
        return Figure("runway", period, None, "not_provided")
    lineage = Lineage()
    lineage.merge(cash.lineage)
    for b in burns:
        lineage.merge(b.lineage)
    average = sum((b.value for b in burns if b.value is not None), ZERO) / 3
    method = "cash_movement" if any(b.custom for b in burns) else "standard"
    inputs = {"cash_balance": str(cash.amount), "average_net_burn": str(average)}
    if average <= 0:
        return Figure(
            "runway",
            period,
            None,
            "cash_generative",
            lineage,
            method=method,
            inputs=inputs,
            risk_measure=Decimal(999),
        )
    return Figure(
        "runway", period, cash.amount / average, "ok", lineage, method=method, inputs=inputs
    )


def revenue_vs_plan(ctx: Context, period: str) -> Figure:
    rev = ctx.finance("revenue", period)
    if rev is None:
        return Figure("revenue_vs_plan", period, None, "not_provided")
    target = ctx.target(REVENUE_TARGET_NAMES, "revenue", period)
    if target is None or target.amount == 0:
        return Figure("revenue_vs_plan", period, None, "no_plan")
    lineage = Lineage()
    lineage.merge(rev.lineage)
    lineage.merge(target.lineage)
    share = rev.amount / target.amount
    return Figure(
        "revenue_vs_plan",
        period,
        rev.amount - target.amount,
        "ok",
        lineage,
        inputs={"revenue": str(rev.amount), "target": str(target.amount)},
        extra={"percent_of_plan": str(share), "variance_percent": str(share - 1)},
        risk_measure=share,
    )


# Formulas: sales, as at the latest sales data


def pipeline(ctx: Context, period: str) -> Figure:
    found = ctx.sales("open_deals", "amount")
    if found is None:
        return Figure("pipeline", period, None, "not_provided")
    ds, rows, selection, other = found
    used = present((n, dec(r.get("amount"))) for n, r in rows)
    lineage = Lineage()
    lineage.add_rows(ds, [n for n, _ in used], {"amount", "status"}, selection)
    return Figure(
        "pipeline",
        period,
        sum((v for _, v in used), ZERO),
        "ok",
        lineage,
        inputs={"open_deals": str(len(used))},
        extra={"other_currency_rows_left_out": other} if other else {},
    )


def weighted_pipeline(ctx: Context, period: str) -> Figure:
    found = ctx.sales("open_deals", "amount", "probability")
    if found is None:
        return Figure("weighted_pipeline", period, None, "not_provided")
    ds, rows, selection, other = found
    pairs = [(n, dec(r.get("amount")), dec(r.get("probability"))) for n, r in rows]
    if any(a is None or p is None for _, a, p in pairs):
        missing = sum(1 for _, a, p in pairs if a is None or p is None)
        return Figure(
            "weighted_pipeline",
            period,
            None,
            "not_provided",
            extra={"open_deals_without_amount_or_probability": missing},
        )
    lineage = Lineage()
    lineage.add_rows(ds, [n for n, _, _ in pairs], {"amount", "probability", "status"}, selection)
    value = sum((a * p for _, a, p in pairs if a is not None and p is not None), ZERO)
    return Figure(
        "weighted_pipeline",
        period,
        value,
        "ok",
        lineage,
        inputs={"open_deals": str(len(pairs))},
        extra={"other_currency_rows_left_out": other} if other else {},
    )


def _closed_in(
    rows: list[tuple[int, dict[str, Any]]], period: str
) -> list[tuple[int, dict[str, Any]]]:
    return [(n, r) for n, r in rows if month_of(r.get("closed_date")) == period]


def coverage(ctx: Context, period: str) -> Figure:
    open_ = ctx.sales("open_deals", "amount", "expected_close_date")
    won = ctx.sales("won_deals", "amount", "closed_date")
    if open_ is None or won is None:
        return Figure("coverage", period, None, "not_provided")
    target = ctx.target(BOOKINGS_TARGET_NAMES, "closed_won", period)
    if target is None:
        return Figure("coverage", period, None, "no_plan")
    ods, orows, osel, _ = open_
    wds, wrows, wsel, _ = won
    closing = present(
        (n, dec(r.get("amount")))
        for n, r in orows
        if month_of(r.get("expected_close_date")) == period
    )
    won_now = present((n, dec(r.get("amount"))) for n, r in _closed_in(wrows, period))
    pipeline_due = sum((v for _, v in closing), ZERO)
    won_total = sum((v for _, v in won_now), ZERO)
    lineage = Lineage()
    lineage.add_rows(ods, [n for n, _ in closing], {"amount", "expected_close_date"}, osel)
    lineage.add_rows(wds, [n for n, _ in won_now], {"amount", "closed_date"}, wsel)
    lineage.merge(target.lineage)
    inputs = {
        "pipeline_due": str(pipeline_due),
        "target": str(target.amount),
        "won_so_far": str(won_total),
    }
    remaining = target.amount - won_total
    if remaining <= 0:
        return Figure(
            "coverage",
            period,
            None,
            "target_met",
            lineage,
            inputs=inputs,
            risk_measure=Decimal(999),
        )
    return Figure("coverage", period, pipeline_due / remaining, "ok", lineage, inputs=inputs)


def win_rate(ctx: Context, period: str) -> Figure:
    won, lost = ctx.sales("won_deals", "closed_date"), ctx.sales("lost_deals", "closed_date")
    if won is None or lost is None:
        return Figure("win_rate", period, None, "not_provided")
    w, l_ = _closed_in(won[1], period), _closed_in(lost[1], period)
    if not w and not l_:
        return Figure("win_rate", period, None, "not_provided")
    lineage = Lineage()
    lineage.add_rows(won[0], [n for n, _ in w], {"status", "closed_date"}, won[2])
    lineage.add_rows(lost[0], [n for n, _ in l_], {"status", "closed_date"}, lost[2])
    return Figure(
        "win_rate",
        period,
        Decimal(len(w)) / Decimal(len(w) + len(l_)),
        "ok",
        lineage,
        inputs={"won": str(len(w)), "lost": str(len(l_))},
    )


def avg_deal_size(ctx: Context, period: str) -> Figure:
    won = ctx.sales("won_deals", "amount", "closed_date")
    if won is None:
        return Figure("avg_deal_size", period, None, "not_provided")
    used = present((n, dec(r.get("amount"))) for n, r in _closed_in(won[1], period))
    if not used:
        return Figure("avg_deal_size", period, None, "not_provided")
    lineage = Lineage()
    lineage.add_rows(won[0], [n for n, _ in used], {"amount", "closed_date"}, won[2])
    total = sum((v for _, v in used), ZERO)
    return Figure(
        "avg_deal_size",
        period,
        total / len(used),
        "ok",
        lineage,
        inputs={"won_amount": str(total), "won_count": str(len(used))},
    )


def stalled_deals(ctx: Context, period: str) -> Figure:
    found = ctx.sales("open_deals", "last_activity_date")
    if found is None:
        return Figure("stalled_deals", period, None, "not_provided")
    ds, rows, selection, _ = found
    cutoff = (ctx.sales_as_of() - timedelta(days=STALLED_AFTER_DAYS)).isoformat()
    stalled = [
        n for n, r in rows if r.get("last_activity_date") and r["last_activity_date"] < cutoff
    ]
    unknown = sum(1 for _, r in rows if not r.get("last_activity_date"))
    lineage = Lineage()
    lineage.add_rows(ds, stalled, {"last_activity_date", "status"}, selection)
    share = Decimal(len(stalled)) / Decimal(len(rows)) if rows else ZERO
    extra: dict[str, Any] = {"open_deals": len(rows), "as_of": ctx.sales_as_of().isoformat()}
    if unknown:
        extra["open_deals_without_activity_date"] = unknown
    return Figure(
        "stalled_deals",
        period,
        Decimal(len(stalled)),
        "ok",
        lineage,
        inputs={"stalled": str(len(stalled)), "open_deals": str(len(rows))},
        extra=extra,
        risk_measure=share,
    )


FINANCE_FORMULAS: dict[str, Callable[[Context, str], Figure]] = {
    "revenue": revenue,
    "revenue_growth": revenue_growth,
    "gross_margin": gross_margin,
    "net_burn": net_burn,
    "cash_balance": cash_balance,
    "runway": runway,
    "revenue_vs_plan": revenue_vs_plan,
}
SALES_SNAPSHOT: dict[str, Callable[[Context, str], Figure]] = {
    "pipeline": pipeline,
    "weighted_pipeline": weighted_pipeline,
    "coverage": coverage,
    "stalled_deals": stalled_deals,
}
SALES_MONTHLY: dict[str, Callable[[Context, str], Figure]] = {
    "win_rate": win_rate,
    "avg_deal_size": avg_deal_size,
}


def compute_all(ctx: Context) -> list[Figure]:
    """Every phase 1 figure for every period the data covers."""
    out: list[Figure] = []
    for period in ctx.finance_periods():
        for fn in FINANCE_FORMULAS.values():
            out.append(fn(ctx, period))
    if any(d.kind == "sales" for d in ctx.datasets):
        as_of = month_of(ctx.sales_as_of())
        assert as_of is not None  # noqa: S101
        for fn in SALES_SNAPSHOT.values():
            out.append(fn(ctx, as_of))
        for back in range(12):
            month = month_add(as_of, -back)
            for fn in SALES_MONTHLY.values():
                f = fn(ctx, month)
                if f.status == "ok":
                    out.append(f)
    # A figure that could not be calculated is kept only for the latest period, so the
    # tile can say "Not provided" instead of disappearing.
    latest: dict[str, str] = {}
    for f in out:
        latest[f.metric] = max(latest.get(f.metric, f.period), f.period)
    return [f for f in out if f.status != "not_provided" or f.period == latest[f.metric]]


def annual_revenue(figures: list[Figure]) -> Decimal | None:
    """The last 12 months of revenue, annualised when fewer months are known."""
    months = sorted(
        (f for f in figures if f.metric == "revenue" and f.value is not None),
        key=lambda f: f.period,
    )[-12:]
    if not months:
        return None
    total = sum((f.value for f in months if f.value is not None), ZERO)
    return total * 12 / len(months)
