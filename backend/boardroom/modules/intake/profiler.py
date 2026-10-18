"""A deterministic profile of each column (FR-4.2). Skill 1 reads this, not the file."""

import re
from dataclasses import asdict, dataclass
from datetime import datetime

from boardroom.modules.intake.fields import DATE_FORMATS
from boardroom.modules.intake.parsing import Table

_MONEY = re.compile(
    r"^\(?-?[£$€]?\s?-?\d{1,3}(,\d{3})*(\.\d+)?\)?$|^\(?-?[£$€]?\s?-?\d+(\.\d+)?\)?$"
)
_PERCENT = re.compile(r"^-?\d+(\.\d+)?\s?%$")
_BOOL = frozenset({"true", "false", "yes", "no", "y", "n"})


@dataclass
class ColumnProfile:
    name: str
    inferred_type: str  # empty, integer, decimal, money, percent, date, boolean, text
    null_rate: float
    distinct_count: int
    min: str | None
    max: str | None
    date_formats: list[str]


def _as_date(value: str, fmt: str) -> datetime | None:
    try:
        return datetime.strptime(value, fmt)
    except ValueError:
        return None


def matching_date_formats(values: list[str]) -> list[str]:
    sample = values[:200]
    if not sample:
        return []
    return [f for f in DATE_FORMATS if all(_as_date(v, f) for v in sample)]


def _number(v: str) -> float | None:
    t = v.replace(",", "").replace("£", "").replace("$", "").replace("€", "").replace(" ", "")
    negative = t.startswith("(") and t.endswith(")")
    t = t.strip("()").rstrip("%")
    try:
        n = float(t)
    except ValueError:
        return None
    return -n if negative else n


def profile_column(name: str, values: list[str]) -> ColumnProfile:
    filled = [v for v in values if v]
    null_rate = round(1 - len(filled) / len(values), 3) if values else 1.0
    distinct = len(set(filled))
    if not filled:
        return ColumnProfile(name, "empty", null_rate, 0, None, None, [])

    formats = matching_date_formats(filled)
    numbers = [_number(v) for v in filled]
    if formats and not all(_MONEY.match(v) for v in filled):
        parsed = sorted(d for v in filled if (d := _as_date(v, formats[0])))
        return ColumnProfile(
            name,
            "date",
            null_rate,
            distinct,
            parsed[0].date().isoformat(),
            parsed[-1].date().isoformat(),
            formats,
        )
    if all(_PERCENT.match(v) for v in filled):
        kind = "percent"
    elif all(n is not None for n in numbers):
        if any(c in v for v in filled for c in "£$€") or any("(" in v for v in filled):
            kind = "money"
        elif all(float(n).is_integer() for n in numbers if n is not None):
            kind = "integer"
        else:
            kind = "decimal"
    elif all(v.lower() in _BOOL for v in filled):
        kind = "boolean"
    else:
        kind = "text"

    if kind in ("percent", "money", "integer", "decimal"):
        nums = [n for n in numbers if n is not None]
        return ColumnProfile(name, kind, null_rate, distinct, _fmt(min(nums)), _fmt(max(nums)), [])
    # Text range is length, never values: a profile carries no cell text.
    lengths = sorted(len(v) for v in filled)
    return ColumnProfile(
        name, kind, null_rate, distinct, f"{lengths[0]} chars", f"{lengths[-1]} chars", []
    )


def _fmt(n: float) -> str:
    return str(int(n)) if float(n).is_integer() else f"{n:.4f}".rstrip("0")


def profile(table: Table) -> list[ColumnProfile]:
    return [profile_column(h, [r[i] for r in table.rows]) for i, h in enumerate(table.headers)]


def as_dicts(profiles: list[ColumnProfile]) -> list[dict[str, object]]:
    return [asdict(p) for p in profiles]
