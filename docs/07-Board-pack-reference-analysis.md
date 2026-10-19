# Board pack reference analysis

The evidence behind the board pack sections specification (docs/06-Board-pack-sections.md) and FRD chapter 15. 19 October 2026.

## 1. Sources and method

**Sources.** Two investor dashboards a company built and filled in by hand, supplied by the CEO on 19 October 2026 as reference material:

| Ref | What it is | Sections |
|---|---|---|
| A | The earlier version | Overview, Roadmap, Product, Cashflow, Momentum, Risks, CEO development |
| B | The later, edited version | Overview, Roadmap, Product, Cashflow, Pipeline, CEO development, Market validation |

Both files are held privately and are **not** in this repository. The repository is public, the files hold another company's finances, customers, investors and plans, and CLAUDE.md keeps BoardRoom.io separate from any other business. This document records their structure only. No names, figures or wording from them appear here or in the product.

**Method.** Each file was opened in a browser and every top-level section and sub-tab was walked in turn. Each block on each page was listed with its type and contents. Each block was then classified by where its content would come from in BoardRoom, under the principles in CLAUDE.md. The counts in section 6 are totals of the tables in section 5, not estimates.

**Limits.**
- The charts did not render offline. Their type and subject come from the files' chart definitions and headings.
- Where A and B differ, B is used, and A is used only for what B dropped: the risk register, two Product sub-tabs and "What we built".
- The classification says where content **can** come from. It does not prove that Claude does it well. Section 8 lists what is still unproven.

## 2. Source codes

| Code | Meaning | Allowed by |
|---|---|---|
| **C** | Calculated by code from a file or a connected tool, with a fixed formula | Principle 2 |
| **M** | Modelled by code from assumptions a person entered; labelled "Modelled, not a forecast" | Principle 2 |
| **D** | Drafted by Claude from figures and documents; text only, passes the number check, approved by a person | Principles 2 and 3 |
| **Q** | Quoted from a company document (deck, plan, notes), shown with the document name | Not yet allowed: open decision |
| **E** | Entered by a person, labelled "Entered by [name], [date]" | FR-4.8 |
| **J** | A judgement a person makes: a level, a score, a status, a tick | FR-4.8 |

A block whose parts come from different sources is listed with each code, primary first.

## 3. Navigation

| | Reference dashboards | BoardRoom.io today |
|---|---|---|
| Top level | One bar across the top, every section, always visible | Company users: left sidebar (Dashboard, Board pack, Files, Team, Settings), then section tabs inside Board pack. Investors: header, company picker, then section tabs |
| Second level | Every section has sub-tabs (2 to 6 per section) | None |
| Home | Six cards: icon, title, one-line description, two or three figure chips, arrow | Same layout; most cards have no chips |
| Updates | Not a concept. The dashboard is one snapshot, edited and re-sent | A tab in the section bar: dated updates with approval, comments and commentary |
| Clicks to content | One | Two for company users |
| Header per section | Company name, section title, period covered, sub-tab bar | Section tabs only |

**Decided (CEO, 19 October 2026):** sections move to one top bar with sub-tabs, as in the references.

## 4. Block types found

Every block on every page is one of these fifteen types. The specification builds each once and reuses it.

| # | Type | What it shows | Found in |
|---|---|---|---|
| T1 | Section header | Company, section title, period covered, sub-tabs | Every section |
| T2 | Tile row | Up to four tiles: label, value, context line; value coloured by status | Every section |
| T3 | Target block | One large target, a line of conditions, three or four sub-targets | Roadmap |
| T4 | Progress list | Rows of label, bar, actual; actual may be a word ("Done") | Roadmap, Overview |
| T5 | Call-out | A labelled paragraph: position today, action needed, why, what capital buys | Every section |
| T6 | Severity list | Rows of title, description, mitigation, level pill | Risks, Stack optimisation |
| T7 | Milestone cards | Date, title, description, tag | Roadmap (all tracks) |
| T8 | Timeline grid | Tracks by month, a status in each cell | Roadmap |
| T9 | Table | Rows and columns, with a totals row | Cashflow, Pipeline, Roadmap |
| T10 | Chart | Bar, line, combined bar and line, donut with drill-down and month filter, radar | Cashflow, Roadmap, CEO development |
| T11 | Story card | Person, role, what happened, why it matters | Momentum |
| T12 | Checklist | Tasks grouped by week, each typed and tickable, with progress | CEO development |
| T13 | Schedule | Time blocks by day, week and fortnight | CEO development |
| T14 | Detail pop-up | Opens from a row: diagnosis, action, linked items | CEO development, Roadmap, Stack optimisation |
| T15 | Formula strip | Inputs, operators and result laid out as a sum | Roadmap |

