"""Deterministic code applies a confirmed interpretation (FR-4.5). The AI never edits data:
the same file and interpretation always produce the same dataset."""

import calendar
import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from boardroom.modules.intake.fields import DATE_FORMATS, IGNORE_BELOW, FieldType
from boardroom.modules.intake.fields import field as field_def
from boardroom.modules.intake.parsing import Table
from boardroom.modules.intake.skill1 import ColumnMapping, Interpretation

_MONTH_FORMATS = ("%b %Y", "%B %Y", "%b-%y", "%b %y", "%Y-%m", "%m/%Y", "%Y-%m-%d", "%d/%m/%Y")


@dataclass
class Dataset:
    kind: str
    rows: list[dict[str, Any]]  # canonical fields, plus "_source" pointing back to the file
    invalid_cells: int = 0
    data_as_of: date | None = None
    fields: list[str] = field(default_factory=list)

    def fingerprint(self) -> str:
        body = json.dumps(self.rows, sort_keys=True, default=str)
        return hashlib.sha256(body.encode()).hexdigest()


# Value parsing


def parse_decimal(text: str) -> Decimal | None:
    t = text.strip()
    if not t:
        return None
    negative = (t.startswith("(") and t.endswith(")")) or t.endswith("-")
    t = t.strip("()").rstrip("-")
    for symbol in ("£", "$", "€", ",", " ", " ", "GBP", "USD", "EUR"):
        t = t.replace(symbol, "")
    multiplier = Decimal(1)
    if t[-1:].lower() == "k":
        multiplier, t = Decimal(1000), t[:-1]
    elif t[-1:].lower() == "m":
        multiplier, t = Decimal(1_000_000), t[:-1]
    if t.endswith("%"):
        t = t[:-1]
    try:
        value = Decimal(t) * multiplier
    except InvalidOperation:
        return None
    return -value if negative and value > 0 else value


def parse_date(text: str, fmt: str | None, fallback_formats: list[str]) -> date | None:
    t = text.strip()
    if not t:
        return None
    for f in ([fmt] if fmt else []) + fallback_formats + ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S"]:
        try:
            return datetime.strptime(t, f).date()
        except ValueError:
            continue
    return None


def parse_month(text: str, fmt: str | None = None) -> str | None:
    t = " ".join(text.strip().split())
    for f in ([fmt] if fmt else []) + list(_MONTH_FORMATS):
        try:
            return datetime.strptime(t, f).strftime("%Y-%m")
        except ValueError:
            continue
    return None


def _column_date_formats(values: list[str]) -> list[str]:
    sample = [v for v in values if v][:500]
    good = []
    for f in DATE_FORMATS:
        try:
            for v in sample:
                datetime.strptime(v, f)
            good.append(f)
        except ValueError:
            continue
    return good


# Transforms


def _apply_transform(value: str, row: dict[str, str], m: ColumnMapping) -> str:
    t = m.transform
    if t.type == "split" and t.separator:
        parts = value.split(t.separator)
        return (
            parts[t.part].strip()
            if t.part is not None and -len(parts) <= t.part < len(parts)
            else ""
        )
    if t.type == "combine" and t.with_column:
        other = row.get(t.with_column, "")
        return f"{value}{t.separator or ' '}{other}".strip() if other else value
    if t.type == "map_values":
        lookup = {a.strip().lower(): b for a, b in t.mapping}
        return lookup.get(value.strip().lower(), value)
    return value


def _coerce(kind: str, m: ColumnMapping, value: str, formats: list[str]) -> tuple[Any, bool]:
    """Returns (stored value, valid). Money and numbers are stored as decimal strings."""
    f = field_def(kind, m.field)
    if f is None or not value.strip():
        return None, True
    if f.type in (FieldType.MONEY, FieldType.NUMBER):
        n = parse_decimal(value)
        if n is None:
            return None, False
        if m.transform.type == "scale" and m.transform.factor is not None:
            n = n * Decimal(str(m.transform.factor))
        if m.transform.type == "flip_sign":
            n = -n
        # Plain notation at the precision the file gave: "58000.00" stays "58000.00".
        return format(n, "f"), True
    if f.type == FieldType.PERCENT:
        n = parse_decimal(value)
        if n is None:
            return None, False
        if "%" in value or n > 1:
            n = n / 100
        return format(n.normalize(), "f"), True
    fmt = m.transform.date_format if m.transform.type == "parse_date" else None
    if f.type == FieldType.DATE:
        d = parse_date(value, fmt, formats)
        return (d.isoformat(), True) if d else (None, False)
    if f.type == FieldType.MONTH:
        month = parse_month(value, fmt)
        if month is None:
            d = parse_date(value, fmt, formats)
            month = d.strftime("%Y-%m") if d else None
        return (month, True) if month else (None, False)
    return value.strip(), True


