# BoardRoom.io FRD

Functional requirements for the MVP, one chapter per section of the revised spec. 18 October 2026.

FR-4.3 requirementBR-4.1 business requirement it serves[Phase 2] off behind a flag in phase 1[Open] depends on an open decision

## How to use this document

Each requirement names the business requirement it serves and has an acceptance line. A requirement is done when its acceptance line is proven by a test in CI. Phase 2 requirements stay switched off behind a feature flag in phase 1. Open decisions are listed in chapter 14.

### Proposed epics

| Epic                               | Covers                    | Phase |
|------------------------------------|---------------------------|-------|
| E1 Foundations and tenancy         | Chapters 2, 10, 11, 12    | 1     |
| E2 AI file intake                  | Chapter 4                 | 1     |
| E3 Figures engine                  | Chapter 5                 | 1     |
| E4 Setup chat                      | Chapter 8                 | 1     |
| E5 Updates, approvals and comments | Chapters 3, 6             | 1     |
| E6 Commentary and number check     | FR-5.5, FR-10.3 (skill 3) | 1     |
| E7 Investor portfolio overview     | Chapter 7                 | 1     |
| E8 Billing entitlements            | Chapter 9                 | 1     |
| E9 Web app and critical journeys   | Chapters 3, 13            | 1     |
| E10 Hardening and beta             | Chapters 11, 12, 13       | 1     |
| E11 Delivery, people and currency  | Chapters 4, 5, 7          | 2     |

## 1. Summary and scope

[Phase 1 and 2]

- FR-1.1BR-1.4Every figure is produced by deterministic code from stored data. AI output is never stored or shown as a figure.**Accept:** a test confirms no figure value is written from any AI response.
- FR-1.2BR-1.2Every figure stores its lineage: formula version, dataset version, the rows used, or the person and date for a hand-entered figure.**Accept:** every figure in a test update resolves to rows or a named person.
- FR-1.3BR-1.5Product delivery, people and currency conversion sit behind feature flags, off in phase 1.**Accept:** with flags off, none of those features is reachable in the app or API.
- FR-1.4BR-1.1A company can go from sign-up to an update its investors can see without filling any template.**Accept:** the end-to-end journey passes using only a raw finance export and a raw pipeline export.

**Not built in the MVP:** live integrations, M&A deal rooms, benchmarking, SSO, custom designs beyond logo and colours, mobile app.

## 2. Users, tenants and roles

[Phase 1]

- FR-2.1BR-2.1A user can create a company workspace and becomes its Owner.**Accept:** sign-up creates one company tenant with that user as Owner.
- FR-2.2BR-2.1The Owner or CEO can invite users by email with a role: CEO, Department lead (scoped to one or more departments) or Contributor.**Accept:** an invited user who signs up has only that role's permissions in that company.
- FR-2.3BR-2.2, BR-2.3The CEO can invite an investor by email. On acceptance the investor gains standing access to every update the company has shared and will share.**Accept:** an update shared after the invite appears for the investor with no further action.
- FR-2.4BR-2.2One investor login holds memberships in many companies.**Accept:** an investor invited by three companies sees all three after one login.
- FR-2.5BR-2.4Within a company, an investor can see the names of the other investors in it.**Accept:** investor A in company X sees investor B in X, and no investors of companies A does not back.
- FR-2.6BR-2.5The active tenant is part of every request, and data from one company never appears in another's responses.**Accept:** two-tenant tests on every endpoint return no cross-company data.
- FR-2.7BR-2.1Who can approve an update is a per-company permission, defaulting to the CEO.**Accept:** changing the permission changes who sees the approve action.
- FR-2.8BR-2.3[Open] The CEO can remove an investor, which stops access immediately. What a removed investor keeps of past updates is open.**Accept:** removal blocks the investor's next request.
- FR-2.9The tenant type list includes a reserved deal-team value with no screens or flows.**Accept:** the value exists in the schema and no route uses it.

### Permissions

| Action                 | Owner | CEO         | Department lead | Contributor    | Investor |
|------------------------|-------|-------------|-----------------|----------------|----------|
| Upload files           | Yes   | Yes         | Own departments | Own department | No       |
| Edit an update         | Yes   | Yes         | Own sections    | No             | No       |
| Approve an update      | Yes   | Default yes | If granted      | No             | No       |
| Invite users           | Yes   | Yes         | No              | No             | No       |
| Invite investors       | Yes   | Yes         | No              | No             | No       |
| Comment                | Yes   | Yes         | Yes             | Yes            | Yes      |
| See portfolio overview | No    | No          | No              | No             | Yes      |
| Delete workspace       | Yes   | No          | No              | No             | No       |

