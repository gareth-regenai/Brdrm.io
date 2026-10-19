# BoardRoom.io BRD

Business requirements for the MVP, one chapter per section of the revised spec. 18 October 2026.

## About this document

This BRD is for the build team and for Claude Code. It says what the business needs from each part of the MVP. The FRD says how the system meets it. Requirements are numbered BR-chapter.number, and the FRD traces every functional requirement back to one of them.

**Principle**BoardRoom is AI-native. The AI reads whatever a company has and chooses the data. Code does every calculation. Rules exist only where a figure must be exact.

### Users

| User            | Who they are                                                                 | What they need                                                               |
|-----------------|------------------------------------------------------------------------------|------------------------------------------------------------------------------|
| CEO             | Runs the company, usually also the finance lead                              | Share accurate figures with investors in minutes, with nothing to prepare    |
| Department lead | Owns sales, delivery or people                                               | Add their own files without help                                             |
| Contributor     | A team member                                                                | Add files and comment                                                        |
| Investor        | Angel, syndicate lead, fund or solo capitalist backing one or more companies | See every company they back in one place, spot risk early, trust the numbers |
| Platform admin  | BoardRoom.io staff                                                           | Support customers safely, with access that is time-limited and visible       |

### Phases

| Phase                          | Scope                                                                                                                                   |
|--------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------|
| Phase 1, the MVP               | Finance and sales pipeline files, targets from the setup chat, one reporting currency, investor overview with six of the eight measures |
| Phase 2, straight after launch | Product delivery and people files, currency conversion, the last two overview measures                                                  |

## 1. Summary and scope

[Phase 1 and 2]

**Business need**Small and early-stage companies have to report to their investors but have little time, no finance team and numbers spread across several tools. Investors chase updates by email and get figures in different shapes from each company. Existing tools ask the company to fill templates and forms first.

### Outcomes

- BR-1.1A company can share figures with its investors using files it already has, with nothing to prepare.
- BR-1.2Every figure an investor sees traces to its source: an uploaded row or a named person who entered it.
- BR-1.3An investor sees every company they back in one place.
- BR-1.4The AI reads files and chooses the data. Code does all arithmetic, so figures are exact and repeatable.
- BR-1.5The MVP ships in two phases, so the first release covers the most important figures quickly.

### Success measures

- First upload to investors seeing figures in under 30 minutes.
- Most real files understood with no correction, measured on a labelled sample from the beta.
- No cross-tenant data access, proven by automated tests.
- Every published figure traceable to its source.

**Out of scope:** live integrations (the first connector, such as Xero, is a candidate to pull forward), M&A deal rooms, benchmarking, SSO, custom designs beyond a logo and colours, a mobile app, and pricing.

## 2. Users, tenants and roles

[Phase 1]

**Business need**A company has several people who add data. An investor often backs several companies. One company's numbers must never reach another company or an investor who does not back it.

### Outcomes

- BR-2.1A company workspace holds many users with different roles.
- BR-2.2An investor has one login linked to every company that has invited them.
- BR-2.3One invite gives an investor standing access to a company. Every later update reaches them with no further action.
- BR-2.4Co-investors in the same company can see each other.
- BR-2.5Nothing crosses between companies.

### Business rules

- A company team sees its own company only.
- Investors view and comment only. They approve nothing.
- Who can approve an update is a permission per company. The default is the CEO.
- A user can belong to several tenants, such as a founder who is also an angel elsewhere.
- The platform holds no cap table. The invite is the link between an investor and a company.
- The deal-team tenant type is reserved in the data model but not built.

### Success measures

- Zero cross-tenant incidents in testing and beta.
- No investor ever needs a second invite to see a new update.

## 3. How it works

[Phase 1]

**Business need**The flow must ask as little of the company as possible, while the company stays in control of what its investors see.

### Outcomes

- BR-3.1Data moves from file to investor in six steps: set up, add files, understand, calculate, describe, share.
- BR-3.2A person is asked something only when the AI cannot work out a figure without them.
- BR-3.3The company decides what goes to its investors.
- BR-3.4Each update reaches investors as a dated statement of who added what.

### Success measures

- Questions asked per upload, tracked in the beta, with a target agreed from the first results.
- Time from upload to update shared, within the 30-minute goal in chapter 1.

