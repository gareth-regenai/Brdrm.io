"""Redacted samples for skill 1 (FR-4.3, FR-11.4). Numbers, dates and short labels stay,
because they are what tells one column from another. Anything that could identify a
person, or long free text that could carry instructions, is replaced by its shape."""

import re

from boardroom.modules.intake.parsing import Table

_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", re.I)
_URL = re.compile(r"https?://\S+|www\.\S+", re.I)
_PHONE = re.compile(r"(?:\+\d[\d\s().-]{7,}\d)|(?:\b0\d{3,4}[\s-]?\d{3}[\s-]?\d{3,4}\b)")
MAX_TEXT = 40
SAMPLE_ROWS = 15


def redact_cell(value: str) -> str:
    if not value:
        return value
    value = _EMAIL.sub("<email>", value)
    value = _URL.sub("<url>", value)
    value = _PHONE.sub("<phone>", value)
    if len(value) > MAX_TEXT:
        return f"<text, {len(value)} chars>"
    return value


def sample_indexes(n: int, k: int = SAMPLE_ROWS) -> list[int]:
    """First, middle and last rows, so a sample shows how a file starts and ends."""
    if n <= k:
        return list(range(n))
    third = k // 3
    mid = n // 2 - third // 2
    picks = list(range(third)) + list(range(mid, mid + third)) + list(range(n - (k - 2 * third), n))
    return sorted(set(picks))


def sample_rows(table: Table) -> list[list[str]]:
    return [[redact_cell(c) for c in table.rows[i]] for i in sample_indexes(len(table.rows))]


def redact_preamble(lines: list[str]) -> list[str]:
    return [
        redact_cell(line) if len(line) <= 120 else f"<text, {len(line)} chars>" for line in lines
    ]