## 3. How it works

[Phase 1]

- FR-3.1BR-3.1An upload moves through these states, shown to company users: received, understanding, calculating, describing, ready, shared.**Accept:** each state change is visible in the app and recorded as an event.
- FR-3.2BR-3.2When the AI cannot work out a figure, the company sees one plain question in the app and by email. The upload waits at understanding until it is answered.**Accept:** a test file with an ambiguous cash column produces exactly one question, and answering it completes the upload.
- FR-3.3BR-3.3An update is visible to investors only once the company's approval setting is met.**Accept:** with approval required, an investor cannot see the update until an approver acts.
- FR-3.4BR-3.4A shared update shows the line "\[Role\] \[Name\] added new \[department\]. Data true as of \[date\]. Subject to change and may be edited."**Accept:** the line renders with the uploader's role and name and the data-as-of date.

## 4. Files and intake

[Phase 1 and 2]

- FR-4.1BR-4.1[Open] The upload accepts CSV and Excel files up to the entitlement size limit, straight to private storage with a short-lived signed link. Other formats such as PDF are open.**Accept:** CSV and XLSX exports from at least three different tools upload successfully.
- FR-4.2BR-4.1A deterministic profiler records each column's name, inferred type, null rate, distinct count and value range.**Accept:** profile output matches a hand-checked fixture set.
- FR-4.3BR-4.1, BR-4.2Skill 1 receives the department guidance, the profile and 10 to 20 redacted sample rows, never the whole file. It returns, per column, a field from the closed department field list or "ignore", one transform from a closed list (rename, parse date, scale, flip sign, split, combine, map values), a confidence from 0 to 1 and a short reason.**Accept:** responses outside the schema are rejected, and the payload snapshot contains no full file.
- FR-4.4BR-4.3Columns matching pay, bank, national insurance, date-of-birth or personal-email patterns, by header or content, are dropped before storage and before any AI call. The rest of the file is processed.**Accept:** fixtures with these columns leave no trace in storage or AI payloads.
- FR-4.5BR-4.1Deterministic code applies the confirmed interpretation. The AI never edits data.**Accept:** the same file and interpretation always produce the same dataset.
- FR-4.6BR-3.2If a column below 0.8 confidence blocks a figure, the user gets one plain question. The answer is saved to the layout.**Accept:** see FR-3.2.
- FR-4.7BR-4.1A confirmed layout is saved against the file's header fingerprint and reused instantly next time.**Accept:** a second upload with the same headers asks nothing.
- FR-4.8BR-4.4A company user can enter a figure or forecast by hand. It is labelled "Entered by \[name\], \[date\]", has no file source and is excluded from data checks.**Accept:** the click view shows the name and date and no file.
- FR-4.9BR-4.7If the AI is unavailable or the user prefers, a manual mapping screen lets them assign columns.**Accept:** with the AI switched off, a file still produces figures.
- FR-4.10BR-4.8Each upload writes an internal log of interpretations, ignored columns and confidence, visible only to platform admins.**Accept:** no company or investor endpoint returns the log.
- FR-4.11BR-4.5Targets come from the setup chat, from any budget or forecast the AI finds, or from settings. With no target, "against plan" tiles read "No plan set".**Accept:** a company with no targets sees the label and no error.
- FR-4.12In phase 1, the AI identifies product delivery and people files but their measures stay off until phase 2.**Accept:** such a file uploads without error and shows no tiles.
- FR-4.13BR-4.6[Phase 2] Each row may carry its own currency. Amounts are converted to the reporting currency using a published rate for the period. The click view shows the original amount, the rate and its source, and the company can override a rate.**Accept:** a mixed GBP and USD file converts correctly against fixed test rates.

## 5. Figures and metrics

[Phase 1 and 2]

- FR-5.1BR-5.1A versioned metric registry holds a fixed formula per measure, as in the table below.**Accept:** every figure records the formula version that produced it.