## 4. Files and intake

[Phase 1 and 2]

**Business need**A company's data sits in exports from many tools and never matches our format. Rejecting files or asking for templates is the biggest source of friction. Pay data must never be held.

### Outcomes

- BR-4.1Any file is accepted. The AI works out what each column is and ignores what it does not need.
- BR-4.2The department guidance (finance, sales pipeline, product delivery, people, plan) shows what helps but never blocks a file.
- BR-4.3Pay-like columns (salary, bonus, bank details, national insurance numbers, dates of birth) are never stored or sent to the AI. The rest of the file is kept.
- BR-4.4A person can enter a figure or forecast by hand. It is labelled with their name and the date.
- BR-4.5Targets are captured without a plan file.
- BR-4.6Phase 2: any currency per row, converted to the company's reporting currency with a visible rate the company can override.
- BR-4.7If the AI is unavailable, the company can still map columns by hand.
- BR-4.8What the AI understood and ignored is logged for our dev team only.

### Business rules

- Phase 1 covers finance and sales pipeline files. Product delivery and people follow in phase 2.
- Delivery is measured as tasks completed against tasks planned. Points are not used.
- With no plan there is no "against plan" figure. The tile reads "No plan set" and nothing is blocked.
- Money is never added across companies.

### Success measures

- Share of beta files understood with no correction, tracked from the first upload.
- Zero sensitive columns found in storage or AI payloads, proven by tests.

## 5. Figures and metrics

[Phase 1 and 2]

**Business need**Investors make decisions on these figures, and for a small company a few thousand pounds can decide whether payroll is met. Figures must be exact, comparable across companies and traceable.

### Outcomes

- BR-5.1Each measure uses a fixed, standard formula, so the same measure means the same thing for every company.
- BR-5.2The AI chooses which of the company's rows feed each formula. Code runs the formula. A company-specific method is allowed only where the standard one cannot work, and it is flagged.
- BR-5.3Clicking any figure shows its exact value, its source, what it moves (for example cash moves runway) and its risk level.
- BR-5.4Figures written in commentary are only normal rounding of the real figure. There is no tolerance band.
- BR-5.5Money is displayed at a precision set by the company's annual revenue, which the company can adjust.
- BR-5.6Each figure carries a High, Medium or Low risk level from warning lines. Defaults ship in config, and each company can choose what it sees.

### Business rules

| Annual revenue                     | Money shown as                               |
|------------------------------------|----------------------------------------------|
| Under £100k, including pre-revenue | Whole pounds                                 |
| £100k to £1m                       | £k, 1 decimal                                |
| £1m to £10m                        | £m, 3 decimals over £1m; £k, 1 decimal below |
| £10m to £100m                      | £m, 2 decimals over £1m; £k whole below      |
| Over £100m                         | £m, 1 decimal                                |

- Months and percentages always show one decimal.
- The number check ignores dates, quarters and counts of things.
- The exact figure is always one click away.

### Success measures

- Every commentary figure passes the check, or the section is written by a person.
- Calculated figures match hand-checked golden datasets exactly.
- No custom method appears without a flag.

## 6. Updates and approvals

[Phase 1]

**Business need**Companies report when they have data, not on a fixed cycle. Locking and versioning add process for no benefit, but investors still need to see when a figure has changed.

### Outcomes

- BR-6.1Each addition of data is an update, shown as a dated line: "CEO Sam Hart added new financials. Data true as of 17 Oct 2026. Subject to change and may be edited."
- BR-6.2An update can be edited after it goes out, and then shows "Last edited \[date\]".
- BR-6.3Approval happens on the company side. Who approves is a permission per company, defaulting to the CEO.
- BR-6.4Commentary speaks as the company ("we") by default, with a setting for third person. Labels always say who did what, for example "Drafted by Claude".
- BR-6.5Investors comment on an update and the company replies in the same thread.
- BR-6.6Every figure keeps its lineage, so it can always be traced.

### Success measures

- An investor can always see when an update was last changed.
- No update reaches investors without meeting the company's approval setting.

## 7. Investor portfolio overview

[Phase 1 and 2]

**Business need**An investor logging in wants to see every company they back and which one needs attention first. Companies must be judged the same way to be compared fairly.

### Outcomes

