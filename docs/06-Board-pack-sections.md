# Board pack sections specification

What each board pack section contains, how it is laid out and where every block's content comes from. 19 October 2026.

- **Evidence:** docs/07-Board-pack-reference-analysis.md (the block-by-block inventory of two reference dashboards, with counts).
- **Requirements:** BRD and FRD chapter 15. Build to the FRD; this document is the detail it points to.
- **Status:** navigation, scope and sources decided; the open decisions in section 8 block parts of it. Nothing is built until FRD chapter 15 is agreed.

## 1. Navigation (decided)

- **Section bar.** One bar across the top, always visible, the same for company users and investors, in this order: Overview, Roadmap, Product, Cashflow, Pipeline, Momentum, Risk register, CEO development.
- **Sub-tabs.** Each section has its own sub-tab bar under a section header (block type T1). The sub-tabs are listed in section 4.
- **Working pages.** Dashboard, Files, Your tools, Team and Settings sit in a side menu for company users only. Investors never see them.
- **Investors.** The company picker stays in the header. Investors see only content from approved updates (FR-6.3).
- **Updates.** Where the dated updates and their comment threads live is open (section 8, decision 5).
- **Phase 2.** Sections or sub-tabs whose data is phase 2 show "Coming in phase 2" behind their feature flag (FR-1.3).

## 2. Sources

Every block is built from one or more of these sources. Codes match the analysis.

| Code | Source | Rules |
|---|---|---|
| C | Calculated | A fixed formula in the metric registry over rows Claude selected with the closed filters (FR-5.1, FR-5.2). Click view as FR-5.4 |
| M | Modelled | Code applies a fixed formula to assumptions a person entered. Every modelled block is labelled "Modelled, not a forecast" and shows its assumptions and who entered them. Never mixed with actuals in one tile or chart series |
| D | Drafted | Claude writes text only. Every figure in it passes the number check (FR-5.5). Labelled "Drafted by Claude" and editable; edits show "Edited by [name]". Investors see it only once approved |
| Q | Quoted | Text or a figure taken from a company document, shown with the document name and page. Open decision 2: not built until decided |
| E | Entered | Typed by a company user. Labelled "Entered by [name], [date]" (FR-4.8) |
| J | Judgement | A level, score, status or tick set by a named person. Claude may propose; only a person sets it |

**Never:** a figure, score, level or status produced by Claude and shown as fact (principle 2).

## 3. Block types

Built once, reused by every section. "Value" means a figure from C, M or E.

| Type | Block | Content rules |
|---|---|---|
| T1 | Section header | Company, section name, the period covered and "data true as of" from the latest approved update; sub-tab bar |
| T2 | Tile row | Up to four tiles: label, value, one context line. Value colour comes only from the figure's risk level (FR-5.7) or a J status. Each value opens the click view |
| T3 | Target block | One headline target (E), its conditions (E), three or four sub-targets with actuals (C) |
| T4 | Progress list | Label, bar, actual. Numeric rows: actual C against target E. Worded rows ("Done", "Building"): J with name and date, no bar fill unless a person sets one |
| T5 | Call-out | Labelled paragraph. D by default, E if a person writes it. Labels from a fixed list: Position today, Why, Action needed, What it buys, Context |
| T6 | Severity list | Title, description, mitigation, owner, level pill. Text D or E; level J only |
| T7 | Milestone cards | Date, title, description, tag, status. E (or Q once decided); status J; from a project tool in phase 2 |
| T8 | Timeline grid | Tracks by month, one status per cell. Items from T7; statuses J, or C from a project tool in phase 2 |
| T9 | Table | Rows, columns and a totals row. Every number C or M; the totals row is code, never typed |
| T10 | Chart | Bar, line, combined bar and line, donut with drill-down and month filter, radar. C or M data only; colours from tokens; no chart of D content |
| T11 | Story card | Who, their role, what happened, why it matters, optional figures. Text E or D from notes; figures C or E |
| T12 | Checklist | Tasks grouped by week, typed Reflect, Execute or Team, tickable; progress C from ticks. Tasks D, ticks J |
| T13 | Schedule | Time blocks by day, week and fortnight with purpose. D, editable |
| T14 | Detail pop-up | Opens from a row: diagnosis, action, linked items. Same rules as the row's source |
| T15 | Formula strip | Inputs, operators and result laid out as a sum. Inputs E (assumptions) or C; result M |