| Metric                           | Formula                                                                                                           | Phase |
|----------------------------------|-------------------------------------------------------------------------------------------------------------------|-------|
| Revenue and growth               | Revenue for the period and month-on-month change                                                                  | 1     |
| Gross margin                     | (revenue − cost of sales) ÷ revenue                                                                               | 1     |
| Net burn                         | cost of sales + operating expenses − revenue                                                                      | 1     |
| Runway                           | Latest cash balance ÷ average net burn of the last three months, or "cash-generative" if burn is zero or negative | 1     |
| Pipeline and weighted pipeline   | Sum of open deal amounts, and amount × probability                                                                | 1     |
| Coverage                         | Open pipeline expected to close in the period ÷ (target − closed-won so far)                                      | 1     |
| Win rate and average deal size   | won ÷ (won + lost), and won amount ÷ won count                                                                    | 1     |
| Stalled deals                    | Open deals with no activity for more than N days (default 30)                                                     | 1     |
| Delivery vs plan                 | Tasks completed ÷ tasks planned in the period                                                                     | 2     |
| Slippage                         | Average days between due and completed dates, and count past due                                                  | 2     |
| Headcount, open roles, attrition | Active at period end, open requisitions, leavers ÷ average headcount                                              | 2     |
| Variance vs plan                 | Actual minus target, and as a percentage                                                                          | 1     |

- FR-5.2BR-5.2[Open] Skill 2 returns, for each formula input, a row selection built only from a closed set of filters. Code validates and runs it. The exact filter set is open.**Accept:** a selection using anything outside the set is rejected.
- FR-5.3BR-5.2A company-specific method is allowed only when the standard formula cannot work. It is flagged on the figure and in the click view.**Accept:** no custom method exists without its flag.
- FR-5.4BR-5.3Clicking a figure shows its exact value, its source (rows, formula version and check, or the person and date), what it moves (for example cash moves runway) and its risk level.**Accept:** the click view shows all four for every figure type.
- FR-5.5BR-5.4The number check extracts every figure from commentary, ignores dates, quarters and counts of things, and passes a figure only if it equals the real value rounded to the precision written, with units (£, k, m, %, x, months). A failure triggers one regeneration with the differences listed. A second failure marks the section for a person to write.**Accept:** £1.4m passes for £1.378m, £1.5m fails, and "12 December" is ignored.
- FR-5.6BR-5.5Money displays at the precision set by annual revenue (BRD chapter 5). A company can move any metric up or down a band. Months and percentages always show one decimal.**Accept:** fixtures in each band render as specified.
- FR-5.7BR-5.6[Open] Each metric has High, Medium and Low thresholds held in config with defaults. A company can change which metrics it sees and their thresholds for its own pages. The default numbers are open.**Accept:** changing a company threshold changes its own tiles but not the investor overview.

## 6. Updates and approvals

[Phase 1]

- FR-6.1BR-6.1Each upload that completes creates an update recording who added it, the department, the data-as-of date and the created time.**Accept:** the update shows the dated line in FR-3.4.
- FR-6.2BR-6.2Users with edit permission can edit an update after it is shared. A changed update shows "Last edited \[date\]" to investors, and the audit log keeps who changed what, before and after.**Accept:** editing a figure shows the new date to the investor and writes an audit entry.
- FR-6.3BR-6.3Approval follows the company's permission setting, defaulting to the CEO.**Accept:** see FR-3.3.
- FR-6.4BR-6.4A company setting switches commentary between "we" (default) and third person. Labels show who did what: "Drafted by Claude", "Edited by \[name\]", "Approved by \[name\]".**Accept:** switching the setting changes the next draft's voice, and labels always show.
- FR-6.5BR-6.5Each update has a comment thread. Investors and company users can comment, and new comments notify the other side.**Accept:** an investor comment notifies the CEO and the reply notifies the investor.
- FR-6.6An update can be exported as a PDF with the company's logo and colours.**Accept:** the PDF matches a snapshot and neutralises formula injection.
- FR-6.7BR-6.6Lineage is kept for every figure in every update.**Accept:** see FR-1.2.

## 7. Investor portfolio overview

[Phase 1 and 2]

- FR-7.1BR-7.1After login an investor lands on the overview, listing one card per company they back.**Accept:** an investor in three companies sees three cards.
- FR-7.2BR-7.2Each card shows the eight measures in that company's reporting currency and display precision, each with High, Medium or Low from the common overview thresholds.**Accept:** two companies with the same runway get the same level.
- FR-7.3BR-7.1[Open] Cards sort highest risk first. Proposed rule: most High measures first, then most Medium, then shortest runway.**Accept:** a test portfolio sorts in that order.
- FR-7.4BR-7.4Clicking a card opens that company's own section: updates, tiles, click view and comments.**Accept:** the investor reaches the company's latest update in one click.
- FR-7.5BR-7.5In phase 1, delivery and headcount show "Coming in phase 2".**Accept:** with phase 2 flags off, both measures show the label.
- FR-7.6"Last update" shows days since the company's latest shared update.**Accept:** the value matches the latest update date.
- FR-7.7BR-7.3Company roles cannot reach the overview.**Accept:** the overview endpoint refuses company users.
- FR-7.8Money is never totalled across companies, and there are no filters beyond sorting.**Accept:** no total appears anywhere on the overview.

