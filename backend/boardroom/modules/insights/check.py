"""The number check (FR-5.5, BR-5.4). Nothing in commentary can be out.

Every figure written with a unit is found: money (£1.4m, £78.1k, €950), percentages
(91.6%), ratios (2.4x) and months (17.6 months). It passes only if it is a real figure
rounded half up to the precision written, with the same unit. No tolerance band: £1.4m
passes for £1,378,000 and £1.5m fails.

Real figures are the update's figures, their values last period, the change between the
two (so "runway fell 1.5 months" can pass), the money inputs a figure was calculated
from, and revenue as a share of target.

Ignored, because they are not figures: dates ("12 December", "Sep 2026", "2026"),
quarters ("Q3"), and counts of things ("2 deals", "the last 3 months"). In practice that
is any number written without a unit, and a whole number of months, since months are
always written with one decimal (BR-5 business rules).
"""

import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

SYMBOLS = {"£": "GBP", "€": "EUR", "$": "USD"}
SCALES = {
    "k": Decimal(1000),
    "thousand": Decimal(1000),
    "m": Decimal(1_000_000),
    "million": Decimal(1_000_000),
    "bn": Decimal(1_000_000_000),
    "billion": Decimal(1_000_000_000),
}

_FIGURE = re.compile(
    r"(?P<cur>[£€$])?\s?"
    r"(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(?:\s?(?P<suffix>bn|billion|million|thousand|k|m|%|x|months?)(?![A-Za-z0-9]))?",
    re.I,
)


@dataclass(frozen=True)
class Candidate:
    """A real figure a written one may round to."""

    unit: str  # money, percent, ratio, months
    value: Decimal  # money in units, percent as a fraction
    label: str


@dataclass(frozen=True)
class Found:
    text: str
    unit: str
    matched: str | None  # the label of the real figure it rounds to


@dataclass(frozen=True)
class Result:
    found: list[Found] = field(default_factory=list)

    @property
    def failures(self) -> list[Found]:
        return [f for f in self.found if f.matched is None]

    @property
    def passed(self) -> bool:
        return not self.failures

    def to_json(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "figures": [{"text": f.text, "unit": f.unit, "matched": f.matched} for f in self.found],
        }


def _round(value: Decimal, places: int) -> Decimal:
    return value.quantize(Decimal(1).scaleb(-places), ROUND_HALF_UP)


def _matches(written: Decimal, places: int, real: Decimal) -> bool:
    return _round(abs(real), places) == written


def check(text: str, candidates: list[Candidate], currency: str = "GBP") -> Result:
    found: list[Found] = []
    for m in _FIGURE.finditer(text):
        cur, num, suffix = m.group("cur"), m.group("num"), (m.group("suffix") or "").lower()
        start = m.start("cur") if cur else m.start("num")
        before = text[max(0, start - 1) : start]
        if before.isalpha() or before.isdigit():
            continue  # part of a word or a code, such as Q3 or SKU12
        try:
            written = Decimal(num.replace(",", ""))
        except InvalidOperation:
            continue
        places = len(num.split(".")[1]) if "." in num else 0
        shown = m.group(0).strip()
        if cur or suffix in SCALES:
            unit = "money"
            if cur and SYMBOLS[cur] != currency:
                found.append(Found(shown, unit, None))  # the wrong currency is wrong
                continue
            scale = SCALES.get(suffix, Decimal(1))
            match = next(
                (
                    c.label
                    for c in candidates
                    if c.unit == unit and _matches(written, places, c.value / scale)
                ),
                None,
            )
        elif suffix == "%":
            unit = "percent"
            match = next(
                (
                    c.label
                    for c in candidates
                    if c.unit == unit and _matches(written, places, c.value * 100)
                ),
                None,
            )
        elif suffix == "x":
            unit = "ratio"
            match = next(
                (
                    c.label
                    for c in candidates
                    if c.unit == unit and _matches(written, places, c.value)
                ),
                None,
            )
        elif suffix.startswith("month") and places > 0:
            unit = "months"
            match = next(
                (
                    c.label
                    for c in candidates
                    if c.unit == unit and _matches(written, places, c.value)
                ),
                None,
            )
        else:
            continue  # a date, a year, a quarter or a count of things
        found.append(Found(shown, unit, match))
    return Result(found)
