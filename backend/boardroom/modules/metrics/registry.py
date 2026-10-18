"""The metric registry (FR-5.1): one fixed, versioned formula per measure.

A formula change means a new version here. Every figure records the version that made it.
The formulas themselves are in compute.py, one function per entry.
"""

from dataclasses import dataclass
from enum import StrEnum


class Unit(StrEnum):
    MONEY = "money"
    MONTHS = "months"
    PERCENT = "percent"  # stored as a fraction: 0.416 is 41.6%
    RATIO = "ratio"  # shown as 2.4x
    COUNT = "count"


@dataclass(frozen=True)
class Metric:
    key: str
    label: str
    unit: Unit
    version: str
    formula: str
    phase: int = 1
    # Other figures this one feeds, for the click view's "what it moves" (FR-5.4).
    moves: tuple[str, ...] = ()
    # A company-specific method, used only when the standard one cannot work (FR-5.3).
    variants: tuple[str, ...] = ()


METRICS: dict[str, Metric] = {
    m.key: m
    for m in (
        Metric(
            "revenue",
            "Revenue",
            Unit.MONEY,
            "1",
            "Revenue for the period",
            moves=("revenue_growth", "gross_margin", "net_burn", "runway", "revenue_vs_plan"),
        ),
        Metric(
            "revenue_growth",
            "Revenue growth",
            Unit.PERCENT,
            "1",
            "(revenue this month - revenue last month) / revenue last month",
        ),
        Metric(
            "gross_margin", "Gross margin", Unit.PERCENT, "1", "(revenue - cost of sales) / revenue"
        ),
        Metric(
            "net_burn",
            "Net monthly burn",
            Unit.MONEY,
            "1",
            "cost of sales + operating expenses - revenue",
            moves=("runway",),
            variants=("cash_movement",),
        ),
        Metric(
            "cash_balance",
            "Cash balance",
            Unit.MONEY,
            "1",
            "Cash at bank at period end",
            moves=("runway",),
        ),
        Metric(
            "runway",
            "Runway",
            Unit.MONTHS,
            "1",
            "latest cash balance / average net burn of the last three months, "
            "or cash-generative if that burn is zero or negative",
        ),
        Metric(
            "revenue_vs_plan",
            "Revenue against plan",
            Unit.MONEY,
            "1",
            "revenue - revenue target, and as a percentage of the target",
        ),
        Metric(
            "pipeline", "Pipeline", Unit.MONEY, "1", "Sum of open deal amounts", moves=("coverage",)
        ),
        Metric(
            "weighted_pipeline",
            "Weighted pipeline",
            Unit.MONEY,
            "1",
            "Sum of open deal amount x probability",
        ),
        Metric(
            "coverage",
            "Pipeline coverage",
            Unit.RATIO,
            "1",
            "open pipeline expected to close in the period / (target - closed-won so far)",
        ),
        Metric(
            "win_rate", "Win rate", Unit.PERCENT, "1", "won / (won + lost), closed in the period"
        ),
        Metric(
            "avg_deal_size",
            "Average deal size",
            Unit.MONEY,
            "1",
            "won amount / won count, closed in the period",
        ),
        Metric(
            "stalled_deals",
            "Stalled deals",
            Unit.COUNT,
            "1",
            "Open deals with no activity for more than 30 days",
        ),
        Metric(
            "delivery_vs_plan",
            "Delivery against plan",
            Unit.PERCENT,
            "1",
            "tasks completed / tasks planned in the period",
            phase=2,
        ),
        Metric(
            "headcount", "Headcount against plan", Unit.COUNT, "1", "Active at period end", phase=2
        ),
    )
}

VARIANT_FORMULAS = {
    "cash_movement": "cash balance at the start of the month - cash balance at the end",
}

STALLED_AFTER_DAYS = 30


# Row sets: the named groups of rows each formula reads. Skill 2 chooses their filters.


@dataclass(frozen=True)
class RowSet:
    key: str
    kind: str
    description: str
    # The standard selection: used when skill 2 is off, unavailable or answers out of schema.
    standard: tuple[tuple[str, str, tuple[str, ...]], ...]  # (op, field, values)


ROW_SETS: dict[str, RowSet] = {
    r.key: r
    for r in (
        RowSet(
            "finance_actuals",
            "finance",
            "Rows that are actual results for the company as a whole: not budgets, "
            "forecasts, or one department's slice.",
            (),
        ),
        RowSet(
            "open_deals",
            "sales",
            "Deals still open: not yet won or lost.",
            (("in", "status", ("open",)),),
        ),
        RowSet("won_deals", "sales", "Deals won.", (("in", "status", ("won",)),)),
        RowSet("lost_deals", "sales", "Deals lost.", (("in", "status", ("lost",)),)),
    )
}