## 5. Inventory by section

### 5.1 Overview (B)

| Block | Type | Contents | Source |
|---|---|---|---|
| Title | T1 | Company, "The Full Picture", period, confidentiality | C |
| Section cards | T2 | Six cards, each with a description and two or three chips | C, D |
| Data as of | T1 | "All data current as of [date]" | C |

### 5.2 Roadmap (B): Overview, Product, Sales, Cash, Team

| Sub-tab | Block | Type | Contents | Source |
|---|---|---|---|---|
| Overview | Next target | T3 | One headline target, conditions, four sub-targets | E, C |
| Overview | Progress to targets | T4 | Eight rows, five numeric and three worded | C, J |
| Overview | End-of-period goals | T7 | Four cards: revenue, customer, team, product | E, Q |
| Overview | Stage curve | T10 | Company placed on a named founder-journey curve | J |
| Overview | Timeline | T8 | Five tracks, about 30 items, six months, status per cell | E, Q, C |
| Product | Tiles | T2 | Then, now, biggest build, plan progress | E, C |
| Product | The one build that matters | T5 | Why it matters | D, Q |
| Product | Milestones | T7 | Ten cards | E, Q |
| Sales | Tiles | T2 | Target customers, target revenue, volume, conversion | E, C |
| Sales | How revenue builds | T15 | Volume times fee plus volume times rates times price | M |
| Sales | Growth chart | T10 | Customers as columns, revenue lines at three rates | M |
| Sales | Milestones | T7 | Seven cards | E, Q |
| Sales | Commercial position | T5 | Revenue live, what accelerates it | D |
| Sales | Channels | T7 | Four channel cards with status | E, Q |
| Cash | Tiles | T2 | Booked revenue, cost reduction, a count, date revenue covers burn | C, M |
| Cash | Action needed | T5 | What must happen now | D |
| Cash | Milestones | T7 | Six cards | E, Q |
| Cash | Growth model | T9 | Per customer at three rates | M |
| Cash | Month-by-month path | T9 | Customers, revenue, cost, profit, margin | M |
| Team | Tiles | T2 | Team size, key roles, next hire | C, E |
| Team | From consultants to a team | T5 | The change and why | D, Q |
| Team | Hiring milestones | T7 | Five cards | E, Q |
| Team | Hiring principle | T5 | One standard for every hire | E |

### 5.3 Product (A and B): What we built, How it works, Outcomes

| Sub-tab | Block | Type | Contents | Source |
|---|---|---|---|---|
| What we built | Tiles | T2 | Counts then and now, model tiers, integrations | E, Q |
| What we built | What it is | T5 | One-paragraph description | Q, D |
| What we built | Capabilities | T7 | Twelve cards in three groups | Q |
| How it works | Stages | T7 | Three phases, eight stages, steps in each | Q |
| How it works | Example output | T9 | A worked example table | Q |
| Outcomes | Tiles | T2 | Four outcome figures | C, E |
| Outcomes | What a customer gets | T5 | The offer in one paragraph | Q |
| Outcomes | Customer proof | T11 | Three cards, two figures each | C, E |
| Outcomes | Beyond the result | T7 | Four cards | Q |

### 5.4 Cashflow (B): Overview, Spend, Income, Revenue, Balance, Stack optimisation

