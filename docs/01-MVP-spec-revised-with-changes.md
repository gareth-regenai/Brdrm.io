# BoardRoom.io MVP Spec: changes

Revised 18 October 2026. Build only. Pricing and commercials are out of scope.

**Red** new or changed ~~Struck red~~ removed from the previous version Plain text, unchanged [Why] the logic behind the change

## The logic change in one place

1.  **From rules to AI.** The previous version boxed the AI into two narrow jobs behind strict templates and rejections. BoardRoom is AI-native: the AI reads whatever the company has, and rules exist only where a figure must be exact.
2.  **The AI picks the rows, code runs fixed formulas.** Fixed formulas on fixed columns break on real data, and formulas that change per company break comparison. The AI picks which rows feed each standard formula, code does the maths, and the AI never gives a number from its head.
3.  **From locked cycles to dated updates.** No Draft, Review, Approved, Published states, no lock, no versions. An update is a dated line, "true as of \[date\], subject to change", and can be edited, showing a "Last edited" date.
4.  **From per-pack grants to standing access.** The CEO invites an investor once. Investors get a portfolio overview across every company they back, in the MVP, and only view and comment.
5.  **From forms to a setup chat.** No plan file and no settings forms. The AI makes most setup assumptions itself, confirms them, and asks only what it cannot find.
6.  **Nothing can be out.** Commentary figures must be normal rounding of the real figure, the exact figure is one click away, and display precision scales with the company's revenue.

## Summary and scope

[Changed]

The MVP lets a company ~~upload one CSV per department, turns them into a validated and calculated board pack, and shares each approved cycle with investors through a read-only view.~~ **drop in whatever financial, sales, delivery and people files it already has. The AI works out what is in them, code calculates the figures, and the company's investors see them as tiles they can trace to the source.** It is built as Python microservices on Render, with ~~two Claude skills~~ **the AI** doing the work that needs judgement.

- **Who it serves:** company teams (the CEO and department leads) and ~~their investors~~ **the investors who back them. One investor can back many companies and sees them as one portfolio.** M&A deal teams ship after the MVP.
- **The core promise:** ~~upload, validate, map if the file is off-spec, calculate, draft the pack, CEO approves, investors view.~~ **upload anything, see figures, and investors see them too. Little to set up and nothing to prepare.**
- ~~**Claude skill 1, mapping:** when a CSV does not match the template, the skill proposes a column mapping that a person confirms before anything is used.~~  
  **AI intake: the AI reads every file, works out what each column is, ignores what it does not need and never stores pay data. A person is asked one plain question only when a figure cannot be worked out without it.**
- **AI calculations: each tile has a fixed formula. The AI decides which of the company's rows feed it, and code runs it, so the arithmetic is exact and every company's figures compare.**
- **AI commentary:** writes the commentary from the calculated figures, and a check rejects any figure that does not match.
- **Stack:** Python (FastAPI), Postgres, a Render Key Value queue, S3-compatible storage, the Frankfurt region and a React single-page app. Unchanged.

### Proposed success criteria

- A company goes from first upload to ~~an approved, shareable pack~~ **its investors seeing figures** in under 30 minutes.
- Most ~~off-spec CSVs map correctly with at most a few corrections~~ **real files are understood with no correction**, measured on a labelled sample.
- Automated tests show no cross-tenant data access.
- Every figure traces back to ~~an uploaded row~~ **its source, either an uploaded row or a named person who entered it**.

****MVP phases:** phase 1 is the MVP: finance and sales pipeline files, targets from the setup chat, and reporting in one currency. That covers six of the eight overview measures. Phase 2 follows straight after launch: product delivery, people and currency conversion.**

**Out of scope:** live integrations **(the first connector, such as Xero, is a candidate to pull forward)**, M&A deal rooms, benchmarking, SSO, custom pack designs beyond a logo and colours, and a mobile app.

**Why**This is a low-friction product for small companies that have almost nothing to give us. Every template, required column and confirmation step in the previous version was work pushed onto the customer that the AI can do.

## Users, tenants and roles

[Changed]

| Tenant type | Who it is                                                                                                                   | MVP status                                                                                                                                   |
|-------------|-----------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------|
| Company     | A business that ~~uploads department data and publishes board packs~~ **adds its data and shares it with its investors** | Ships                                                                                                                                        |
| Investor    | An angel, syndicate lead, fund or solo capitalist **who backs one or more companies**                                    | ~~Read-only viewing ships; portfolio dashboards and sponsor billing come later~~ **Ships: portfolio overview, company view and comments** |
| Deal team   | An M&A team running packs across target or acquired businesses                                                              | Reserved in the model; ships after the MVP                                                                                                   |

