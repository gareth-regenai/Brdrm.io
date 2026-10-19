# Board pack sections: what each one holds

What each board pack section and sub-tab contains, and where every piece comes from. Written from two investor dashboards a company filled in by hand, so the content is what a real board wants to see. This document describes structure only: no names, figures or copy from those dashboards are used in the product.

Status: draft for review. Nothing here is built until the decisions at the end are made and the FRD carries the requirements.

## How to read the source column

| Source | Meaning | Principle |
|---|---|---|
| **Calculated** | Code computes it from a file or a connected tool, with a fixed formula in the metric registry | 2 |
| **Entered** | A person types it. Shows "Entered by [name], [date]" | FR-4.8 |
| **Modelled** | Code computes it from assumptions a person entered. Always labelled "Modelled, not a forecast" | 2 |
| **Drafted** | Claude writes text from the data and the company's own documents. Passes the number check, labelled "Drafted by Claude", editable | 3 |
| **Rule** | Code raises it when a figure crosses a threshold | 2 |

Claude never produces a figure, a score or a rating. Where a section needs one and no file holds it, a person enters it.

## Patterns every section shares

- A header: company, section name, the period covered and "data true as of".
- A row of up to four headline tiles, leading with the number.
- One plain-English callout for the position today (Drafted, editable).
- Lists of cards with a status or severity pill (Critical, High, Medium, Low; or Done, In progress, Planned, Live).
- Modelled figures sit in their own labelled block, never mixed with actuals.
- Every figure opens the click view: exact value, source, what it moves, risk level (FR-5.4).

## 1. Overview

| Block | Content | Source |
|---|---|---|
| Section cards | One card per section with two headline chips (for example cash and runway) | Calculated |
| Progress to plan | Each target with actual, target and a bar | Calculated against Entered targets |
| Headline tiles | Revenue, cash, runway, net burn | Calculated |
| Founder update | Short summary across sections | Drafted |

Built today, except the chips are missing from most cards.

## 2. Roadmap

Sub-tabs: Overview, Product, Sales, Cash, Team.

| Sub-tab | Content | Source |
|---|---|---|
| Overview | Next milestone target with three or four target tiles; progress to each target; four end-of-period goals (revenue, customers, team, product); a timeline of every track by month with status per item | Targets Entered, progress Calculated where a measure exists, otherwise Entered status |
| Product | Then and now tiles (for example services built), the one build that matters most and why, milestone cards (date, title, description, tag) | Entered, or from a Jira or monday.com export (phase 2) |
| Sales | Target tiles (customers, recurring revenue, average deal, conversion); how revenue builds as a worked formula; growth chart with customers as columns and revenue as lines per scenario; milestone and channel cards | Inputs Entered, results Modelled |
| Cash | Booked revenue, cost reduction, date revenue covers burn; the action needed now; cash milestones; growth model tables (per customer and month by month, with cost, revenue and margin) | Actuals Calculated, plan Modelled |
| Team | Current team size, key roles, next hire; hiring milestones; hiring principle | Entered (headcount Calculated in phase 2) |

## 3. Product

Sub-tabs: What we built, How it works, Outcomes.

| Sub-tab | Content | Source |
|---|---|---|
| What we built | Count tiles (then and now); capability cards grouped by theme | Entered, or Drafted from the company's documents |
| How it works | Stages from start to result, each with short steps | Entered or Drafted |
| Outcomes | Outcome tiles (for example reply rate, price per unit); customer proof cards with two figures each; what a customer gets | Figures Calculated where a file holds them, else Entered |

## 4. Cashflow

Sub-tabs: Overview, Spend, Income, Revenue, Balance, Stack optimisation. Needs bank transactions as a new source (decision 2).

| Sub-tab | Content | Source |
|---|---|---|
| Overview | Money in against money out by month; headline tiles | Calculated |
| Spend | Category wheel with drill-down into a category; month filter (all or one month); full list by category | Calculated. Claude picks each transaction's category from a closed list; code adds up |
| Income | Income split into revenue, investment and loans; corrections netted out | Calculated. A line that could be revenue or a loan is one question to a person |
| Revenue | Booked, collected and qualified pipeline tiles; one card per customer with the invoices behind it | Calculated from transactions and the CRM |
| Balance | Balance over time; peak, current, forward burn, target date | Calculated, target Entered |
| Stack optimisation | Recurring suppliers found in transactions: already stopped, overlapping, rising in cost, low use; potential monthly saving | Calculated (last charge, trend, total). Claude groups overlaps from a closed list of tool types; a person marks each one kept or cut |

## 5. Pipeline

Sub-tabs: Deal stages, Scenario modelling.

| Sub-tab | Content | Source |
|---|---|---|
| Deal stages | Qualified pipeline total; one card per stage with count, value and named deals; closed won; early prospects listed separately and not counted until they pass a first meeting | Calculated from the CRM export or connector |
| Scenario modelling | Low, base and high conversion; per-deal table of volume, results and revenue at each rate; totals; segments kept apart (for example small business and enterprise) | Modelled. Rates and prices Entered; a default volume is used and starred where the real one is unknown |

## 6. Market validation

Sub-tabs: Validation, Recognition, Cost savings.

| Sub-tab | Content | Source |
|---|---|---|
| Validation | Conversion tiles (for example event meetings, partner sign-ups); endorsement cards: who, their role, what happened, why it matters | Tiles Calculated or Entered; stories Entered |
| Recognition | Speaking slots, invitations, live customers; one card each | Entered |
| Cost savings | Spend on suppliers that have stopped, monthly saving, where the money goes next; one line per supplier | Calculated from transactions, with suppliers tagged by a person |

## 7. Risk register

Sub-tabs: Without capital, Market, Execution, Team.

| Block | Content | Source |
|---|---|---|
| Tiles | Runway without new money, amount invoiceable now, burn reduction, funding trigger | Calculated |
| Position | What happens without the capital, and what the capital buys | Drafted, editable |
| Risks | Title, description, level, mitigation, owner, status. Ranked by level | Entered, or Rule (for example runway under six months raises a capital risk), or proposed by Claude. A person decides every level |

## 8. CEO development

Sub-tabs: Gap map, 30-day plan, Operating rhythm.

| Sub-tab | Content | Source |
|---|---|---|
| Gap map | Count of critical gaps, high priorities and strengths; a score from 0 to 100 per area with level; radar chart; detail per area | Areas proposed by Claude from an assessment conversation; every score Entered by the CEO |
| 30-day plan | One task a day in weeks, typed Reflect, Execute or Team; tick to complete; progress | Drafted, ticked by the CEO |
| Operating rhythm | Daily, weekly and fortnightly blocks with their purpose | Drafted, editable |

## New sources this needs

1. **Bank transactions** (CSV export or an accounting connector): Cashflow, Market validation cost savings, Revenue collected.
2. **Scenario assumptions** (rates, prices, volumes): Roadmap sales and cash, Pipeline scenarios.
3. **Milestones and timeline items**: Roadmap. Entered now, from Jira or monday.com in phase 2.
4. **Hand-written content blocks**: Product, Market validation stories, Risk register, CEO development.

## Decisions for the CEO

1. Are Risk register and CEO development in scope, and do investors see CEO development?
2. Add bank transactions as a source, with Claude choosing categories from a closed list?
3. Payroll in bank data: show one total only, never a line per person, in line with the pay-like data rule. Confirm.
4. Scenario modelling: assumptions entered by the company and always labelled modelled. Confirm.
5. Should the sections in this document be phase 1 (MVP) or phase 2 behind a feature flag?