| Sub-tab | Block | Type | Contents | Source |
|---|---|---|---|---|
| Overview | Tiles | T2 | Current balance, booked revenue, qualified pipeline, status against target | C, J |
| Overview | Situation today and why | T5 | Two paragraphs | D |
| Overview | Opportunity ahead and why | T5 | Two paragraphs | D |
| Overview | Totals | T2 | Capital in, total out, net burn | C |
| Overview | Money in against money out | T10 | Bar chart by month | C |
| Overview | Forward burn | T2 | Peak month, reduction, current run rate, each with a note | C, D |
| Overview | Pipeline to break-even | T9 | What must close | C, M |
| Spend | Spend wheel | T10 | Donut by category, drill-down into three categories, month filter | C |
| Spend | Spend list | T9 | Every category with total | C |
| Income | Income sources | T10 | Revenue, investment and loans | C, J |
| Income | Explanation | T5 | Loans and corrections explained | D |
| Revenue | Tiles | T2 | Booked, collected, qualified pipeline | C |
| Revenue | Reclassification note | T5 | A payment that is a loan, not revenue | D, J |
| Revenue | Per customer | T11 | Three cards with invoice lines | C |
| Revenue | Upside | T5 | What a larger run would be worth | M |
| Balance | Balance over time | T10 | Line chart | C |
| Balance | Tiles | T2 | Peak, current, forward burn, target date | C, E |
| Balance | Bridge to break-even | T5 | The cash position explained | D |
| Stack optimisation | Saving | T2 | Potential monthly saving | C |
| Stack optimisation | Context | T5 | What changed in the stack | D |
| Stack optimisation | Already stopped | T6 | Suppliers with no recent charge | C |
| Stack optimisation | Opportunities | T6 | Seven suppliers: cost trend, recommendation pill, saving | C, J, D |

### 5.5 Pipeline (B): Deal stages, Scenario modelling

| Sub-tab | Block | Type | Contents | Source |
|---|---|---|---|---|
| Deal stages | Total and note | T2, T5 | Qualified pipeline and a paragraph | C, D |
| Deal stages | Stages | T9 | Four stages: count, value, named deals | C |
| Deal stages | Early prospects | T7 | Eight cards: volume, next step, not counted in the total | C, E |
| Scenario modelling | Assumptions note | T5 | How the model works, starred defaults | M |
| Scenario modelling | Segment tiles | T2 | Three rates for each of two segments | M |
| Scenario modelling | Pilot table | T9 | Per deal at three rates | M |
| Scenario modelling | Full-size table | T9 | Per deal at three rates | M |

### 5.6 Momentum (A and B): Validation, Recognition, Cost savings

| Sub-tab | Block | Type | Contents | Source |
|---|---|---|---|---|
| Validation | Tiles | T2 | Event, partner and reply conversion | C, E |
| Validation | Endorsements | T11 | Three story cards | E, D |
| Recognition | Tiles | T2 | Speaking slots, invitations, live customers, a rate | E, C |
| Recognition | Recognition cards | T11 | Four cards | E |
| Cost savings | Tiles | T2 | Spend stopped, monthly saving, payment end, where it goes | C, E |
| Cost savings | The change | T5 | One paragraph | D |
| Cost savings | Suppliers stopped | T9 | Four suppliers with totals | C, J |
| Cost savings | Where it goes next | T5 | One paragraph | D, E |

A also had "What we built" under Momentum. It repeats Product, What we built, so it is not listed again.

### 5.7 Risk register (A): Without capital, Market, Execution, Team

| Sub-tab | Block | Type | Contents | Source |
|---|---|---|---|---|
| Without capital | Tiles | T2 | Runway without new money, invoiceable now, cost reduction, funding trigger | C, E |
| Without capital | The position | T5 | What happens without the capital | D |
| Without capital | What stops | T6 | Six risks with level | E, D, J |
| Without capital | What capital buys | T5 | One paragraph | D |
| Market | Context | T5 | One paragraph | D |
| Market | Risks | T6 | Four risks with mitigation and level | E, D, J |
| Execution | Risks | T6 | Four risks with mitigation and level | E, D, J |
| Team | Context | T5 | One paragraph | D |
| Team | Risks | T6 | Four risks with mitigation and level | E, D, J |

### 5.8 CEO development (B): Gap map, 30-day plan, Operating rhythm