## 8. Setup chat

[Phase 1]

- FR-8.1BR-8.1After sign-up and the first upload, the setup chat infers reporting currency, what the business does (from its website and data), revenue lines, targets from any budget or forecast, and the display band from revenue.**Accept:** with a sample finance file and website, the chat proposes all five without asking.
- FR-8.2BR-8.2The chat shows its assumptions in one message, and the CEO can correct any of them in plain words.**Accept:** "we report in euros" changes the currency setting.
- FR-8.3BR-8.3The chat asks only what it cannot find, usually targets and investor emails to invite.**Accept:** a company with a budget in its upload is asked about investors only.
- FR-8.4BR-8.4The chat can be skipped and reopened later, for example with "update my targets".**Accept:** skipping leaves defaults in place, and reopening changes targets.
- FR-8.5BR-8.5The chat writes only to settings, through structured outputs, and never writes figures.**Accept:** no figure value changes because of a chat message.

## 9. Tiers and limits

[Parked]

- FR-9.1BR-9.1Entitlements are named keys (for example viewers, uploads_per_month, max_file_mb), checked by each service at the point of use.**Accept:** changing a key's value changes behaviour with no deploy.
- FR-9.2BR-9.2Stripe Checkout and the customer portal handle payment, with idempotent webhooks.**Accept:** replayed webhooks change nothing.
- FR-9.3BR-9.3No approval behaviour depends on the tier.**Accept:** approval works the same on every tier.
- FR-9.4[Open] Limit behaviour is configurable as warn or block. Which one is open.**Accept:** both settings work in a test.

## 10. Architecture and services

[Phase 1]

- FR-10.1BR-10.1The web app talks only to the gateway. All other components are on the private network.**Accept:** no internal component has a public address.
- FR-10.2BR-10.2[Open] The code is split into modules, deployable as separate services or as one app plus a worker: gateway, identity, billing, intake, understanding, metrics, insights, updates, setup, notify. The service count is open.**Accept:** no module reads another module's tables.
- FR-10.3BR-10.2Three AI skills, each with a closed output schema: skill 1 file understanding (FR-4.3), skill 2 row selection (FR-5.2), skill 3 board commentary. Skill 3 sees computed figures for the period, the previous period, targets and risk levels, never raw rows or employee data, and returns a headline, a note per department and likely board questions.**Accept:** schema tests reject any other output shape.
- FR-10.4BR-10.3The setup chat runs on the Messages API with structured outputs that write to company settings.**Accept:** see FR-8.5.
- FR-10.5BR-10.4Skills are called with pinned versions. A per-tenant switch routes all AI work through the Messages-API-only path with no code execution.**Accept:** with the switch on, no request uses the code execution tool.
- FR-10.6BR-10.5If the AI is unavailable, intake falls back to manual mapping and the pipeline continues.**Accept:** see FR-4.9.
- FR-10.7Events go through an outbox per module and are delivered at least once to idempotent consumers.**Accept:** duplicate events cause no double processing.

## 11. Security and data protection

[Phase 1]

- FR-11.1BR-11.1Every table has a tenant ID and a Postgres row-level security policy, with the tenant set per connection and a database role per module.**Accept:** a CI check fails if any table lacks a policy.
- FR-11.2BR-11.2Short-lived JWTs are checked at the gateway and in each module, with one shared role check.**Accept:** a role-by-endpoint matrix generated from the API files passes at 100%.
- FR-11.3BR-11.3Sensitive columns are dropped as in FR-4.4.**Accept:** see FR-4.4.
- FR-11.4BR-11.4AI calls carry only headers, redacted samples and aggregates, with cell text passed as data. No AI-written code is run.**Accept:** payload snapshot and injection-cell tests pass.
- FR-11.5BR-11.5An append-only audit log records logins, uploads, approvals, edits to updates and every investor view.**Accept:** every state change emits an audit event.
- FR-11.6BR-11.6Staff support access is time-limited, logged and shown to the customer.**Accept:** a support session appears in the customer's audit view and expires.
- FR-11.7Files have size and row limits, a malware scan before parsing, parsing in a worker with memory and time limits, and formula injection neutralised on export.**Accept:** the hostile file set (oversized rows, decompression bombs, encoding tricks, cells starting with =, +, - or @) is handled safely.
- FR-11.8Secrets live in environment secret variables, are rotated and are scanned for in CI.**Accept:** the secret-scan gate blocks a seeded secret.

