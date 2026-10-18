# BoardRoom.io MVP Spec

2026-10-15 · @Alex cooper

## Summary and scope

The MVP lets a company upload one CSV per department, turns them into a validated and calculated board pack, and shares each approved cycle with investors through a read-only view. It is built as Python microservices on Render, with two Claude skills doing the work that needs judgement.

- **Who it serves:** company teams (the CEO and department leads) and their investors. M&A deal teams are designed in as a third workspace type but ship after the MVP.
- **The core promise:** upload, validate, map if the file is off-spec, calculate, draft the pack, CEO approves, investors view.
- **Claude skill 1, mapping:** when a CSV does not match the template, the skill organises it into the template and proposes a column mapping that a person confirms before anything is used.
- **Claude skill 2, analytics:** the skill writes the commentary, variance explanations and flags from the calculated metrics.
- **One rule for both skills:** every number comes from deterministic Python code. Claude proposes mappings and writes words, and a check rejects any commentary figure that does not match a computed one.
- **Stack:** Python (FastAPI services), Postgres, a Render Key Value queue, S3-compatible object storage and the Frankfurt region. The web front end is the one non-Python piece, a React single-page app on a Render static site, because a board-pack UI needs rich charts and editing.
- **Billing:** Stripe Checkout and the customer portal, with tiers enforced by an entitlements check in each service.

**Proposed success criteria** (to confirm against a real test set before launch):

- A company goes from first upload to an approved, shareable pack in under 30 minutes.
- Most off-spec CSVs map correctly with at most a few corrections, measured on a labelled sample.
- Automated tests show no cross-tenant data access.
- Every figure in a published pack traces back to an uploaded row.

**Out of scope for the MVP:** live integrations, M&A deal rooms, benchmarking, SSO, custom pack designs beyond a logo and colours, and a mobile app. These are in the expansion roadmap.

## Users, tenants and roles

Every piece of data belongs to one tenant, and a tenant has a type. The MVP ships the company type fully and the investor view as a read-only slice of it. The deal-team type is reserved in the data model so the M&A segment does not force a redesign.

| Tenant type | Who it is | MVP status |
|---|---|---|
| Company | A business that uploads department data and publishes board packs | Ships |
| Investor | An angel, syndicate lead, fund or solo capitalist who views packs from the companies that invite them | Read-only viewing ships; portfolio dashboards and sponsor billing come later |
| Deal team | An M&A team that runs board-style information packs across target or acquired businesses | Reserved in the model; ships after the MVP |

| Role | Scope | Can do |
|---|---|---|
| Owner | Company | Everything, including billing and deleting the workspace |
| CEO approver | Company | Approve and publish cycles, invite investors, set the plan targets |
| Department lead | One or more departments | Upload and map their department's CSVs, edit their section, submit for approval |
| Contributor | One department | Upload files and comment, but not submit |
| Investor viewer | Company packs they are invited to | View published packs and the lineage of each figure, and comment |
| Platform admin | BoardRoom.io staff | Support access, time-limited, logged and visible to the customer |

Two rules apply across every role. A user can belong to several tenants, such as a founder who is also an angel in other companies, and the active tenant is part of every request. Investor access is always per company and per pack, never account-wide.

## Core flow

*[chart: core flow · 9 steps, 2 decisions]*

A company's data moves from upload to an investor's screen in nine steps and two checks. Code does the parsing, the mapping and every calculation, Claude makes two suggestions, and a person approves each one before anything is published. A failed number check gets one automatic retry, then a person writes the section.

## Data model

The MVP defines five CSV templates, and the same templates become the schema that integrations fill later. Files are UTF-8 with a header row, ISO dates (YYYY-MM-DD) and one currency per file.

| Template | One row per | Required columns | Optional columns |
|---|---|---|---|
| Finance | Month | period (YYYY-MM), revenue, cost_of_sales, operating_expenses, cash_balance | payroll_total, capex, debt, arr, deferred_revenue, currency |
| Sales pipeline | Deal | deal_id, account_name, stage, amount, status (open, won, lost), created_date | expected_close_date, closed_date, probability, source, owner, last_activity_date |
| Product delivery | Work item or epic | item_id, title, status, points | type, started_date, due_date, completed_date, planned_period, goal_id, owner |
| People | Role or position | department, role_title, status (active, open, left), start_date | end_date, requisition_opened_date, location |
| Plan | Metric and period | metric_key, period, target_value | note |