| Role                                | Scope                                                                            | Can do                                                                                                                                                          |
|-------------------------------------|----------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Owner                               | Company                                                                          | Everything, including ~~billing and~~ deleting the workspace                                                                                                    |
| ~~CEO approver~~ **CEO**         | Company                                                                          | ~~Approve and publish cycles, invite investors, set the plan targets~~ **Upload, edit and approve updates, invite investors, set targets**                   |
| Department lead                     | One or more departments                                                          | Upload ~~and map their department's CSVs~~ **their department's files** and edit their section~~, submit for approval~~                                      |
| Contributor                         | One department                                                                   | Upload files and comment~~, but not submit~~                                                                                                                    |
| ~~Investor viewer~~ **Investor** | ~~Company packs they are invited to~~ **Every company that has invited them** | ~~View published packs and the lineage of each figure, and comment~~ **See the portfolio overview, open each company's updates, trace a figure and comment** |
| Platform admin                      | BoardRoom.io staff                                                               | Support access, time-limited, logged and visible to the customer                                                                                                |

- ~~Investor access is always per company and per pack, never account-wide.~~
- **The CEO invites each investor once. That invite is their standing access, and every update reaches them. No per-update grants, no hold-backs, no cap table in the platform.**
- **An investor sees every company that has invited them as one portfolio. Co-investors in the same company can see each other. Nothing crosses between companies.**
- **A company team sees its own company only. Investors view and comment only; they approve nothing.**
- **Who can approve an update is a permission set per company. The default is the CEO.**
- A user can belong to several tenants, and the active tenant is part of every request.

**Why**Investors are on the cap table and CEOs are open with them. Ticking every investor on every pack means one forgotten tick leaves an investor with nothing, and they chase by email, which is the problem this product exists to remove. An investor backing several companies needs one login across all of them.

## How it works

[Rewritten]

~~A company's data moves from upload to an investor's screen in nine steps and two checks. Code does the parsing, the mapping and every calculation, Claude makes two suggestions, and a person approves each one before anything is published.~~

1.  **Set up: a short AI chat confirms what the AI assumed about the company and asks only what it cannot find. It can be skipped.**
2.  **Add files: the CEO or a department lead drops in any file, such as a finance export, a pipeline report, a budget or a team list.**
3.  **Understand: the AI works out what each column is and ignores the rest. Pay data is dropped and never stored.**
4.  **Calculate: for each tile the AI picks the rows that feed its fixed formula, and code runs it. Each figure keeps its source.**
5.  **Describe: the AI drafts commentary from the figures.** A failed number check gets one automatic retry, then a person writes the section.
6.  **Share: the update goes to investors as a dated line, "CEO X added new financials, true as of \[date\], subject to change." Investors view and comment.**

**Why**A person approving every AI suggestion turns the AI into a form the customer has to check. People are asked only when the AI is stuck, and the company stays in charge of what goes out.

## Files and intake

[Was "Data model"]

The ~~MVP defines five CSV templates~~ **five departments stay as the guide to what helps. They are guidance, not a gate: no file is rejected for not matching a template.** ~~Files are UTF-8 with a header row, ISO dates (YYYY-MM-DD) and one currency per file.~~

| Department       | One row per       | ~~Required / optional columns~~ **Columns that help**                                                                                              |
|------------------|-------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------|
| Finance          | Month             | period, revenue, cost of sales, operating expenses, cash balance. Also payroll total, capex, debt, ARR, deferred revenue, currency                    |
| Sales pipeline   | Deal              | deal id, account, stage, amount, status, created date. Also expected close, closed date, probability, source, owner, last activity                    |
| Product delivery | Work item         | item id, title, status, ~~points~~ **due date, completed date, planned period. The measure is tasks completed against tasks planned**              |
| People           | Role              | department, role title, status, start date. Also end date, requisition opened date, location                                                          |
| Plan             | Metric and period | ~~metric_key, period, target_value, uploaded as a file~~ **Targets from the setup chat, or from any budget or forecast the AI finds in an upload** |

- ~~Columns that look like salary, bonus, bank details, national insurance numbers or dates of birth are rejected at upload and are not stored.~~  
  **Those columns are dropped on upload, never stored and never sent to the AI. The file is still accepted.**
