"""The department guidance and the closed field list skill 1 maps columns onto.

Guidance, never a gate (BR-4.2): a file with none of these columns is still accepted.
"""

from dataclasses import dataclass
from enum import StrEnum


class FieldType(StrEnum):
    MONTH = "month"  # a reporting period, stored as YYYY-MM
    DATE = "date"  # stored as YYYY-MM-DD
    MONEY = "money"  # stored as a decimal string, in the file's currency
    NUMBER = "number"
    PERCENT = "percent"  # stored as a fraction: 60% is 0.6
    TEXT = "text"


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    type: FieldType
    description: str


FIELDS: dict[str, tuple[Field, ...]] = {
    "finance": (
        Field("period", "period", FieldType.MONTH, "The month a row reports on."),
        Field("revenue", "revenue", FieldType.MONEY, "Income from sales for the period."),
        Field("cost_of_sales", "cost of sales", FieldType.MONEY, "Direct costs of what was sold."),
        Field(
            "operating_expenses",
            "operating expenses",
            FieldType.MONEY,
            "Overheads such as rent, software and salaries in total.",
        ),
        Field("cash_balance", "cash balance", FieldType.MONEY, "Cash at bank at period end."),
        Field(
            "payroll_total", "payroll total", FieldType.MONEY, "Total payroll cost, not per person."
        ),
        Field("capex", "capital expenditure", FieldType.MONEY, "Spend on long-term assets."),
        Field("debt", "debt", FieldType.MONEY, "Loans and borrowings outstanding."),
        Field("arr", "annual recurring revenue", FieldType.MONEY, "ARR at period end."),
        Field(
            "deferred_revenue", "deferred revenue", FieldType.MONEY, "Billed but not yet earned."
        ),
        Field("currency", "currency", FieldType.TEXT, "ISO currency code of the amounts."),
    ),
    "sales": (
        Field("deal_id", "deal id", FieldType.TEXT, "The CRM's id for the deal."),
        Field("account", "account", FieldType.TEXT, "The customer or prospect company."),
        Field("stage", "stage", FieldType.TEXT, "Pipeline stage."),
        Field("amount", "deal amount", FieldType.MONEY, "Deal value."),
        Field("status", "status", FieldType.TEXT, "open, won or lost."),
        Field("created_date", "created date", FieldType.DATE, "When the deal was created."),
        Field("expected_close_date", "expected close date", FieldType.DATE, "Forecast close."),
        Field("closed_date", "closed date", FieldType.DATE, "When it was won or lost."),
        Field("probability", "probability", FieldType.PERCENT, "Chance of winning."),
        Field("source", "source", FieldType.TEXT, "Where the deal came from."),
        Field("owner", "owner", FieldType.TEXT, "Salesperson responsible."),
        Field("last_activity_date", "last activity date", FieldType.DATE, "Latest activity."),
        Field("currency", "currency", FieldType.TEXT, "ISO currency code of the amount."),
    ),
    "delivery": (
        Field("item_id", "item id", FieldType.TEXT, "The tracker's id for the item."),
        Field("title", "title", FieldType.TEXT, "What the item is."),
        Field("status", "status", FieldType.TEXT, "Item status."),
        Field("due_date", "due date", FieldType.DATE, "When it is due."),
        Field("completed_date", "completed date", FieldType.DATE, "When it was completed."),
        Field(
            "planned_period", "planned period", FieldType.MONTH, "The period it was planned for."
        ),
    ),
    "people": (
        Field("department", "department", FieldType.TEXT, "Team or department."),
        Field("role_title", "role title", FieldType.TEXT, "Job title."),
        Field("status", "status", FieldType.TEXT, "active, leaver or open role."),
        Field("start_date", "start date", FieldType.DATE, "Start date."),
        Field("end_date", "end date", FieldType.DATE, "Leaving date."),
        Field("requisition_opened_date", "requisition opened", FieldType.DATE, "Role opened."),
        Field("location", "location", FieldType.TEXT, "Office or country."),
    ),
    "plan": (
        Field("metric", "metric", FieldType.TEXT, "Which measure the target is for."),
        Field("period", "period", FieldType.MONTH, "The month the target applies to."),
        Field("target_value", "target", FieldType.MONEY, "The target value."),
    ),
}

KINDS = tuple(FIELDS)
PHASE_2_KINDS = frozenset({"delivery", "people"})

# A low-confidence column mapped to one of these fields stops a phase 1 figure,
# so it earns a question (FR-4.6). Anything else falls back to the AI's best guess.
BLOCKING_FIELDS: dict[str, frozenset[str]] = {
    "finance": frozenset(
        {"period", "revenue", "cost_of_sales", "operating_expenses", "cash_balance"}
    ),
    "sales": frozenset({"amount", "status", "stage", "expected_close_date", "closed_date"}),
    "plan": frozenset({"metric", "period", "target_value"}),
    "delivery": frozenset(),
    "people": frozenset(),
}

QUESTION_THRESHOLD = 0.8
IGNORE_BELOW = 0.5

DATE_FORMATS = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%d %b %Y",
    "%d %B %Y",
    "%d-%b-%y",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%d/%m/%Y %H:%M",
    "%m/%d/%Y %H:%M",
    "%b %Y",
    "%B %Y",
    "%b-%y",
    "%Y-%m",
    "%m/%Y",
)

TRANSFORMS = ("rename", "parse_date", "scale", "flip_sign", "split", "combine", "map_values")


def field(kind: str, key: str) -> Field | None:
    for f in FIELDS.get(kind, ()):
        if f.key == key:
            return f
    return None


def guidance_text() -> str:
    """The department guidance as skill 1 sees it."""
    lines = []
    for kind, fields in FIELDS.items():
        lines.append(f"{kind}:")
        for f in fields:
            lines.append(f"  - {f.key} ({f.type.value}): {f.description}")
    return "\n".join(lines)