## 4. Sections

Each table lists the blocks in page order. "Data" names what the block needs; "Empty" says what shows without it.

### 4.1 Overview

| Block | Type | Source | Data | Empty |
|---|---|---|---|---|
| Title | T1 | C | Company profile | Always shown |
| Section cards, one per section | T2 | C, D | Two chips per card from that section's headline figures | Card shows its description and no chips |
| Progress to plan | T4 | C, E | Targets (FR-4.11) | "Set a target to see progress against plan" |
| Headline tiles | T2 | C | Revenue, cash, runway, net burn | "Not shared yet" per tile |

### 4.2 Roadmap: Overview, Product, Sales, Cash, Team

| Sub-tab | Block | Type | Source | Data |
|---|---|---|---|---|
| Overview | Next target | T3 | E, C | Targets, matching measures |
| Overview | Progress to targets | T4 | C, J | Targets; worded statuses |
| Overview | End-of-period goals | T7 | E | Four goals: revenue, customers, team, product |
| Overview | Timeline | T8 | E, J | Milestones from every track |
| Product | Tiles | T2 | E, C | Counts the company chooses, plan progress |
| Product | The build that matters | T5 | D | Milestones, documents |
| Product | Milestones | T7 | E | Product milestones |
| Sales | Tiles | T2 | E, C | Sales targets, conversion from the CRM |
| Sales | How revenue builds | T15 | M | Scenario assumptions (decision 3) |
| Sales | Growth chart | T10 | M | Scenario assumptions, customer plan |
| Sales | Milestones and channels | T7 | E | Sales milestones, channels |
| Sales | Commercial position | T5 | D | Sales figures |
| Cash | Tiles | T2 | C, M | Booked revenue, cost reduction, date revenue covers burn |
| Cash | Action needed | T5 | D | Cash figures |
| Cash | Milestones | T7 | E | Cash milestones |
| Cash | Growth model and month-by-month path | T9 | M | Scenario assumptions, cost plan |
| Team | Tiles | T2 | E (C in phase 2) | Team size, key roles, next hire |
| Team | Hiring milestones and principle | T7, T5 | E | Hiring plan |

Not built: the reference's founder-journey curve. It places the company on a named third-party framework by judgement alone, and adds no figure an investor can trace.

### 4.3 Product: What we built, How it works, Outcomes

| Sub-tab | Block | Type | Source | Data |
|---|---|---|---|---|
| What we built | Tiles | T2 | E | Counts the company chooses |
| What we built | What it is | T5 | E, D | Description; documents once decided |
| What we built | Capabilities | T7 | E | Capability cards in groups |
| How it works | Stages | T7 | E | Stages with steps |
| Outcomes | Tiles | T2 | C, E | Outcome figures |
| Outcomes | What a customer gets | T5 | E, D | Offer description |
| Outcomes | Customer proof | T11 | E, C | Customer, result, two figures |

Product depends most on documents (decision 2). Without them every block is entered.

### 4.4 Cashflow: Overview, Spend, Income, Revenue, Balance, Stack optimisation

Needs bank transactions (decided as a source). Spend, Income, Balance and Stack optimisation show "Add your bank transactions" until they arrive.

