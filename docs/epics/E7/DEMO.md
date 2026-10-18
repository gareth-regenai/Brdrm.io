# E7 Investor portfolio overview: demo

**Done when:** an investor with three companies sees them ranked by risk.

## Run it

As in `docs/epics/E5/DEMO.md`. No new migration.

## What to show (about 3 minutes)

1. Make three companies and share one update in each. To get known runways, upload `quickbooks_monthly.csv` with the bank balance changed: ending at £279,200 gives 4.0 months, £698,000 gives 10.0 months, and the file as it is gives 17.1 months. `books()` in `backend/tests/test_overview.py` writes these files.
2. Invite the same investor to all three and sign in as them. They land on **Companies you back**: Alder Labs (High risk, runway 4.0 months), Kestrel Field (Medium), Northpath (Low).
3. Each card has the same eight measures in the company's own currency and precision. Revenue against plan and pipeline coverage say "Not shared yet" until a company shares them; delivery and headcount say "Coming in phase 2".
4. Click a card: the company's own section opens. **Figures** comes first: every measure the company has shared, not only the overview's eight, at its latest shared value with last period beside it. Choose one for its exact value, formula and the rows used. Below it, every update with its commentary and comments.
5. As one CEO, make the company's own runway line stricter in the click view. Its own tile turns High; the investor's overview does not change, because it uses the common lines.
6. Sign in as a CEO and go to `/portfolio`: refused.

## Requirements covered

| FR | Status | Proved by |
|---|---|---|
| FR-7.1 | Done | An investor in three companies sees three cards, and none of a fourth company |
| FR-7.2 | Done | Two companies with a 10.0-month runway both get Medium. Figures use each company's currency and precision. A company's own lines do not change the overview (FR-5.7) |
| FR-7.3 | Done, proposed rule | Most High first, then most Medium, then shortest runway: High, Medium, Low at 15.0 months, Low at 17.1 months |
| FR-7.4 | Done | A card opens the company's section: its shared figures as tiles with the click view (on the common lines, as on the overview), then its updates and comments |
| FR-7.5 | Done | With the flags off, delivery and headcount say "Coming in phase 2"; with the people flag on, headcount shows like any other measure |
| FR-7.6 | Done | "Today" when shared today; 41 days ago reads "41 days" and High |
| FR-7.7 | Done | The Owner and CEO are refused |
| FR-7.8 | Done | Cards only: no field anywhere sums money across companies |
| FR-3.3 | Done | A company's unshared update shows nothing on the overview. A figure changed by hand in a shared update shows as changed, on the common lines |