- **Any file: the AI works out what each column is, whatever tool it came from, and asks one plain question only when a figure cannot be calculated without it.**
- **Currency (phase 2): any currency, per row, converted to the company's reporting currency with a published rate for the period. The click view shows the original amount, the rate and its source, and the company can override a rate. Money is never added across companies. Needs a rates feed.**
- **Hand-entered figures: a person can type in a figure or forecast, labelled "Entered by \[name\], \[date\]". It has no file source and is not checked against data.**
- **No plan means no "against plan" figure. The tile reads "No plan set" and nothing is blocked.**
- If the AI is unavailable, the manual mapping screen takes over.
- **What the AI understood and ignored is logged for our dev team only. The CEO and investors never see it.**

**Why**Real exports never match a template, and rejecting a file makes the CEO fix it by hand. Pay is still never stored, so the privacy promise holds; only the friction goes. Most small teams do not use points but do have tasks. Many start-ups invoice in more than one currency.

## Figures and metrics

[Changed]

Each metric is a versioned formula in a registry, so every figure shows which formula version produced it. **The formulas below are fixed, so every company's figures mean the same thing. The AI chooses which of the company's rows feed each formula, and code runs it. A company-specific method is allowed only where the standard formula cannot work, and it is flagged on the figure.**

| Metric                                      | Default definition                                                                         |
|---------------------------------------------|--------------------------------------------------------------------------------------------|
| Revenue and growth                          | Revenue for the period and month-on-month change                                           |
| Gross margin                                | (revenue − cost of sales) ÷ revenue                                                        |
| Net burn                                    | cost of sales + operating expenses − revenue                                               |
| Runway                                      | Latest cash balance ÷ average net burn of the last three months, or "cash-generative"      |
| Pipeline, coverage, win rate, stalled deals | As before                                                                                  |
| Delivery vs plan                            | ~~Completed points ÷ planned points~~ **Tasks completed ÷ tasks planned** in the period |
| Slippage, headcount, open roles, attrition  | As before                                                                                  |
| Variance vs plan                            | Actual minus target, for any metric ~~that has a plan row~~ **with a target**           |

**The number check:** a figure in commentary must match a computed metric ~~within the rounding rules~~ **as normal rounding at the precision written. No tolerance band: £1.4m passes for £1.378m, £1.5m fails. Dates, quarters and counts are ignored.**

**Click view: clicking a figure opens its exact value, its source (rows, formula and check, or who entered it), what it moves (cash moves runway) and its risk level. On each tile the source sits behind a small, minimised "Source" line.**

**Display precision, set by annual revenue and adjustable in settings:**

| Annual revenue                     | Money shown as                               | Example |
|------------------------------------|----------------------------------------------|---------|
| Under £100k, including pre-revenue | Whole pounds                                 | £4,210  |
| £100k to £1m                       | £k, 1 decimal                                | £78.1k  |
| £1m to £10m                        | £m, 3 decimals over £1m; £k, 1 decimal below | £1.378m |
| £10m to £100m                      | £m, 2 decimals over £1m; £k whole below      | £13.78m |
| Over £100m                         | £m, 1 decimal                                | £137.8m |

**Months and percentages always show one decimal. Each figure carries High, Medium or Low from warning lines; defaults ship in config (in place of the fixed flags such as runway under 12 months) and each company can change what it sees in settings.**

**Why**For a small company a few thousand pounds is the difference between making payroll or not, and that is what investors look at, so a figure can never be "near enough". Rounding is for reading only, and the exact figure is always one click away. Precision follows company size because £1m is large for an incubator start-up.

## Updates and approvals

[Replaces "Cycles and versions"]

~~A cycle is one reporting period, monthly or quarterly. It moves through Draft, In review, Approved and Published, and a published cycle is immutable. A correction creates a new version with a change note, and investors see the latest published version with its history.~~

- **A company adds data whenever it has it, and each addition is an update: "CEO Sam Hart added new financials. Data true as of 17 Oct 2026. Subject to change and may be edited."**
- **An update can be edited after it goes out. No version process and no per-item marks, but a changed update shows "Last edited \[date\]" so investors can see a figure moved.**
- **Any approval happens on the company side. Who approves is a permission per company, default the CEO.**
- **Commentary speaks as the company ("we") by default, with a setting for third person.** Labels such as "Drafted by Claude" stay.
- **Investors comment on an update and the company replies in the same thread.**
- Every figure stores its lineage, so any number can be traced to its source.

