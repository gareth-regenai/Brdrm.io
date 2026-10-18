"""Display precision (FR-5.6) and risk levels (FR-5.7).

Rounding is for reading only: the exact value is always kept and one click away.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from boardroom.modules.metrics.registry import METRICS, Unit

SYMBOLS = {"GBP": "£", "USD": "$", "EUR": "€"}

# Bands by annual revenue (BRD chapter 5). Each is (upper bound, how money is shown).
BAND_LIMITS = (Decimal(100_000), Decimal(1_000_000), Decimal(10_000_000), Decimal(100_000_000))


def band_for(annual_revenue: Decimal | None) -> int:
    revenue = annual_revenue or Decimal(0)
    for i, limit in enumerate(BAND_LIMITS):
        if revenue < limit:
            return i
    return len(BAND_LIMITS)


def _round(value: Decimal, places: int) -> Decimal:
    return value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def format_money(value: Decimal, band: int, currency: str = "GBP") -> str:
    symbol = SYMBOLS.get(currency, f"{currency} ")
    sign = "-" if value < 0 else ""
    v = abs(value)
    band = max(0, min(band, 4))
    million, thousand = Decimal(1_000_000), Decimal(1000)
    if band == 0:
        text = f"{_round(v, 0):,.0f}"
    elif band == 1:
        text = f"{_round(v / thousand, 1):,.1f}k"
    elif band == 2:
        text = (
            f"{_round(v / million, 3):,.3f}m"
            if v >= million
            else f"{_round(v / thousand, 1):,.1f}k"
        )
    elif band == 3:
        text = (
            f"{_round(v / million, 2):,.2f}m"
            if v >= million
            else f"{_round(v / thousand, 0):,.0f}k"
        )
    else:
        text = f"{_round(v / million, 1):,.1f}m"
    return f"{sign}{symbol}{text}"


def format_value(value: Decimal, metric: str, band: int, currency: str = "GBP") -> str:
    """Months and percentages always show one decimal."""
    unit = METRICS[metric].unit
    if unit == Unit.MONEY:
        return format_money(value, band, currency)
    if unit == Unit.MONTHS:
        return f"{_round(value, 1)} months"
    if unit == Unit.PERCENT:
        return f"{_round(value * 100, 1)}%"
    if unit == Unit.RATIO:
        return f"{_round(value, 1)}x"
    return f"{_round(value, 0):,.0f}"


# Risk levels. The default numbers are an open decision (FRD chapter 14, OPEN.md).


@dataclass(frozen=True)
class Threshold:
    high: Decimal
    medium: Decimal
    # "below": a lower value is riskier (runway). "above": a higher value is riskier.
    direction: str = "below"


DEFAULT_THRESHOLDS: dict[str, Threshold] = {
    "runway": Threshold(Decimal(6), Decimal(12)),
    "gross_margin": Threshold(Decimal("0.2"), Decimal("0.4")),
    "revenue_growth": Threshold(Decimal("-0.05"), Decimal(0)),
    # Applied to revenue as a share of target: 0.8 is 80% of plan.
    "revenue_vs_plan": Threshold(Decimal("0.8"), Decimal("0.95")),
    "coverage": Threshold(Decimal(1), Decimal(2)),
    "win_rate": Threshold(Decimal("0.15"), Decimal("0.25")),
    # Applied to stalled deals as a share of open deals.
    "stalled_deals": Threshold(Decimal("0.3"), Decimal("0.15"), "above"),
}


def risk(measure: Decimal | None, threshold: Threshold | None) -> str | None:
    if measure is None or threshold is None:
        return None
    if threshold.direction == "above":
        return (
            "high"
            if measure > threshold.high
            else "medium"
            if measure > threshold.medium
            else "low"
        )
    return "high" if measure < threshold.high else "medium" if measure < threshold.medium else "low"