| Sub-tab | Block | Type | Source | Data |
|---|---|---|---|---|
| Overview | Tiles | T2 | C, J | Current balance, booked revenue, qualified pipeline, status against break-even target |
| Overview | Position today and why | T5 | D | Cashflow figures |
| Overview | Totals | T2 | C | Capital in, total out, net burn for the period |
| Overview | Money in against money out | T10 | C | Monthly totals |
| Overview | Forward burn | T2 | C, D | Peak month, change, current run rate |
| Spend | Spend wheel | T10 | C | Categories; drill-down into a category; month filter |
| Spend | Spend list | T9 | C | Category totals |
| Income | Income sources | T10 | C, J | Revenue, investment, loans |
| Income | Explanation | T5 | D | Income figures |
| Revenue | Tiles | T2 | C | Booked, collected, qualified pipeline |
| Revenue | Per customer | T11 | C | Invoices and payments per customer |
| Balance | Balance over time | T10 | C | Daily or monthly balance |
| Balance | Tiles | T2 | C, E | Peak, current, forward burn, break-even target date |
| Balance | Position | T5 | D | Balance figures |
| Stack optimisation | Saving | T2 | C | Sum of savings on suppliers marked "cut" |
| Stack optimisation | Already stopped | T6 | C | Recurring suppliers with no charge in two cycles |
| Stack optimisation | Opportunities | T6 | C, J, D | Recurring suppliers: trend, overlap group, recommendation (J), reason (D) |

Rules:
- **Categories.** Claude picks each transaction's category from a closed list; code adds up. The list is a config file, editable without a deploy.
- **Payroll.** One payroll total only, never a line per person. Pay is dropped at intake under the hard rule (section 6).
- **Uncertain income.** An income line that could be revenue, investment or a loan becomes one question to a person (principle 4), then the answer is remembered for that counterparty.
- **Corrections.** A payment and its reversal within 30 days are netted and shown as one line with both dates.

### 4.5 Pipeline: Deal stages, Scenario modelling

| Sub-tab | Block | Type | Source | Data |
|---|---|---|---|---|
| Deal stages | Total and note | T2, T5 | C, D | Qualified pipeline |
| Deal stages | Stages | T9 | C | Stage, count, value, deal names |
| Deal stages | Early prospects | T7 | C, E | Deals before the qualifying stage, next step; never counted in the total |
| Scenario modelling | Assumptions | T15 | E | Rates, prices, volumes (decision 3) |
| Scenario modelling | Segment tiles | T2 | M | Results at each rate, per segment |
| Scenario modelling | Per-deal tables | T9 | M | Per deal at each rate |

The qualifying stage, and which segment a deal belongs to, are company settings (E). A deal with no volume uses the company's default volume and is starred.

### 4.6 Momentum: Validation, Recognition, Cost savings

| Sub-tab | Block | Type | Source | Data |
|---|---|---|---|---|
| Validation | Tiles | T2 | C, E | Conversion figures the company chooses |
| Validation | Endorsements | T11 | E, D | Who, role, what happened |
| Recognition | Tiles and cards | T2, T11 | E, C | Talks, invitations, awards; live customers from data |
| Cost savings | Tiles | T2 | C, E | Spend on stopped suppliers, monthly saving |
| Cost savings | Suppliers stopped | T9 | C, J | Suppliers a person marks as stopped |
| Cost savings | The change and where it goes | T5 | D, E | Cost figures |

Momentum replaces "Market validation" (decided). The reference's "What we built" under Momentum moves to Product.

### 4.7 Risk register: Without capital, Market, Execution, Team

| Sub-tab | Block | Type | Source | Data |
|---|---|---|---|---|
| Without capital | Tiles | T2 | C, E | Runway without new money, invoiceable now, cost reduction, funding trigger |
| Without capital | Position and what capital buys | T5 | D | Cash figures, risks |
| Every sub-tab | Risks | T6 | E, D, J | Title, description, mitigation, owner, level |
| Market, Team | Context | T5 | D | Risks in that category |

Risks arrive three ways:
- **Entered** by a company user.
- **Raised by a rule.** Rules live in config with defaults: runway under six months, one customer over 40% of revenue, a deal stalled over 30 days, burn up over 20% month on month.
- **Proposed by Claude** from data and documents.

A rule-raised or proposed risk shows "Proposed" until a person sets its level. Only a person sets or changes a level.

### 4.8 CEO development: Gap map, 30-day plan, Operating rhythm