- BR-7.1On login an investor sees one card per company, highest risk first.
- BR-7.2Every card shows the same eight measures with the same High, Medium and Low lines.
- BR-7.3The CEO never sees the overview.
- BR-7.4Clicking a company opens that company's own section.
- BR-7.5In phase 1, delivery and headcount show "Coming in phase 2".

| \#  | Measure                | Phase |
|-----|------------------------|-------|
| 1   | Cash balance           | 1     |
| 2   | Runway (months)        | 1     |
| 3   | Net monthly burn       | 1     |
| 4   | Revenue against plan   | 1     |
| 5   | Pipeline coverage      | 1     |
| 6   | Delivery against plan  | 2     |
| 7   | Headcount against plan | 2     |
| 8   | Last update (days ago) | 1     |

### Business rules

- Warning lines on the overview are one common set from config. A company's own settings apply only on its own pages.
- Money shows in each company's reporting currency and is never added across companies.
- No commentary, tables or filters on the overview beyond sorting by risk.

### Success measures

- An investor can name their highest-risk company without opening any company, checked in beta sessions.

## 8. Setup chat

[Phase 1]

**Business need**Settings forms and plan files are work a small company will not do. The AI should make most of the setup assumptions itself.

### Outcomes

- BR-8.1The AI infers the setup: currency from the files, what the business does from its website and data, revenue lines, targets from any budget or forecast, and display scale from revenue.
- BR-8.2The AI states its assumptions and the CEO can correct them.
- BR-8.3The AI asks only what it cannot find, usually targets and which investors to invite.
- BR-8.4The chat can be skipped and run again later, for example "update my targets".
- BR-8.5Assumptions cover setup only, never the figures.

### Success measures

- A company is set up with at most two questions.

## 9. Tiers and limits

[Parked]

**Business need**Pricing, tiers and limits are under separate commercial review. The build must not hard-wire any of them.

### Outcomes

- BR-9.1Entitlements are held as named keys, so tiers and limits can change without code changes.
- BR-9.2Stripe Checkout and the customer portal are the billing route.
- BR-9.3Approval is a permission, never tied to a price tier.

**Open:** whether a limit warns or blocks the action.

## 10. Architecture and services

[Phase 1]

**Business need**A small team must ship quickly and keep the product reliable. The architecture must support the AI doing more of the work, with fewer screens for people to check.

### Outcomes

- BR-10.1The browser talks only to a gateway. Everything else is private.
- BR-10.2The AI has three jobs: understand files, choose rows for each fixed formula, and write commentary. It never edits data and never writes code that runs.
- BR-10.3The setup chat writes straight into company settings.
- BR-10.4Customers who need zero data retention can use a path with no AI code execution.
- BR-10.5The pipeline keeps working if the AI is down, through manual mapping.

**Open:** whether to start with separate services or one app plus a worker. The build team proposes, keeping the app thin.

## 11. Security and data protection

[Phase 1]

**Business need**Board figures are commercially sensitive. Customers must trust that no other company, investor or outsider can see their data, and that sensitive staff data is never held.

### Outcomes

- BR-11.1Every row belongs to one tenant, and isolation is enforced in the database.
- BR-11.2Investor access is per company and standing from one invite.
- BR-11.3Sensitive columns are dropped at intake and never stored or sent to the AI.
- BR-11.4The AI sees only headers, redacted samples and aggregates, and no AI-written code is run.
- BR-11.5Logins, uploads, approvals, edits to updates and every investor view are audited.
- BR-11.6Staff support access is time-limited and visible to the customer.

**Before launch:** an external penetration test, a dependency and licence review, a privacy notice and ICO registration if required. Data roles and retention are to be confirmed with a solicitor.

## 12. Infrastructure

[Phase 1]

**Business need**Hosting must keep data in Europe, recover from failure and cost little at the start.

### Outcomes

- BR-12.1Everything runs on Render in Frankfurt, with file storage in the UK or EU.
- BR-12.2Production and staging are separate, with a preview environment per change.
- BR-12.3Backups allow point-in-time recovery, and a restore is tested before launch.
- BR-12.4The starting cost follows the service count chosen in chapter 10.

## 13. Build plan and testing

[Phase 1 and 2]