# Layouts


def used_mappings(interp: Interpretation, confirmed: set[str]) -> list[ColumnMapping]:
    """Mappings that feed the dataset: not ignored, and either confident enough or confirmed."""
    return [
        m
        for m in interp.columns
        if m.field != "ignore" and (m.confidence >= IGNORE_BELOW or m.column in confirmed)
    ]


def _rows_layout(table: Table, interp: Interpretation, confirmed: set[str]) -> Dataset:
    mappings = used_mappings(interp, confirmed)
    index = {h: i for i, h in enumerate(table.headers)}
    formats = {
        m.column: _column_date_formats([r[index[m.column]] for r in table.rows]) for m in mappings
    }
    out, invalid = [], 0
    for n, cells in enumerate(table.rows):
        raw = dict(zip(table.headers, cells, strict=True))
        record: dict[str, Any] = {}
        for m in mappings:
            value = _apply_transform(raw[m.column], raw, m)
            stored, ok = _coerce(interp.file_kind, m, value, formats[m.column])
            invalid += 0 if ok else 1
            if stored is not None and record.get(m.field) is None:
                record[m.field] = stored
        if record:
            record["_source"] = {"rows": [n]}
            out.append(record)
    return Dataset(interp.file_kind, out, invalid, fields=sorted({m.field for m in mappings}))


def _periods_layout(table: Table, interp: Interpretation, confirmed: set[str]) -> Dataset:
    assert interp.label_column is not None  # noqa: S101
    label_idx = table.headers.index(interp.label_column)
    periods = {
        i: p for i, h in enumerate(table.headers) if i != label_idx and (p := parse_month(h))
    }
    labels = {
        r.label: r.field
        for r in interp.row_labels
        if r.field != "ignore" and (r.confidence >= IGNORE_BELOW or r.label in confirmed)
    }
    by_period: dict[str, dict[str, Any]] = {}
    invalid = 0
    for n, cells in enumerate(table.rows):
        target = labels.get(cells[label_idx])
        if not target:
            continue
        f = field_def(interp.file_kind, target)
        for col, period in periods.items():
            value = cells[col] if col < len(cells) else ""
            if not value.strip():
                continue
            number = parse_decimal(value)
            if number is None or f is None:
                invalid += 1
                continue
            record = by_period.setdefault(
                period, {"period": period, "_source": {"rows": [], "columns": []}}
            )
            if record.get(target) is None:
                record[target] = format(number, "f")
                record["_source"]["rows"].append(n)
                record["_source"]["columns"].append(table.headers[col])
    rows = [by_period[p] for p in sorted(by_period)]
    fields = sorted({"period", *labels.values()}) if rows else []
    return Dataset(interp.file_kind, rows, invalid, fields=fields)


def _as_of(ds: Dataset) -> date | None:
    if ds.kind in ("finance", "plan"):
        months = [r["period"] for r in ds.rows if r.get("period")]
        if not months:
            return None
        y, m = (int(x) for x in max(months).split("-"))
        return date(y, m, calendar.monthrange(y, m)[1])
    keys = {
        "sales": ("created_date", "closed_date", "last_activity_date"),
        "delivery": ("completed_date", "due_date"),
        "people": ("start_date", "end_date", "requisition_opened_date"),
    }.get(ds.kind, ())
    dates = [r[k] for r in ds.rows for k in keys if r.get(k)]
    # Future dates (an expected close) are not evidence of how current the data is.
    today = date.today().isoformat()
    past = [d for d in dates if d <= today]
    return date.fromisoformat(max(past)) if past else None


def apply(table: Table, interp: Interpretation, confirmed: set[str] | None = None) -> Dataset:
    confirmed = confirmed or set()
    if interp.layout == "periods_as_columns":
        ds = _periods_layout(table, interp, confirmed)
    else:
        ds = _rows_layout(table, interp, confirmed)
    ds.data_as_of = _as_of(ds)
    return ds