Investors see this section (decided).

| Sub-tab | Block | Type | Source | Data |
|---|---|---|---|---|
| Gap map | Tiles | T2 | C | Counts of critical, high and strength areas from scores; plan progress |
| Gap map | Radar | T10 | C | Scores by area |
| Gap map | How it was assessed | T5 | E | Date and method |
| Gap map | Areas | T6, T14 | J, D | Area, score 0 to 100 set by the CEO, level, diagnosis and action |
| 30-day plan | Progress and daily structure | T2, T5 | C, D | Ticks, protected time |
| 30-day plan | Tasks | T12 | D, J | Thirty tasks, typed and ticked |
| Operating rhythm | The problem and the schedule | T5, T13 | D, E | Daily, weekly and fortnightly blocks |

The areas and diagnoses come from an assessment conversation with Claude, like the setup chat (chapter 8). Claude proposes areas and wording; the CEO sets every score.

## 5. Data needed

| Source | Feeds | Status |
|---|---|---|
| Finance export (existing) | Cashflow overview, Overview tiles | Built |
| CRM deals (existing) | Pipeline, Revenue booked, Sales tiles | Built; needs deal name, next step and segment fields |
| Bank transactions | Cashflow spend, income, revenue collected, balance, stack optimisation; Momentum cost savings | Decided as a source. Bank export, accounting connection, or both: see decision 6 |
| Scenario assumptions | Roadmap sales and cash, Pipeline scenarios | Decision 3 |
| Documents (deck, plan, notes) | Product, milestones, Momentum stories, risk proposals | Decision 2; file formats are already an open decision (FRD chapter 14) |
| Assessment conversation | CEO development | Decided in scope; built like the setup chat |
| Monthly check-in conversation | Anything no source holds | Decision 4 |
| Project tool (Jira, monday.com) | Roadmap timeline statuses | Phase 2 |
| HR export | Team headcount | Phase 2 |

## 6. Privacy

- Pay is never stored or shown per person. Payroll appears as one total in Cashflow (hard rule, CLAUDE.md).
- Bank details, personal emails and dates of birth in transaction references are dropped at intake as today.
- Counterparty names in transactions are kept: they are needed to group suppliers and customers.
- CEO development is visible to every investor of the company; the CEO sees exactly what investors will see before approving.

## 7. Evaluations before a section is done

Each needs a golden set and a pass mark, run in CI with recorded answers (FR-13.2), as for skill 1:

1. Transaction categories.
2. Revenue, investment or loan.
3. Recurring supplier detection.
4. Drafting cards from documents, with every card traceable to a passage (once decision 2 is made).
5. Risk proposals against risks a CEO kept.

The benchmark (analysis section 8, item 6) is run privately before each section ships.

## 8. Open decisions

| # | Decision | Blocks |
|---|---|---|
| 1 | Phase: MVP, or phase 2 behind a flag | Build order |
| 2 | Documents as a source, and figures quoted from them shown as quoted (Q) | Product, milestones, stories, risk proposals |
| 3 | Scenario assumptions entered by the company; defaults taken from the company's own data where it has them | Roadmap sales and cash, Pipeline scenarios |
| 4 | A monthly check-in conversation that asks only for what no source holds | Momentum, risks, worded progress |
| 5 | Where updates live: in each section under its figures, or as their own page | Navigation |
| 6 | The CEO asked to "test both". Either a bank export against an accounting connection (no conflict), or one payroll total against pay per person (per-person pay needs the hard rule changed). To confirm which | Cashflow sources and spend |

## 9. Proposed build order

One PR per step, each ending with a demo and a benchmark run.

1. Navigation: section bar, sub-tabs, section header, block types T1, T2, T4, T5.
2. Cashflow, with bank transactions and evaluations 1 to 3.
3. Pipeline, including scenario modelling once decision 3 is made.
4. Roadmap.
5. Risk register, with rules.
6. Momentum.
7. CEO development, with the assessment conversation.
8. Product, once decision 2 is made.