The People template never accepts pay. Columns that look like salary, bonus, bank details, national insurance numbers or dates of birth are rejected at upload and are not stored.

**Calculated metrics.** Each metric is a versioned formula in a registry, so a pack always shows which formula version produced a number.

| Metric | Definition | Source template |
|---|---|---|
| Revenue and growth | Revenue for the period and month-on-month change | Finance |
| Gross margin | (revenue − cost_of_sales) ÷ revenue | Finance |
| Net burn | cost_of_sales + operating_expenses − revenue | Finance |
| Runway | Latest cash_balance ÷ average net burn of the last three months, or "cash-generative" if burn is zero or negative | Finance |
| Pipeline and weighted pipeline | Sum of open deal amounts, and amount × probability | Sales pipeline |
| Coverage | Open pipeline expected to close in the period ÷ (target − closed-won so far) | Sales pipeline, Plan |
| Win rate and average deal size | won ÷ (won + lost), and won amount ÷ won count | Sales pipeline |
| Stalled deals | Open deals with no activity for more than N days (default 30) | Sales pipeline |
| Delivery vs plan | Completed points ÷ planned points in the period | Product delivery |
| Slippage | Average days between due and completed dates, and the count of items past due | Product delivery |
| Headcount, open roles, attrition | Active at period end, open requisitions, leavers ÷ average headcount | People |
| Variance vs plan | Actual minus target, and as a percentage, for any metric that has a plan row | Plan |

**Cycles and versions.** A cycle is one reporting period, monthly or quarterly. It moves through Draft, In review, Approved and Published, and a published cycle is immutable. A correction creates a new version with a change note, and investors see the latest published version with its history. Every figure stores its lineage: the formula version, the dataset version and the rows or filters it was computed from, so any number in a pack can be traced back to an upload.

## Tiers and limits

The MVP launches two company tiers, Growth and Scale, and no free tier. Prices are proposed from the competitor research in Competitor Pricing and Tiers: Visible's founder tiers run $59, $129 and $199 a month with a free Starter. Growth and Scale below reuse its first two numbers in pounds, so they sit below Visible in real terms, and there is no equivalent of its $199 top tier yet. Angel pricing is deliberately not copied from the $39 individual plan in that research, which covers one investor's deal flow rather than reporting across many companies. All prices are proposals to test, not decisions.

|  | Growth | Scale |
|---|---|---|
| Price a month (annual billing) | £59 | £129 |
| Internal users | 5 | 15 |
| Investor viewers | 10 | 25 |
| Departments | All 5 templates | All 5 templates |
| Uploads a month | 30 | 100 |
| Max file size and rows | 25 MB, 200k rows | 50 MB, 500k rows |
| AI mapping assists a month | 30 | 100 |
| AI commentary drafts | 10 per cycle | 30 per cycle |
| Cycle history kept | Last 12 | Unlimited |
| Approval | Single approver | Multi-step (lead, then CEO) |
| PDF export | Logo and colours | Logo and colours |
| Audit log | Viewable | Viewable and exportable |
| Support | Email | Priority email |

Two more plans are designed for but not built in the MVP: a sponsor plan where an investor pays and invites companies, and an enterprise plan with SSO and a custom contract. Both are in the expansion roadmap.

**How limits are enforced.** The billing service holds each tenant's entitlements as named keys (for example viewers, uploads_per_month, max_file_mb). Each service checks the entitlement at the point of use, and that check is part of its own tests. Soft limits show an upgrade prompt and hard limits refuse the action. On a downgrade, data over the new limits stays readable but cannot be extended.

**AI cost per pack is small.** At Sonnet 5.5 list prices of $2 per million input tokens and $10 per million output tokens, my estimate is about $0.02 for a mapping assist (3k tokens in, 1k out) and about $0.07 for a commentary draft (20k in, 3k out). That excludes code-execution container charges, which I have not checked, so confirm them before fixing the AI limits above.

## Architecture

*[chart: system architecture · 8 services, 4 workers, 2 data stores]*

The browser talks only to the gateway. Everything else sits on Render's private network, and the workers pull jobs from the queue. Billing calls Stripe's API, the gateway receives its webhooks, and the browser uploads files straight to storage using short-lived signed links.

## Service catalogue

