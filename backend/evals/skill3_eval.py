"""Scheduled eval for skill 3 against the real model (FR-13.2). Never run in CI.

Each labelled set of figures is drafted in both voices. Two rates are measured:
- checked: the share of sections that end with text that passes the number check, after
  the one redraft. A section that fails twice goes to a person, which is safe but costs
  the company time, so a drop here is a regression.
- voice: the share of third-person drafts with no "we", "our" or "us" (FR-6.4).

Run from backend/: ANTHROPIC_API_KEY=... python -m evals.skill3_eval [--threshold 0.9]
"""

import argparse
import json
import re
import sys
from decimal import Decimal
from pathlib import Path

from boardroom.modules.insights import service as insights

SETS = Path(__file__).resolve().parent / "commentary"
FIRST_PERSON = re.compile(r"\b(we|our|us)\b", re.I)


def _figures(raw: list[dict]) -> list[insights.FigureFact]:
    out = []
    for f in raw:
        out.append(
            insights.FigureFact(
                key=f["key"],
                label=f["label"],
                unit=f["unit"],
                period=f["period"],
                value=Decimal(f["value"]),
                shown_as=f["shown_as"],
                previous_period=f.get("previous_period"),
                previous_value=Decimal(f["previous_value"]) if "previous_value" in f else None,
                previous_shown_as=f.get("previous_shown_as"),
                risk=f.get("risk"),
                inputs={k: Decimal(v) for k, v in f.get("inputs", {}).items()},
                share_of_target=Decimal(f["share_of_target"]) if "share_of_target" in f else None,
            )
        )
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, default=0.9)
    args = parser.parse_args()
    sections = checked = third = in_voice = 0
    for path in sorted(SETS.glob("*.json")):
        data = json.loads(path.read_text())
        for voice in ("we", "third_person"):
            draft = insights.draft(
                data["company"],
                voice,
                data["currency"],
                data["department"],
                data["data_as_of"],
                _figures(data["figures"]),
            )
            if draft.model is None:
                print("Claude is not available: set ANTHROPIC_API_KEY.")
                return 2
            texts = [s.text for s in draft.sections if s.text]
            sections += len(draft.sections)
            checked += len(texts)
            failed = [s.check for s in draft.sections if s.text is None]
            print(
                f"{path.stem} ({voice}): {len(texts)}/{len(draft.sections)} passed, "
                f"{draft.attempts} attempt(s){'; failed: ' + json.dumps(failed) if failed else ''}"
            )
            if voice == "third_person":
                third += 1
                prose = " ".join(s.text for s in draft.sections if s.text and s.kind != "questions")
                in_voice += 0 if FIRST_PERSON.search(prose) else 1
    checked_rate, voice_rate = checked / sections, in_voice / third
    print(f"checked {checked_rate:.0%}, voice {voice_rate:.0%}, threshold {args.threshold:.0%}")
    return 0 if min(checked_rate, voice_rate) >= args.threshold else 1


if __name__ == "__main__":
    sys.exit(main())
