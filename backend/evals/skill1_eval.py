"""Scheduled eval for skill 1 against the real model (FR-13.2). Never run in CI.

For each labelled file, the model's mapping is compared with the label. A file counts as
understood with no correction when every field the label maps is mapped to the same
column or line, and nothing the label ignores is mapped to a figure field.

Labels live in tests/fixtures/recorded/*.json (the "response" is the label). Add real,
anonymised beta files here as they arrive: the agreed rate is measured on those.

Run from backend/: ANTHROPIC_API_KEY=... python -m evals.skill1_eval [--threshold 0.9]
"""

import argparse
import json
import sys
from pathlib import Path

from boardroom.modules.intake import skill1
from boardroom.modules.intake.parsing import parse_sandboxed
from boardroom.modules.intake.profiler import profile
from boardroom.modules.intake.sensitive import drop_sensitive

ROOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
FILES = {
    "xero_pnl": "xero_pnl.csv",
    "quickbooks_monthly": "quickbooks_monthly.csv",
    "finance_ambiguous": "finance_ambiguous.csv",
    "hubspot_deals": "hubspot_deals.csv",
    "pipedrive_deals": "pipedrive_deals.xlsx",
    "team_with_pay": "team_with_pay.csv",
    "injection": "injection.csv",
}


def _pairs(interp: dict) -> set[tuple[str, str]]:
    cols = {(c["column"], c["field"]) for c in interp["columns"] if c["field"] != "ignore"}
    labels = {(r["label"], r["field"]) for r in interp["row_labels"] if r["field"] != "ignore"}
    return cols | labels


def score(label: dict, got: dict) -> tuple[bool, list[str]]:
    problems = []
    if got["file_kind"] != label["file_kind"]:
        problems.append(f"kind {got['file_kind']} not {label['file_kind']}")
    want, have = _pairs(label), _pairs(got)
    problems += [f"missed {c} -> {f}" for c, f in sorted(want - have)]
    problems += [f"extra {c} -> {f}" for c, f in sorted(have - want)]
    return not problems, problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, default=0.9)
    args = parser.parse_args()
    client = skill1.get_client()
    if client is None:
        print("Set ANTHROPIC_API_KEY to run the eval.")
        return 2
    passed = 0
    for name, filename in FILES.items():
        label = json.loads((ROOT / "recorded" / f"{name}.json").read_text())["response"]
        table, _ = drop_sensitive(parse_sandboxed((ROOT / "files" / filename).read_bytes()))
        try:
            got = skill1.validate(
                client.interpret(skill1.build_payload(table, profile(table), filename)), table
            ).to_json()
        except (skill1.SkillOutputError, skill1.SkillUnavailable) as exc:
            print(f"FAIL {name}: {exc}")
            continue
        ok, problems = score(label, got)
        passed += ok
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else ": " + "; ".join(problems)))
    rate = passed / len(FILES)
    print(f"Understood with no correction: {passed} of {len(FILES)} ({rate:.0%})")
    return 0 if rate >= args.threshold else 1


if __name__ == "__main__":
    sys.exit(main())
