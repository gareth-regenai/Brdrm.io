"""Drafting commentary that passes the number check (FR-5.5, FR-10.3, FR-6.4).

Claude drafts; code checks every figure in every section. A failure gets one redraft with
the differences listed. A section that fails twice is left for a person to write. Nothing
here stores anything: the updates module keeps the sections.
"""

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from boardroom.logs import get_logger
from boardroom.modules.insights import skill3
from boardroom.modules.insights.check import Candidate, check

log = get_logger(__name__)
SKILL_VERSION = "skill3/2026-10-18.1"

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
CHECKED_UNITS = {"money", "percent", "ratio", "months"}


@dataclass(frozen=True)
class FigureFact:
    """One calculated figure, as code worked it out. Nothing from rows or about people."""

    key: str
    label: str
    unit: str
    period: str
    value: Decimal
    shown_as: str
    previous_period: str | None = None
    previous_value: Decimal | None = None
    previous_shown_as: str | None = None
    risk: str | None = None
    # Money amounts the figure was calculated from, such as cash and burn for runway.
    inputs: dict[str, Decimal] = field(default_factory=dict)
    share_of_target: Decimal | None = None


@dataclass(frozen=True)
class Section:
    kind: str  # headline, note, questions
    department: str | None
    text: str | None  # None: left for a person to write
    check: dict[str, Any]
    reason: str | None = None


@dataclass(frozen=True)
class Draft:
    sections: list[Section]
    model: str | None
    attempts: int


def month(period: str) -> str:
    year, m = period.split("-")
    return f"{MONTHS[int(m) - 1]} {year}"


def _words(key: str) -> str:
    return key.replace("_", " ")


def candidates(figures: list[FigureFact]) -> list[Candidate]:
    out = []
    for f in figures:
        if f.unit not in CHECKED_UNITS:
            continue
        out.append(Candidate(f.unit, f.value, f"{f.label}, {month(f.period)}"))
        if f.previous_value is not None and f.previous_period:
            out.append(
                Candidate(f.unit, f.previous_value, f"{f.label}, {month(f.previous_period)}")
            )
            out.append(
                Candidate(f.unit, f.value - f.previous_value, f"Change in {f.label.lower()}")
            )
        for name, amount in f.inputs.items():
            out.append(Candidate("money", amount, f"{f.label}: {_words(name)}"))
        if f.share_of_target is not None:
            out.append(Candidate("percent", f.share_of_target, f"{f.label} as a share of target"))
    return out


def _percent(fraction: Decimal) -> str:
    return f"{(fraction * 100).quantize(Decimal('0.1'), ROUND_HALF_UP)}%"


def facts_json(
    company: str, currency: str, department: str, data_as_of: str, figures: list[FigureFact]
) -> dict[str, Any]:
    out = []
    for f in figures:
        item: dict[str, Any] = {
            "measure": f.label,
            "period": month(f.period),
            "shown_as": f.shown_as,
            "exact": str(f.value),
            "risk_level": f.risk,
        }
        if f.previous_value is not None and f.previous_period:
            item["last_period"] = {
                "period": month(f.previous_period),
                "shown_as": f.previous_shown_as,
                "exact": str(f.previous_value),
            }
            item["change_from_last_period"] = str(f.value - f.previous_value)
        if f.inputs:
            item["calculated_from"] = {_words(k): str(v) for k, v in f.inputs.items()}
        if f.share_of_target is not None:
            item["share_of_target"] = _percent(f.share_of_target)
        out.append(item)
    return {
        "company": company,
        "currency": currency,
        "data_true_as_of": data_as_of,
        "departments": {department: skill3.DEPARTMENT_WORDS.get(department, department)},
        "figures": out,
    }


def _sections(c: skill3.Commentary) -> dict[tuple[str, str | None], str]:
    out: dict[tuple[str, str | None], str] = {("headline", None): c.headline}
    for department, text in c.notes.items():
        out[("note", department)] = text
    if c.questions:
        out[("questions", None)] = "\n".join(c.questions)
    return out


def _feedback(failures: list[tuple[str, list[str]]]) -> str:
    lines = [
        "The check found figures that are not a real figure rounded normally. "
        "Rewrite only what is needed, using the shown_as values:"
    ]
    for where, figures in failures:
        lines.append(f"- {where}: {', '.join(figures)}")
    return "\n".join(lines)


def _where(key: tuple[str, str | None]) -> str:
    kind, department = key
    return f"the note on {department}" if kind == "note" else f"the {kind}"


def draft(
    company: str,
    voice: str,
    currency: str,
    department: str,
    data_as_of: str,
    figures: list[FigureFact],
) -> Draft:
    """Every section either passes the check or comes back with text None for a person."""
    from boardroom.modules.intake.skill1 import SkillOutputError, SkillUnavailable

    expected: list[tuple[str, str | None]] = [("headline", None), ("note", department)]
    client = skill3.get_client([department])
    if client is None or not figures:
        reason = (
            "Claude is switched off." if client is None else "There are no figures to describe."
        )
        return Draft([Section(k, d, None, {}, reason) for k, d in expected], None, 0)

    facts = facts_json(company, currency, department, data_as_of, figures)
    cands = candidates(figures)
    best: dict[tuple[str, str | None], Section] = {}
    earlier: list[tuple[Any, str]] = []
    attempts = 0
    for _ in range(2):  # one draft and, if needed, one redraft (FR-5.5)
        attempts += 1
        try:
            raw = client.interpret(skill3.build_payload(facts, voice, company, earlier))
            commentary = skill3.validate(raw, [department])
        except (SkillUnavailable, SkillOutputError, skill3.CommentaryOutputError) as exc:
            log.info("commentary_not_drafted", reason=type(exc).__name__, attempt=attempts)
            if isinstance(exc, SkillUnavailable):
                break
            continue
        failures = []
        for key, text in _sections(commentary).items():
            result = check(text, cands, currency)
            current = best.get(key)
            if current is None or (not current.check.get("passed") and result.passed):
                best[key] = Section(key[0], key[1], text, result.to_json())
            if not result.passed:
                failures.append((_where(key), [f.text for f in result.failures]))
        if not failures and all(k in best for k in expected):
            break
        earlier.append((raw, _feedback(failures)))

    sections = []
    keys = expected + [k for k in best if k not in expected]
    for key in keys:
        found = best.get(key)
        if found is not None and found.check.get("passed"):
            sections.append(found)
        elif found is not None:
            sections.append(
                Section(
                    key[0],
                    key[1],
                    None,
                    found.check,
                    "Claude's draft did not pass the number check twice.",
                )
            )
        else:
            sections.append(Section(key[0], key[1], None, {}, "Claude could not draft this."))
    return Draft(sections, getattr(client, "model", None), attempts)