**Why**Locking a pack and versioning a typo is process for its own sake. CEOs are transparent with their investors, and a dated line marked "subject to change" is honest and simple. Founders write to investors as "we".

## Investor portfolio overview

[New in MVP]

**On login an investor sees one card per company, highest risk first: a top-level overview with the same eight measures and the same High, Medium and Low lines for every company. The CEO never sees it. Clicking a company opens its own section. Until phase 2, delivery and headcount show "Coming in phase 2".**

| \#  | Measure                | From                 |
|-----|------------------------|----------------------|
| 1   | Cash balance           | Finance              |
| 2   | Runway (months)        | Finance              |
| 3   | Net monthly burn       | Finance              |
| 4   | Revenue against plan   | Finance, Plan        |
| 5   | Pipeline coverage      | Sales pipeline, Plan |
| 6   | Delivery against plan  | Product delivery     |
| 7   | Headcount against plan | People               |
| 8   | Last update (days ago) | Update record        |

**Why**This was Phase 3 in the previous roadmap. An investor logging in should see the whole portfolio and who needs attention first. The same measures and lines across companies make them comparable; the detail lives in each company's section.

## Setup chat

[New]

- **The AI infers currency from the files, what the business does from its website and data, revenue lines from the revenue rows, targets from any budget, and display scale from revenue.**
- **It states its assumptions and lets the CEO correct them, then asks only what it cannot find, usually targets and which investors to invite.**
- **It can be skipped and repeated ("update my targets"). Assumptions cover setup only, never the figures.**

**Why**A plan file and settings forms are work the customer should not have to do. The AI should make about 80% of the assumptions itself.

## Tiers and limits

[Parked]

~~Growth (£59) and Scale (£129) tiers with limits on users, investor viewers, uploads, AI assists and history; single approver on Growth and multi-step on Scale; the AI cost estimate.~~

**Pricing, tiers and limits are parked for a separate commercial review. Keep entitlements as named keys checked at the point of use, and Stripe as the billing route. Whether a limit warns or blocks is an open decision.**

**Why**Commercials are reviewed separately. Approval is a permission, not something tied to a price tier.

## Architecture and services

[Changed]

The shape stays: the browser talks only to the gateway, everything else is private, workers pull from the queue, files upload with signed links. **Whether to start with separate services or one app plus a worker is an open decision.**

| Service                          | Change                                                                                           |
|----------------------------------|--------------------------------------------------------------------------------------------------|
| api-gateway, billing, notify     | Unchanged in shape                                                                               |
| identity                         | **Standing investor invites per company; permissions hold who can approve**                   |
| intake                           | **Accepts any file, drops pay columns, converts currency**                                    |
| ~~mapping~~ **understanding** | **The AI reads every file, not only off-spec ones; manual mapping is the fallback**           |
| metrics                          | **Stores the AI's row selections for fixed formulas; adds display precision and risk levels** |
| insights                         | **Number check uses normal rounding; voice setting**                                          |
| ~~pack~~ **updates**          | **Updates, comments, approvals, PDF export, investor overview. Replaces cycles and versions** |
| **setup**                     | **New: the setup chat**                                                                       |

- **Skill 1, file understanding** ~~(runs only when validation fails; a person confirms the proposal in the web app)~~ **runs on every upload. A low-confidence column that blocks a figure becomes one plain question.** Deterministic Python applies the result and confirmed layouts are saved.
- ****Skill 2, row selection (new):** picks which rows feed each tile's fixed formula, using a closed set of filters. A custom method is allowed only where the standard one cannot work, and it is flagged.**
- **Skill 3, board commentary** **(was skill 2)**: sees computed figures, targets and ~~rule-based flags~~ **risk levels**, never raw rows or employee data.

**Why**The services follow the logic changes: the pack becomes updates, mapping becomes understanding on every file, and a setup service carries the chat. The AI does more, so fewer human confirmation screens are built.

## Security and data protection

[Small changes]

