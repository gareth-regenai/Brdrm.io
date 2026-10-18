"""Pay-like columns are dropped before storage and before any AI call (FR-4.4, FR-11.3).

Detection is by header and by content. The rest of the file is kept. Only the dropped
column's position and a reason are recorded, never its header text or values.
"""

import re
from dataclasses import dataclass

from boardroom.modules.intake.parsing import Table

_HEADER = re.compile(
    # Not "bank" alone, so "Cash at bank" survives; not "gross" alone, so "Gross profit" does.
    r"salar|wage|\bpay\b|payroll\s*(?:id|number|no)|bonus|commission|gross\s*pay|\bnet\s+pay|"
    r"bank\s*(?:account|details|name|no\b|number)|sort\s*code|account\s*(?:no|num)|"
    r"\biban\b|\bswift\b|\bbic\b|"
    r"national\s*insurance|\bni\s*(?:no|num|number)?\b|\bnino\b|"
    r"date\s*of\s*birth|\bdob\b|\bbirth|\bbirthday|"
    r"personal\s*e-?mail|home\s*e-?mail|private\s*e-?mail|home\s*address|\btax\s*code|\butr\b",
    re.IGNORECASE,
)
_NI = re.compile(r"^[A-CEGHJ-PR-TW-Z][A-CEGHJ-NPR-TW-Z]\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-D]$", re.I)
_SORT_CODE = re.compile(r"^\d{2}-\d{2}-\d{2}$")
_IBAN = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9 ]{11,30}$")
_EMAIL = re.compile(r"^[^@\s]+@([^@\s]+\.[a-z]{2,})$", re.I)
_FREE_MAIL = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "hotmail.com",
        "hotmail.co.uk",
        "outlook.com",
        "live.com",
        "live.co.uk",
        "yahoo.com",
        "yahoo.co.uk",
        "icloud.com",
        "me.com",
        "aol.com",
        "proton.me",
        "protonmail.com",
        "btinternet.com",
        "sky.com",
        "gmx.com",
    }
)


@dataclass(frozen=True)
class Dropped:
    position: int
    reason: str


def _content_reason(values: list[str]) -> str | None:
    filled = [v for v in values if v][:500]
    if not filled:
        return None
    share = lambda pattern: sum(1 for v in filled if pattern.match(v)) / len(filled)  # noqa: E731
    if share(_NI) >= 0.5:
        return "national insurance numbers"
    if share(_SORT_CODE) >= 0.5:
        return "bank sort codes"
    if share(_IBAN) >= 0.5:
        return "bank account numbers"
    emails = [m.group(1).lower() for v in filled if (m := _EMAIL.match(v))]
    mostly_emails = bool(emails) and len(emails) / len(filled) >= 0.5
    if mostly_emails and sum(1 for d in emails if d in _FREE_MAIL) / len(emails) >= 0.5:
        return "personal email addresses"
    return None


def find_sensitive(table: Table) -> list[Dropped]:
    dropped = []
    for i, header in enumerate(table.headers):
        if _HEADER.search(header):
            dropped.append(Dropped(i, "pay-like column name"))
            continue
        reason = _content_reason([r[i] for r in table.rows])
        if reason:
            dropped.append(Dropped(i, reason))
    return dropped


def drop_sensitive(table: Table) -> tuple[Table, list[Dropped]]:
    dropped = find_sensitive(table)
    keep = [i for i in range(len(table.headers)) if i not in {d.position for d in dropped}]
    clean = Table(
        headers=[table.headers[i] for i in keep],
        rows=[[r[i] for i in keep] for r in table.rows],
        preamble=table.preamble,
        sheet=table.sheet,
        source_format=table.source_format,
    )
    return clean, dropped