## 12. Infrastructure

[Phase 1]

- FR-12.1BR-12.1All services, the database and the queue run on Render in Frankfurt. File storage is an S3-compatible bucket in the UK or EU, versioned and private.**Accept:** the Blueprint pins every resource to Frankfurt.
- FR-12.2BR-12.2One monorepo Blueprint defines production and staging as isolated environments, with a full-stack preview per pull request that expires.**Accept:** opening a pull request creates a working preview.
- FR-12.3BR-12.3Postgres point-in-time recovery and storage versioning are on, and a restore drill passes before launch.**Accept:** a timed restore to staging succeeds.
- FR-12.4Logs are structured with tenant ID and no data values. Health checks, error tracking and alerts cover queue depth, AI error rate and auth failures.**Accept:** each alert fires in a staged fault test.

## 13. Build plan and testing

[Phase 1 and 2]

- FR-13.1BR-13.3Every pull request runs lint, types, unit and integration tests, contract checks and security scans, then end-to-end tests on its preview.**Accept:** a seeded defect fails each gate.
- FR-13.2BR-13.3AI unit tests use recorded responses, so CI never calls the live API. Scheduled evals call the real model, and a regression blocks a skill release.**Accept:** CI passes with the network to the AI provider blocked.
- FR-13.3BR-1.4Metric formulas are tested against golden datasets with hand-calculated results, including rounding and currency cases.**Accept:** every formula matches its golden result exactly.
- FR-13.4BR-13.4The six critical journeys run as Playwright tests on every preview: set up through the chat; upload a clean file and see tiles; upload a messy file and see tiles with at most one question; draft commentary that passes the number check; send and edit an update; log in as an investor, see the portfolio, open a company, trace a figure and comment.**Accept:** all six pass before merge.
- FR-13.5BR-13.1Build order: M0 foundations, M1 identity, M2 AI intake, M3 figures, M4 setup chat, M5 updates and comments, M6 commentary, M7 investor overview, M8 billing, M9 web app alongside, M10 hardening and beta, then phase 2.**Accept:** each step ends with a demo of working software.

## 14. Open decisions that block requirements

| Decision                                                  | Blocks                 |
|-----------------------------------------------------------|------------------------|
| Who builds it, and how many engineers                     | Timing of every step   |
| Service count: separate services or one app plus a worker | FR-10.2, FR-12.2       |
| File formats beyond CSV and Excel, such as PDF            | FR-4.1                 |
| The closed filter set for row selection                   | FR-5.2                 |
| Default High, Medium and Low thresholds                   | FR-5.7, FR-7.2, FR-7.3 |
| Overview sort rule (proposed in FR-7.3)                   | FR-7.3                 |
| Limits warn or block                                      | FR-9.4                 |
| Named check on cash, burn and runway before sharing       | FR-3.3, FR-6.3         |
| What a removed investor keeps                             | FR-2.8                 |
| Rates feed provider                                       | FR-4.13 (phase 2)      |
| First connector, such as Xero                             | Not yet in scope       |
| Board pack sections: MVP or phase 2                       | FR-15.1 to FR-15.19    |
| Documents as a source, and figures quoted from them       | Product and milestones in docs/06 |
| Scenario assumptions and their defaults                   | FR-15.13               |
| Monthly check-in conversation                             | docs/06 section 8      |
| Where updates live in the board pack                      | FR-15.1                |
| "Test both": bank routes, or payroll per person          | FR-15.6, FR-15.9       |

## 15. Board pack sections

[Phase to be decided, see chapter 14]

Detail for every requirement here is in docs/06-Board-pack-sections.md, which names each block, its type and its source. Evidence is in docs/07-Board-pack-reference-analysis.md.