| Sub-tab | Block | Type | Contents | Source |
|---|---|---|---|---|
| Gap map | Tiles | T2 | Critical gaps, high priorities, strengths, plan progress | C |
| Gap map | Radar | T10 | Score across six areas | C |
| Gap map | How it was assessed | T5 | Date and method | E |
| Gap map | Gap rows | T6, T14 | Twelve areas: score 0 to 100, level, detail pop-up | J, D |
| 30-day plan | Progress and daily structure | T2, T5 | Percentage done, protected time blocks | C, D |
| 30-day plan | Tasks | T12 | Thirty tasks in five groups, typed Reflect, Execute or Team | D, J |
| Operating rhythm | The problem | T5 | One paragraph | D |
| Operating rhythm | Schedule | T13 | Four daily, five weekly, one fortnightly block | D, E |
| Operating rhythm | A delegated build brief | T5 | Steps for a team member | D |

## 6. Counts

Counted from section 5, by primary source (the first code on each row):

| Section | Blocks | C | M | D | Q | E | J |
|---|---|---|---|---|---|---|---|
| Overview | 3 | 3 | 0 | 0 | 0 | 0 | 0 |
| Roadmap | 23 | 3 | 4 | 4 | 0 | 11 | 1 |
| Product | 9 | 2 | 0 | 0 | 6 | 1 | 0 |
| Cashflow | 22 | 15 | 1 | 6 | 0 | 0 | 0 |
| Pipeline | 7 | 3 | 4 | 0 | 0 | 0 | 0 |
| Momentum | 8 | 3 | 0 | 2 | 0 | 3 | 0 |
| Risk register | 9 | 1 | 0 | 4 | 0 | 4 | 0 |
| CEO development | 9 | 3 | 0 | 4 | 0 | 1 | 1 |
| **Total** | **90** | **33** | **9** | **20** | **6** | **20** | **2** |

What this shows, without rounding it up:

- **62 of 90 blocks (69%) need nobody to write anything:** 33 calculated, 9 modelled once assumptions exist, and 20 drafted by Claude for approval.
- **26 blocks (29%) need content a person holds.** 20 are entered and 6 are quoted from documents. These sit in Roadmap milestones, Product, Momentum stories and risks. If documents become a source, the 6 quoted blocks and most of the 20 entered ones become drafts from documents for a person to approve, rather than typing.
- **2 blocks are pure judgement:** the stage curve and the gap scores. Several other blocks carry a judgement inside them (risk levels, stack recommendations, worded progress, ticks).
- **Cashflow is the most automatable section** (15 of 22 calculated) and is blocked only by having no bank transaction source.
- **Product is the least automatable** (6 of 9 quoted). It depends on documents being a source.

## 7. BoardRoom today against the reference

| Section | Reference blocks | Built today | Gap |
|---|---|---|---|
| Overview | 3 | 3, chips on one card | Chips on every card |
| Roadmap | 23 | 0 ("Coming in phase 2") | Everything |
| Product | 9 | 0 ("Coming in phase 2") | Everything |
| Cashflow | 22 | 3 (one commentary block, four tiles, one chart) | Sub-tabs, bank transaction source and 19 blocks |
| Pipeline | 7 | 1 (two tiles under Market validation) | Sub-tabs, stages table, early prospects, scenarios |
| Momentum | 8 | 0 | Everything |
| Risk register | 9 | 0 | Everything |
| CEO development | 9 | 0 | Everything |

BoardRoom has three things the references do not: every figure traces to its source rows (FR-5.4), commentary is number-checked (FR-5.5), and updates keep dated history with approval and comments (chapter 6). The specification keeps all three.

## 8. What is not proven yet

These are claims the specification depends on. Each needs an evaluation set and a pass mark before its section is called done.

1. **Bank transaction categories.** Claude choosing a category for each transaction from a closed list. Needs a hand-labelled golden set, scored like the skill 1 evals.
2. **Loan, investment or revenue.** Telling these apart in income. Needs labelled examples; anything uncertain must become one question, never a guess.
3. **Drafting from documents.** Turning a deck or plan into milestone cards, capability cards and stories without inventing anything. Needs documents with known contents and a check that every card traces to a passage.
4. **Risk proposals.** Claude proposing risks from data and documents. Needs a review of proposals against the risks a CEO actually kept.
5. **Recurring supplier detection.** Finding subscriptions, overlaps and stopped suppliers. Needs transaction sets with known answers.
6. **The whole picture.** Fed the raw files behind a reference dashboard, how many of its 90 blocks BoardRoom fills correctly. This is the benchmark for the sections specification, run privately and never committed.
