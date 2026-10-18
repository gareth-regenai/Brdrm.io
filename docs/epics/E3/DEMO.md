# E3 Figures engine: demo

**Done when:** every phase 1 metric computes from real files with lineage, and golden datasets match.

## What to show (about 6 minutes)

1. Start as in `docs/epics/E2/DEMO.md` and add `quickbooks_monthly.csv`, `xero_pnl.csv` and `hubspot_deals.csv` from `backend/tests/fixtures/files`. Each upload now waits at Calculating until its figures exist, then reads Ready.
2. **Figures** shows a tile per measure: the value at the company's display precision, the month, last month's value, a risk level where one applies, and a minimised source line.
3. Choose **Runway**. The click view shows the exact value (17.127...), the formula and its version, the inputs, the warning lines, and the three source rows from the file with how they were selected.
4. Enter a revenue target for September 2026 of 80,000 by hand. **Revenue against plan** changes from "No plan set" to -£11.5k at medium risk, with "Entered by" in its source line.
5. In the click view, choose **Show more detail** on Revenue: £68.5k becomes £68,500. Change the runway warning lines to 24 and 36: the tile turns high risk for this company only.
6. Show `backend/tests/test_metrics.py`: the golden datasets, with the working by hand in the comments.

## Run it locally

As in `docs/epics/E2/DEMO.md`, then `alembic upgrade head` again for the metrics tables.

## Requirements covered

| FR | Status | Proved by |
|---|---|---|
| FR-1.1 | Done | Formulas never import or read an AI response; skill 2 answers with extra numbers are rejected; figure values equal code's arithmetic on the selected rows |
| FR-1.2 | Done | Every figure in a three-file upload resolves to dataset rows with versions, or a named person and date; the database refuses an "ok" figure with no lineage |
| FR-5.1 | Done | Each figure stores its formula version from the registry |
| FR-5.2 | Done, filter set open | Selections outside the closed set are rejected (7 cases) and the standard selection is used. Skill 2 sees field counts and category values only, never rows or names |
| FR-5.3 | Done | The cash-movement burn is flagged on the tile, in the click view and in the database |
| FR-5.4 | Done | The click view shows exact value, source rows or person, what it moves and risk level, for file, hand-entered and custom figures. The number check itself is E6 |
| FR-5.6 | Done | Precision fixtures for every band, half-up rounding, and a company moving a measure one band |
| FR-5.7 | Done, defaults open | Changing a company's warning lines changes its own tiles and leaves the common level, used by the investor overview, alone |
| FR-13.3 | Done | Golden finance and sales datasets match to the last digit, including rounding, a cash-generative company, a target met, blank cells and another currency |
| FR-4.11 | Done | "No plan set" with no target; a typed-in target fills the plan tile |

202 backend tests pass.

## Not yet

- Investors do not see figures yet: they arrive through shared updates (E5) and the overview (E7).
- Skill 2 has not been run against the real model. With no API key, or in the local demo, the standard selection is used and the click view says so.