Eight services own data and logic, and four workers run their slow jobs. Every service is Python 3.12 with FastAPI, Pydantic v2, SQLAlchemy 2 and Alembic, and workers use Celery. They live in one monorepo with shared libraries for tenant context, auth middleware, error format, event envelope and test fixtures, and each deploys on its own.

| Service | Owns | Main API | Async work and events | Test focus |
|---|---|---|---|---|
| api-gateway (public) | No data | The only public REST API for the web app; Stripe webhook route | Rate limits, request IDs, JWT check, tenant resolution | Contract tests against every downstream OpenAPI file, role-by-endpoint matrix |
| identity | Tenants, users, memberships, roles, invitations, audit log | /tenants, /memberships, /invitations, /auth/token, /audit | Persists audit events from every service in an append-only table | Cross-tenant access, token tampering and expiry, invitation abuse |
| billing | Customers, subscriptions, entitlements, usage counters | /entitlements/{tenant}, /usage, /checkout, /portal | Handles Stripe webhooks idempotently; emits subscription.changed | Webhook replay, idempotency, entitlement matrix per tier |
| intake | Upload records, template registry, validation reports, dataset versions | /uploads (presigned URL), /uploads/{id}/validation, /templates | ingest-worker scans and parses; emits upload.received, dataset.validated, dataset.rejected | CSV fixture corpus, property-based tests, limit enforcement |
| mapping | Mapping proposals, confirmations, saved layouts per tenant | /proposals, /proposals/{id}/confirm, /mappings | mapping-worker calls Claude skill 1; emits mapping.proposed, mapping.confirmed | Labelled accuracy set, injection cells, redaction, fallback |
| metrics | Metric registry, calculated values, lineage, plan variance | /metrics, /lineage/{value}, internal /compute | Recalculates when a dataset or plan changes; emits metrics.computed | Golden datasets, invariants, formula mutation tests |
| insights | Commentary drafts, flags, number-check results | /drafts, /drafts/{id}/accept | insights-worker calls Claude skill 2; emits insight.drafted, insight.failed_verification | Faithfulness checks, missing-data cases, regression evals |
| pack | Cycles, sections, versions, approvals, investor grants, exports | /cycles, /cycles/{id}/submit, /approve, /publish, /investor/packs | Renders PDF; emits cycle.submitted, cycle.approved, cycle.published | State-machine tests, immutability, approval permissions, snapshots |
| notify (worker) | Email templates and send log | None | Consumes events; cron reminders for missing uploads and pending approvals | Template rendering, de-duplication, bounce handling |

**How services talk.** Requests between services go over Render's private network with short-lived service tokens. Events go through the Key Value queue with an outbox table in each service, so an event is never lost when a database write succeeds. Delivery is at least once, so every consumer is idempotent and keyed by event ID. No service reads another service's tables.

**Claude skill 1: csv-template-mapper.** The mapping worker runs it only when validation fails for reasons a mapping could fix.

- **What Claude sees:** the template spec, a deterministic profile of the file (column names, inferred types, null rates, distinct counts, value ranges) and 10 to 20 redacted sample rows. It never sees the whole file.
- **What it returns:** a Pydantic MappingProposal listing, for each template column, the source column or columns, one transform from a closed list (rename, parse date with format, scale by a factor, flip sign, split, combine, map values), a confidence from 0 to 1 and a short reason. It also lists unmapped required columns, warnings and columns to drop, such as anything that looks like pay.
- **What happens next:** a person confirms the proposal in the web app. Deterministic Python then applies only the confirmed transforms, so Claude never edits data. Fields under 0.8 confidence are highlighted for review, and a confirmed mapping is saved against the file's header fingerprint so the same layout maps instantly next time.
- **Skill contents:** SKILL.md with the rules, the five template specs as JSON references, and a script that checks a proposal's types against the profile.
- **If Claude is unavailable:** the manual mapping screen takes over, and the pipeline never depends on the model being up.

**Claude skill 2: board-commentary.** The insights worker runs it after metrics are computed.