| Area                                                           | Control                                                                                                                            |
|----------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------|
| Tenant isolation, file handling, secrets, backup, supply chain | Unchanged                                                                                                                          |
| Authentication and roles                                       | Short-lived JWTs, one shared role check, investor access ~~per company and per pack~~ **per company, standing from one invite** |
| Sensitive columns                                              | Dropped at intake, never stored or sent to the AI. **The rest of the file is kept.**                                            |
| AI data handling                                               | Headers, redacted samples and aggregates only. **Row selections use a closed set of filters, so no AI-written code is run.**    |
| Audit                                                          | Logins, uploads, ~~mappings, approvals, publishes~~ **approvals, edits to updates** and every investor view                     |
| Privacy and compliance                                         | As before. **Data roles and retention to be confirmed with a solicitor.**                                                       |

**Why**Keeping the AI to row selection means no AI-written code runs. The audit follows the new update model.

## Infrastructure on Render

[Unchanged]

Frankfurt region, private services, Key Value queue, one Postgres instance, S3-compatible storage in the UK or EU, Blueprint environments, Hobby then Pro. **The Blueprint and starting cost follow whatever service count is chosen.**

## Build plan and testing plan

[Reordered]

**Build the AI intake first, keep the app thin, and demo working software at the end of every step. Before any rule, rejection or required field is built, it answers one question: why can't the AI handle this?** The test layers are unchanged.

| Step           | Was                                            | Now                                                                                   |
|----------------|------------------------------------------------|---------------------------------------------------------------------------------------|
| M0             | Foundations                                    | Foundations                                                                           |
| M1             | Identity and tenancy                           | Identity and tenancy **with standing investor invites**                            |
| M2             | ~~Intake: five templates, validation reports~~ | **AI intake: finance and pipeline files, skill 1, pay drop, fallback**             |
| M3             | Metrics engine                                 | **Calculations: skill 2 row selection,** lineage**, precision, risk levels**    |
| M4             | ~~Mapping skill~~                              | **Setup chat**                                                                     |
| M5             | ~~Pack service: cycles, versions, grants~~     | **Updates and comments**                                                           |
| M6             | Analytics skill                                | Commentary **with the rounding check and voice setting**                           |
| M7             | Billing and tiers                              | **Investor portfolio overview**                                                    |
| M8             | Web app                                        | **Billing (entitlements only)**                                                    |
| M9             | Hardening and beta                             | Web app, built alongside                                                              |
| M10            |                                                | Hardening and beta                                                                    |
| **Phase 2** |                                                | **Delivery and people files, currency conversion, the last two overview measures** |

**Six journeys:** **Set up through the chat. Upload a clean file and see tiles. Upload a messy file and see tiles with at most one question.** Draft commentary that passes the check. **Send an update and edit it. Log in as an investor, see the portfolio, open a company,** trace a figure **and comment**.

**Why**The AI intake is the product, so it is built and shown first. A demo at every step catches any drift back to rigid rules in weeks, not months.

## Risks and open decisions

[Changed]

### Open decisions

| Decision                                                                   | Status                                  |
|----------------------------------------------------------------------------|-----------------------------------------|
| Who builds it, and how many engineers                                      | Settle first                            |
| **Service count**                                                       | **To propose; keep the app thin**    |
| **First connector (for example Xero)**                                  | **To decide**                        |
| **Limits warn or block**                                                | **To decide**                        |
| **Named check on cash, burn and runway**                                | **To decide**                        |
| **Warning-line defaults**                                               | **To propose and agree**             |
| **Allowed row filters for skill 2; rates feed**                         | **To propose**                       |
| Authentication, front end, storage, job framework, PDF, AI data path, name | As before                               |
| ~~Currency: GBP only and one currency per file~~                           | **Decided: any currency, converted** |
| ~~Prices: validate before building billing~~                               | **Parked with commercials**          |

### Risks

| Risk                                                      | Mitigation                                                                                                                                         |
|-----------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------|
| **The build drifts back to rigid rules and templates** | **The test for every gate, AI intake first, a demo at every step**                                                                              |
| **The AI misreads a column or picks the wrong rows**   | **Closed transforms, fixed formulas with closed row filters, the method shown in the click view, the number check, evals that block a release** |
| Too many services slow a small team                       | **Start thin,** shared template, review after M5                                                                                                |
| The product is easy to copy                               | Compete on ~~lineage, the approval workflow and investor access~~ **traceable figures, near-zero setup and the investor portfolio view**        |
| ~~Costs creep beyond the \$192 base~~                     | ~~Entitlement limits on AI use~~ **Parked with commercials**                                                                                    |
| Isolation bugs, hostile cells, data retention, one region | As before                                                                                                                                          |