**Business need**The AI intake is the product. It must be built and proven first, and progress must be visible so the build does not drift back to rigid rules.

### Outcomes

- BR-13.1The AI intake is built first, and working software is demonstrated at the end of every step.
- BR-13.2Every rule, rejection or required field must answer "why can't the AI handle this?" before it is built.
- BR-13.3No step is done until its tests pass in CI.
- BR-13.4Six critical journeys work end to end before beta: set up through the chat; upload a clean file and see tiles; upload a messy file and see tiles with at most one question; draft commentary that passes the check; send and edit an update; log in as an investor, see the portfolio, open a company, trace a figure and comment.
- BR-13.5A beta with 5 to 10 companies meets the success measures in chapter 1.

## 14. Risks and open decisions

### Open decisions

| Decision                                   | Status                             |
|--------------------------------------------|------------------------------------|
| Who builds it, and how many engineers      | Settle first                       |
| Service count                              | To propose; keep the app thin      |
| First connector, such as Xero              | To decide                          |
| Limits warn or block                       | To decide                          |
| Named check on cash, burn and runway       | To decide                          |
| Warning-line defaults                      | To propose and agree               |
| Allowed row filters for the AI; rates feed | To propose                         |
| Approval permissions                       | Designed later; default is the CEO |
| Commercials                                | Parked                             |
| Board pack sections: phase                 | To discuss                         |
| Documents as a source; quoted figures      | To decide                          |
| Scenario assumptions                       | To decide                          |
| Monthly check-in conversation              | To decide                          |
| Where updates live in the board pack       | To decide                          |

### Business risks

| Risk                                               | Response                                                                                                 |
|----------------------------------------------------|----------------------------------------------------------------------------------------------------------|
| The build drifts back to rigid rules and templates | The gate question in BR-13.2, AI intake first, a demo every step                                         |
| The AI misreads a column or picks the wrong rows   | Fixed formulas, closed row filters, the method shown in the click view, the number check, blocking evals |
| A tenant isolation bug leaks a company's numbers   | Database isolation, two-tenant tests, a penetration test                                                 |
| Data retention worries block sales                 | The zero-data-retention path and a clear subprocessor page                                               |
| The product is easy to copy                        | Traceable figures, near-zero setup and the investor portfolio view                                       |

## 15. Board pack sections

[Phase to be decided, see chapter 14]

**Business need**A board wants the full picture: where the cash goes, what is in the pipeline, what the plan is, what could go wrong and how the founder is growing. Companies that build this by hand produce rich dashboards, but every figure and paragraph is typed and re-typed each month. BoardRoom must reach the same depth while the company prepares nothing. Evidence: docs/07-Board-pack-reference-analysis.md. Detail: docs/06-Board-pack-sections.md.

### Outcomes

- BR-15.1The board pack has eight sections in one bar, the same for the company and its investors: Overview, Roadmap, Product, Cashflow, Pipeline, Momentum, Risk register and CEO development. Each section has its own sub-tabs.
- BR-15.2Content fills itself wherever a source holds it. People are asked only for what no source holds, and then in as few questions as possible.
- BR-15.3Every block shows where its content came from: calculated, modelled, drafted by Claude, entered by a person, or judged by a person.
- BR-15.4Bank transactions are a source, through a bank export, an accounting connection or both (open), so that spend, income, balance and suppliers are calculated, not typed.
- BR-15.5Modelled figures are always labelled as modelled, show their assumptions, and are never mixed with actual figures.
- BR-15.6Levels, scores, statuses and ticks are always set by a named person. Claude may propose them.
- BR-15.7Risks can be raised automatically by rules on the company's own figures, as well as entered or proposed.
- BR-15.8Investors see CEO development.

### Business rules

- Claude never produces a figure, score, level or status shown as fact.
- Payroll appears as one total. Pay per person is never stored or shown.
- An income payment that could be revenue, investment or a loan is asked about, never guessed.
- Nothing reaches investors before the company's approval setting is met (BR-6.3).

### Success measures

- Fed the raw files behind a hand-built reference dashboard, BoardRoom fills every calculated block with the exact figure, checked against a hand-worked answer.
- No drafted block reaches investors with a figure that fails the number check.
- A company with a finance export, a deals export and bank transactions sees Cashflow and Pipeline complete without typing anything except answers to questions.