- FR-15.1BR-15.1One section bar, in the order Overview, Roadmap, Product, Cashflow, Pipeline, Momentum, Risk register, CEO development, is shown to company users and investors alike. Dashboard, Files, Your tools, Team and Settings move to a side menu shown to company users only.**Accept:** an investor and the CEO of the same company see the same bar; the investor's page has no side menu.
- FR-15.2BR-15.1Each section opens on a header with the company, section name, period covered and "data true as of", and a sub-tab bar with the sub-tabs in docs/06 section 4.**Accept:** every sub-tab in docs/06 is reachable in one click from its section.
- FR-15.3BR-15.3Blocks are built from the fifteen types in docs/06 section 3, and each carries its source label: "Drafted by Claude", "Entered by [name], [date]", "Modelled, not a forecast", or the click view for a calculated figure.**Accept:** a test renders one block of each source and finds the right label on each.
- FR-15.4BR-15.5A modelled block shows its assumptions, who entered them and when, and no chart series or tile mixes modelled and actual values.**Accept:** changing an assumption changes the modelled result and the "Entered by" line, and no actual figure moves.
- FR-15.5BR-15.6Levels, scores, statuses and ticks can only be set through a person's action. A value proposed by Claude or a rule shows "Proposed" until a person sets it.**Accept:** no endpoint stores a level, score or status from an AI response; a proposed risk shows "Proposed".
- FR-15.6BR-15.4[Open] Bank transactions are accepted as a file (CSV or Excel export from a bank) and through an accounting connection, through the same intake path as other files (FR-4.1).**Accept:** the same transactions through either route give identical figures.
- FR-15.7BR-15.4Claude chooses each transaction's category from a closed list held in config. Code totals by category, month and supplier.**Accept:** a category outside the list is rejected; the categories eval passes its mark.
- FR-15.8BR-15.2An income line that could be revenue, investment or a loan becomes one question to a company user. The answer is remembered for that counterparty.**Accept:** an ambiguous line asks once; a second payment from the same counterparty asks nothing.
- FR-15.9Payroll shows as one total. Per-person pay is dropped at intake as in FR-4.4.**Accept:** a bank file with named salary payments stores no per-person amount and shows one payroll line.
- FR-15.10A payment and its reversal within 30 days are netted and shown as one line with both dates.**Accept:** a fixture with a payment and a partial reversal shows the net amount and both dates.
- FR-15.11BR-15.4Code finds recurring suppliers and marks those with no charge in two of their cycles as stopped. A company user marks each remaining supplier as kept or cut, and the potential saving is the total of those marked cut.**Accept:** the supplier detection eval passes its mark; the saving equals the sum of suppliers marked cut.
- FR-15.12The Pipeline stages table shows count, value and deal names per stage. Deals before the company's qualifying stage are listed separately and never counted in the qualified total.**Accept:** moving a deal across the qualifying stage moves it between the two lists and changes the total by its value.
- FR-15.13BR-15.5[Open] Scenario modelling applies fixed formulas to rates, prices and volumes entered by the company, with defaults from the company's own data where it has them.**Accept:** the per-deal tables equal a hand-worked spreadsheet for a fixture.
- FR-15.14BR-15.7Risks are entered, raised by rules in config (runway under six months, one customer over 40% of revenue, a deal stalled over 30 days, burn up over 20% month on month), or proposed by Claude. Each has a title, description, mitigation, owner and level.**Accept:** a fixture crossing each rule raises one proposed risk; a person setting its level removes "Proposed".
- FR-15.15BR-15.8CEO development holds the gap map, the 30-day plan and the operating rhythm. Areas, diagnoses, tasks and schedule come from an assessment conversation with Claude; every score is set by the CEO; progress is calculated from ticks.**Accept:** completing the assessment produces areas with no scores until the CEO sets them; ticking a task changes progress.
- FR-15.16Roadmap milestones and timeline items are entered by company users in phase 1, each with a date, track, title, description and status, and come from a project tool in phase 2.**Accept:** an entered milestone appears on its track's sub-tab and in the timeline in its month.
- FR-15.17Momentum endorsements and recognition are entered as story cards; cost savings are calculated from suppliers a person marks as stopped.**Accept:** marking a supplier stopped adds its spend to cost savings.
- FR-15.18Each section's call-outs are drafted by Claude from that section's figures and pass the number check before any person sees them as final.**Accept:** a call-out with a figure that fails the check is regenerated once, then marked for a person to write (FR-5.5).
- FR-15.19BR-15.2No section is called done until its evaluations in docs/06 section 7 pass in CI on recorded answers and the private benchmark has been run.**Accept:** CI runs each section's evaluation and fails below its mark.
