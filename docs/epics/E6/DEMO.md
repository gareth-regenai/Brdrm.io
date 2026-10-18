# E6 Commentary and number check: demo

**Done when:** commentary passes the check, or a person writes the section.

## Run it

As in `docs/epics/E5/DEMO.md`, then `alembic upgrade head` again for the commentary table. With `SKILL1_REPLAY_DIR` set, a recorded draft is used for `xero_pnl.csv` (matched on its exact figures), so the demo needs no API key. Any other file shows the "a person writes it" path. With `ANTHROPIC_API_KEY` set instead, Claude drafts every update.

## What to show (about 5 minutes)

1. Add `xero_pnl.csv`. The upload passes through **Describing** while the commentary is drafted and checked, then **Ready**.
2. Under the dated line: "Revenue grew 3.5% to £72.9k in September." and a note, each labelled **Drafted by Claude**. Every figure in them is a real figure rounded normally: £2.5k is the £2,460 change from August, £122.8k is operating expenses of £122,820.
3. **Likely board questions, for you only**: they help the company prepare and are never shown to investors, in the app, the PDF or the database.
4. **Edit** the note and write "Cash is now £2.0m." It saves, labelled "Drafted by Claude, edited by Sam Hart", with a warning: "These figures match nothing calculated: £2.0m." A person may write what they like; the company is told.
5. Approve. As an investor, open **Source** on revenue: "Check: Passed. The commentary writes it as £72.9k."
6. Add `quickbooks_monthly.csv` (no recording, or switch the AI off): each section says why it waits, with **Write it**. Write one; it reads "Written by Sam Hart". Leave one empty and investors never see it.
7. In **Settings**, set the commentary voice to "The company" and **Redraft with Claude**: the next draft speaks in the third person. What a person wrote is kept.

## Requirements covered

| FR | Status | Proved by |
|---|---|---|
| FR-5.5 | Done | £1.4m passes for £1,378,000, £1.5m and £1.37m fail, "12 December", Q3, years and counts are ignored, the wrong currency fails. A failed draft is redrafted once with the figures that failed listed; a section that fails twice waits for a person and investors never see it |
| FR-10.3 | Done | Skill 3 is sent calculated figures only: no rows, file names, line-item names or people. Seven malformed answers are refused by the schema checks, and an answer outside the schema counts as a failed draft |
| FR-6.4 | Done | Switching the voice changes the next draft's instructions to the third person by company name. Every section shows who did what: "Drafted by Claude", "Drafted by Claude, edited by [name]", "Written by [name]". "Approved by [name]" is from E5 |
| FR-3.1 | Done | Describing is now a real step: the upload waits there while the commentary is drafted and checked |
| FR-13.2 | Done | Tests use recorded answers. `evals/skill3_eval.py` runs the real model weekly on three labelled sets in both voices and fails below 90% checked or 90% in the right voice |

## Not yet

- The commentary has not been run against the real model in this environment (no key). Run `python -m evals.skill3_eval` with `ANTHROPIC_API_KEY` set to measure it.