- **What Claude sees:** computed metrics for the period, the previous period and the plan, the rule-based flags (for example runway under 12 months, coverage under 2x, stalled deals) and the department leads' notes. No raw rows, and no individual employee data. Account names are sent only if the tenant opts in.
- **What it returns:** a headline of up to 25 words, then per department what changed, risks and asks, each tied to metric keys, plus three questions the board is likely to ask.
- **The number check:** a Python verifier extracts every figure in the draft and requires it to match a supplied metric within the rounding rules. On a mismatch the worker regenerates once with the differences listed. If that fails, the draft is shown as failed verification and the user writes the section.
- **Skill contents:** SKILL.md with voice, structure and the rules (cite only supplied metrics, say "not provided" when data is missing, no advice and no forecasts beyond the plan), a metric glossary, and a copy of the verifier script so Claude can self-check inside the container.

**How both are called.** Each skill is a custom Agent Skill uploaded through the [Skills API](https://platform.claude.com/docs/en/build-with-claude/skills-guide) and referenced in the request's container with a pinned version, alongside the code execution tool. Skill names use lowercase letters and hyphens and cannot contain "claude" or "anthropic". Both start on claude-sonnet-5-5, with Haiku 5.5 evaluated for mapping once the accuracy set exists. Confirm that the model you choose is on the code execution tool's compatibility list. Keep the skills list and its order identical across requests so the system prompt stays cacheable, and handle the pause_turn stop reason for long runs.

## Security and data protection

Board packs hold commercially sensitive numbers, so the design assumes a hostile upload, a curious tenant and an unreliable model. Each control below has a test.

| Area | Control | How it is tested |
|---|---|---|
| Tenant isolation | A tenant ID on every row, Postgres row-level security with the tenant set per connection, a separate database role per service and no cross-schema grants | Two-tenant tests on every endpoint, and a CI check that every table has a policy |
| Authentication and roles | Short-lived JWTs verified at the gateway and again in each service, one shared role check, investor access per company and per pack | A role-by-endpoint matrix generated from the OpenAPI files |
| Sensitive columns | Header and content patterns detect pay, bank details, national insurance numbers, dates of birth and personal emails. They are dropped at intake and never stored or sent to Claude | Fixtures with sensitive columns, asserting absence from storage and from every Claude payload |
| File handling | Size and row limits, malware scan before parsing, parsing in a worker with memory and time limits, private storage with short-lived presigned URLs, formula injection neutralised on export | Hostile fixtures: oversized rows, decompression bombs, encoding tricks, cells starting with =, +, - or @ |
| Claude data handling | Only headers, redacted samples and aggregates are sent. Cell text is passed as data inside a delimited block, and closed output schemas limit what an injected instruction could do | Injection cells in the mapping set, payload snapshot tests, redaction tests |
| Secrets | Render environment groups and secret variables, rotation schedule, secret scanning in CI | Secret-scan gate, no secrets in logs test |
| Audit | Append-only audit log of logins, uploads, mappings, approvals, publishes and every investor view. Staff support access is time-limited and visible to the customer | Every state change must emit an event, enforced by a test |
| Backup and recovery | Render Postgres point-in-time recovery (3 days on Hobby, 7 on Pro), storage versioning, proposed targets of 1 hour data loss and 4 hours to restore | A restore drill before launch and each quarter |
| Software supply chain | pip-audit, Dependabot, bandit, container image scanning and a software bill of materials | Failing gates in CI |
| Privacy and compliance | Each tenant is the data controller and BoardRoom.io the processor, with a DPA, a subprocessor list (Render, Anthropic, the storage provider, Stripe, the email provider), deletion within 30 days of tenant closure and a breach runbook | Deletion test that purges every store, and a tabletop incident exercise |

**What Anthropic retains.** Per Anthropic's [data retention documentation](https://platform.claude.com/docs/en/manage-claude/api-and-data-retention), retained data is never used for training without express permission, and conversation content is not retained by default. Agent Skills are the exception that matters here: they are not covered by zero data retention, and code-execution container data is retained for up to 30 days. Structured outputs and prompt caching are eligible for zero data retention where an organisation has it, and the Message Batches API keeps data for 29 days.

**Design response.** The skills see only headers, redacted samples and aggregates, which limits what sits in those containers. Each tenant also has a switch for a Messages-API-only path with no code execution: the same instructions run as a system prompt with structured outputs, and the number check runs only in our own Python. That path is the one to use for any customer who requires zero data retention. Decide with a lawyer whether the standard path needs a customer-facing disclosure, and check Anthropic's data residency options before promising UK or EU processing of prompts.

Before launch: an external penetration test, a dependency and licence review, a privacy notice and the check that the business is registered with the ICO if required. SOC 2 for BoardRoom.io is a roadmap item, not an MVP promise.

## Infrastructure on Render

Render fits this design: it has private services, background workers, a managed queue store and a single-file Blueprint for the whole system. The decisions below were checked against Render's docs on 15 October 2026.

| Concern | Decision | Why |
|---|---|---|
| Region | Everything in Frankfurt | It is the only European region in the [regions list](https://render.com/docs/regions), services in different regions cannot share a private network, and a service's region cannot be changed later |
| Service types | Static site for the web app, one public web service (the gateway), private services for every internal API, background workers for queue consumers, one cron job for reminders | [Private services](https://render.com/docs/private-services) have no public address, and [workers](https://render.com/docs/background-workers) cannot receive requests, only poll a queue |
| Queue | Render Key Value as the Celery broker, reachable only on the private network | Render's worker docs list Celery with Key Value as a standard pattern |
| Database | One Render Postgres instance with a schema and a role per service for the MVP, split into separate instances when a service needs its own scaling or backups. Connection pooling on, migrations in the pre-deploy command | Small Postgres plans cap connections at 100, and a pre-deploy command runs migrations before the new version starts |
| File storage | An S3-compatible bucket outside Render, in the UK or EU, with versioning and private access | Render's data stores are Postgres, Key Value and [persistent disks](https://render.com/docs/disks), and a disk attaches to one instance, blocks scaling and removes zero-downtime deploys |
| Environments | One monorepo Blueprint (render.yaml), production and staging as separate environments with network isolation on, a full-stack preview environment per pull request, and build filters so a change rebuilds only the services it touches | The [Blueprint spec](https://render.com/docs/blueprint-spec) supports projects, environments, previews and per-service root directories |
| Workspace plan | Hobby while prototyping, Pro at launch | Per Render's [pricing](https://render.com/pricing), Hobby allows 25 services, single-service previews and 2 environments per project. Pro adds unlimited services, full-stack previews, isolated environments, autoscaling and audit logs |
| Deploys | Zero-downtime for web services, and a graceful shutdown delay on workers so in-flight jobs finish. Jobs are acknowledged late and idempotent | Shutdown delay is configurable up to 300 seconds |
| Observability | Structured JSON logs with tenant ID and no data values, health checks on the gateway, error tracking, uptime monitoring, alerts on queue depth, Claude error rate and auth failures | Render supplies dashboard metrics and logs, and the rest is added |

A trimmed Blueprint shows the shape. Each service points at its own folder, and environment variables wire services together without hard-coded addresses.

```yaml
previews:
  generation: automatic
  expireAfterDays: 3
services:
  - type: web
    name: api-gateway
    runtime: python
    region: frankfurt
    plan: 0.5c-512mb
    rootDir: services/gateway
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    healthCheckPath: /healthz
    envVars:
      - key: IDENTITY_URL
        fromService: { type: pserv, name: identity, property: hostport }
  - type: pserv
    name: identity
    runtime: python
    region: frankfurt
    rootDir: services/identity
    buildCommand: pip install -r requirements.txt
    preDeployCommand: alembic upgrade head
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: DATABASE_URL
        sync: false
  - type: worker
    name: ingest-worker
    runtime: python
    region: frankfurt
    plan: 1c-2g
    rootDir: services/intake
    startCommand: celery -A app.worker worker -Q ingest
    maxShutdownDelaySeconds: 120
    envVars:
      - key: QUEUE_URL
        fromService: { type: keyvalue, name: queue, property: connectionString }
  - type: keyvalue
    name: queue
    region: frankfurt
    ipAllowList: []
databases:
  - name: boardroom-db
    region: frankfurt
    plan: 0.5c-1g
    connectionPool: pgbouncer
    ipAllowList: []
```

The per-service database roles are created by a migration job and their connection strings are set as secrets, because a Blueprint's connection string uses the instance's main user.

**Starting cost.** At Render's list prices, production comes to about $192 a month:

| Item | Monthly |
|---|---|
| Pro workspace | $25 |
| Six small services (gateway, identity, billing, intake, mapping, insights) at $7 | $42 |
| Metrics and pack services at $25 | $50 |
| Ingest worker at $25, and mapping, insights and notify workers at $7 | $46 |
| Postgres, 0.5 CPU and 1 GB | $19 |
| Key Value, 256 MB | $10 |
| **Total, before bandwidth, storage, email, Stripe fees, Claude and staging** | **$192** |

The sizes assume the FastAPI services fit in 512 MB and that parsing and PDF rendering need 2 GB, which milestone M0 should measure. Run staging on the smallest plans and let preview environments expire so they do not double the bill.

## Build plan and testing plan

The build runs in ten steps, and no step is done until its tests are written and green in CI. Sizes are relative (S, M, L) because duration depends on team size, which is still open.

### Test layers

| Layer | What it proves | Tooling | Gate |
|---|---|---|---|
| Unit | Domain logic: metric formulas, validators, state machines | pytest, Hypothesis for property tests, mutmut on formulas | At least 85% line coverage on metrics and pack logic; surviving formula mutants reviewed |
| Service integration | One service with real Postgres, queue and object storage | pytest with Testcontainers (Postgres, Redis-compatible, MinIO) | All pass on every pull request |
| Contract | Services agree on each other's APIs and events | OpenAPI files checked by Schemathesis, plus consumer-driven contracts for events | Provider build fails if a consumer contract breaks |
| End to end | Critical journeys through the real web app | Playwright on the pull request's preview environment | Six journeys green before merge |
| Security | Isolation, authorisation, hostile files, dependencies | Role matrix, two-tenant tests, hostile CSV corpus, OWASP ZAP baseline, pip-audit, bandit, image scan | Zero high-severity findings; matrix at 100% |
| AI evals | Mapping accuracy, commentary faithfulness, injection resistance, cost and latency | A labelled file set and an automatic grader, run on a schedule and on any skill or prompt change | Thresholds set in M4 and M6; a regression blocks the skill release |
| Performance and resilience | Upload and pack latency, queue retries, duplicate events | k6 or Locust, fault injection on workers | Targets set in M9; no lost or double-processed jobs |

AI unit tests use a fake Claude client with recorded responses so CI never depends on the live API. The real model is called only by the scheduled evals.

**Pipeline.** A pull request runs lint (ruff), types (mypy), unit and integration tests, contract checks and security scans, then deploys a full-stack preview environment for the end-to-end and ZAP runs. Merging deploys to staging, where the full suite runs nightly. Production needs a manual approval after a staging smoke test, and Render's instant rollback is the recovery path.

### Milestones

| Step | Builds | Depends on | Exit criteria | Tests that must pass |
|---|---|---|---|---|
| M0 Foundations (M) | Monorepo, shared libraries, a service template with auth middleware, tenant context, health checks and the test harness, the Blueprint, CI, observability | None | A template service deploys to a preview environment from the Blueprint; memory sizes measured | Template unit and integration tests, all CI gates running and failing correctly on a seeded defect |
| M1 Identity and tenancy (M) | Tenants, users, roles, invitations, tokens, gateway authentication, audit log | M0 | A user can create a company, invite a colleague and an investor, and every action is audited | Role matrix at 100%, two-tenant tests, token tampering and expiry, invitation abuse, contract tests gateway to identity |
| M2 Intake (L) | Presigned upload, malware scan, parsing, the five templates, validation reports, dataset versions | M1 | Valid files become dataset versions, invalid files give a clear report, limits follow the tier | Fixture corpus (BOM, delimiters, encodings, duplicate headers, huge files, formula cells), Hypothesis tests, sensitive-column drop tests, idempotent upload |
| M3 Metrics engine (M) | Metric registry, formulas, lineage, plan variance | M2 | Every metric in the data model computes with lineage back to rows | Golden datasets with hand-calculated results, invariants, rounding and currency tests, mutation tests, a 100k-row performance test |
| M4 Mapping skill (L) | Profiler, skill 1, proposal and confirm flow, saved layouts, manual fallback | M2 | Off-spec files map with a person's confirmation, and the same layout maps instantly next time | Labelled accuracy set with a threshold agreed up front, schema and closed-vocabulary tests, injection cells, redaction snapshot tests, Claude-down fallback, same mapping gives the same output |
| M5 Pack service (L) | Cycles, sections, versions, approval states, investor grants, PDF export | M3 | A cycle goes from Draft to Published, is immutable, and investors see only what they are granted | State-machine tests for every illegal transition, immutability, approval permissions, snapshot tests of the rendered pack, export injection test |
| M6 Analytics skill (M) | Skill 2, number verifier, flags, accept and edit flow | M3, M5 | Commentary drafts, passes the number check or is blocked, and a person accepts per section | Faithfulness eval (every figure must match), missing-data cases, no-advice and no-individual-data checks, regression set, token budget |
| M7 Billing and tiers (M) | Stripe checkout and portal, webhooks, entitlements, usage counters | M1 | Each tier's limits are enforced across services | Stripe test-mode webhook replay, idempotency, an entitlement matrix per tier, downgrade over-limit behaviour |
| M8 Web app (L) | Onboarding, upload, mapping confirmation, pack editor, approval, investor view | M2 to M7, built alongside | The six critical journeys work in a browser | Component tests, Playwright for the six journeys, accessibility checks with axe, visual regression |
| M9 Hardening and beta (M) | Load test, penetration test, restore drill, runbooks, alerts, privacy documents, beta with 5 to 10 companies | M8 | The summary's success criteria are met on the beta set | Load targets, zero high findings, a successful restore, a deletion test, a tabletop incident |

**The six critical journeys.** Sign up and create a company. Upload a valid file and see metrics. Upload an off-spec file, confirm the mapping and see metrics. Draft commentary, edit it and submit a cycle. Approve and publish as the CEO. View the published pack as an invited investor and trace a figure to its source.

## Risks and open decisions

The biggest risk is overhead: eight services and four workers is a lot of moving parts for a small team, so the service template and the monorepo have to make each new service close to free.

### Open decisions

| Decision | Options | My recommendation |
|---|---|---|
| Who builds it, and how many engineers | Not yet known | Settle first, because it sets how fast the ten steps run and whether to review the service count after M5 |
| Authentication | Build credentials in identity, or use a managed provider behind identity's own tenant and role model | Managed provider for passwords, MFA and magic links, to reduce security risk, with enterprise SSO added the same way later |
| Web front end | React single-page app, or server-rendered Python with HTMX | React, because the pack editor needs rich charts and inline editing. It is the one non-Python piece |
| Object storage | AWS S3 in London, Cloudflare R2, or Backblaze B2 | S3 in London for UK residency, if latency from Frankfurt is acceptable |
| Job framework | Celery with Key Value, or Render Workflows | Celery for the MVP because it is documented on Render. Revisit Workflows at M4 for the Claude calls |
| Database layout | One Postgres instance with a schema per service, or one instance per service | One instance now, split when a service needs its own scaling or backup policy |
| Malware scanning | ClamAV as a private service, or a third-party scanning API | Decide at M2 once file volumes are known |
| PDF rendering | WeasyPrint, or headless Chromium | WeasyPrint for lower memory, with a snapshot test of the output |
| Claude data path | Standard skills path, or the Messages-API-only path for zero data retention | Build both behind a tenant switch, and get legal advice on disclosure |
| Currency | GBP only, or multi-currency | GBP and one currency per file for the MVP |
| Name and domain | BoardRoom.io (working name, expensive or taken). Short-word candidates to check: Gavel, Aye, Dais, Folio, Chair, Tally | Check trademark and domain availability, since "boardroom" is a common term in this category |
| Prices | The proposed tiers | Validate in the 8 to 10 interviews from the market research before building billing |

### Risks

| Risk | Mitigation |
|---|---|
| Microservice overhead slows delivery | Shared template and libraries, one deployable per service, only split workers where load differs, review at M5 |
| Real CSVs are messier than the fixture set | Collect labelled files from the beta, keep saved layouts, always offer the manual mapping screen |
| Claude proposes a wrong mapping or writes an unfaithful figure | Closed transform list, human confirmation, the number verifier, scheduled evals with blocking thresholds |
| A hostile cell tries to steer the model | Cells are passed as data, outputs are schema-bound, injection cases live in the eval set |
| Data retention worries block sales | The zero-data-retention path and a clear subprocessor and retention page |
| A tenant isolation bug leaks one company's numbers | Row-level security, two-tenant tests on every endpoint, an external penetration test before launch |
| A single Postgres instance and one region are failure points | High availability on Pro, point-in-time recovery, a tested restore and a written recovery runbook |
| Costs creep beyond the $192 base | Entitlement limits on AI use, cost alerts on Claude spend, previews that expire |
| The product is easy to copy | Compete on lineage, the approval workflow and investor access, which the market research found missing in cheaper tools |
| The M&A segment dilutes focus | Keep the deal-team tenant reserved until the investor-pays model is validated |
