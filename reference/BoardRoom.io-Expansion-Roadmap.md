# BoardRoom.io Expansion Roadmap

2026-10-15 · @Alex cooper

## Summary

Six phases take BoardRoom.io from CSV board packs for companies to an investor platform, automated integrations and M&A deal-team workspaces. Each phase ends at a gate, which is a measurable test and not a date. It builds on BoardRoom.io MVP Spec.

- **Why this order:** Phase 2 gets the MVP to paying customers. Phase 3 adds the investor side, because investor-sponsored tools spread through portfolios: [Standard Metrics](https://intercom.help/standardmetrics/en/articles/4600342-faqs) is paid for by investment firms and free for companies. Phase 4 removes manual uploads with integrations. Phase 5 adds M&A deal teams, a different buyer and market that still needs its own research. Phase 6 builds the trust features that larger buyers ask for.
- **What never changes:** the five CSV templates stay the data contract. Every integration and every new workspace type feeds the same templates, so metrics, packs and the approval workflow work unchanged.
- **The order is a hypothesis:** whether Phase 3 or Phase 4 comes first depends on whether beta customers ask for investor access or for automation first, so revisit it at Gate 2.
- **Segments covered:** founders and CEOs, investors, and M&A deal teams.

## Segments

Three segments share one platform and one data contract. This assumes "M&A" means advisers and acquirers who gather comparable information on target and acquired businesses.

| Segment | Job to be done | Who pays | Needs beyond the MVP | Arrives |
|---|---|---|---|---|
| Company teams (founders and CEOs) | Produce an accurate board pack with less effort and fewer chasing emails | The company, on the Growth or Scale tier | Reminders, branding, comments, then integrations that remove manual uploads | Phases 2 and 4 |
| Investors (angels, syndicates, funds, solo capitalists) | See consistent numbers from many companies without chasing them | The investor on a sponsor plan, or nobody for a free viewer | A portfolio overview, a request-and-collect flow, cross-company dashboards | Phase 3 |
| M&A deal teams | Collect comparable information from targets and track businesses after a deal | The deal team, per active deal or per seat (to be researched) | Deal workspaces, standard information packs, comparison across targets, strict permissions, Q&A | Phase 5 |

The three are connected. A company that an investor sponsors is the same tenant that a deal team may later acquire, and an acquired business becomes a company workspace under the acquirer's reporting. That is why the tenant model already reserves all three types.

## Roadmap

*[chart: expansion roadmap · 6 phases, 6 gates]*

The phases are equal bands and are not drawn to scale, because the gates set the pace, not the calendar. The next gate is highlighted. Phases 3 and 4 can swap, and Phase 5 waits on its own market research.

## Phase 2: Beta to general availability

Phase 2 turns a working beta into a product people pay for and rely on every month. Nothing in it changes the architecture, so it is mostly depth in the services the MVP already has.

| Workstream | What gets built | Tests and evidence |
|---|---|---|
| Reminders | Scheduled reminders for missing department uploads and pending approvals, in the user's time zone, from the notify worker and its cron job | Scheduling tests across time zones and daylight saving, de-duplication, email authentication checks (SPF, DKIM, DMARC) and bounce handling |
| Saved layouts at scale | Header-fingerprint matching, template versioning that migrates saved mappings, and a review queue for low-confidence mappings | Migration tests when a template changes version, accuracy tracked on real beta files |
| Collaboration | Comments on sections and metrics, mentions, change notes on corrected versions | Permission tests so a viewer's comment never reaches another investor |
| Branding and sharing | Logo and colours, investor links with expiry, watermarked PDFs | Link expiry and revocation tests, snapshot tests of branded output |
| Support tooling | Time-limited, logged staff access, in-app help, a status page, product analytics events without personal data | Access-log completeness test, analytics payload scan for personal data |
| Billing hardening | Annual plans, VAT invoices, failed-payment handling, plan changes | Stripe test-mode scenarios for each failure and change path |
| Data export | A full export of a tenant's data and packs in CSV and PDF | Export parity test: exported numbers equal the app's numbers |
| Accessibility and performance | A WCAG 2.2 AA audit and fixes, page budgets for the pack, tuning for large files | Automated and manual accessibility audit, load test at ten times beta volume |

**Gate 2.** Paying customers complete a second consecutive monthly cycle without help from support, a second external penetration test finds nothing high-severity, and support load per customer is sustainable. Set the percentage targets from beta data at Gate 1, and use the same checkpoint to confirm the order of Phases 3 and 4.

## Phase 3: Investor side and the sponsor plan

Phase 3 builds the investor workspace fully, so one investor can see many companies and pay for the tools those companies use. This is the growth loop: an investor invites companies, and each company that joins brings its own contacts and its other investors.

**What gets built**

- **Investor workspace:** roles for partner, analyst and LP viewer. A list of companies with the latest pack status and four headline metrics (runway, net burn, pipeline coverage, delivery against plan). A view of which companies have gone quiet against their agreed cadence, and alerts when a rule fires, such as runway under a threshold.
- **Request and collect:** the investor sends a standard request naming the metrics and cadence. The company's owner reviews it and approves what is shared metric by metric, and can pause or revoke sharing. The company owns its data throughout.
- **Sponsor plan and invitations:** the investor invites companies and pays a platform fee. Each invited company gets a free basic workspace with the sponsor's request already set up, and can upgrade. The investor sees only what the company shares.
- **Cross-company dashboard:** the same metric across companies, normalised to one currency, with filters and an export of the investor's own view.
- **Data model additions:** investor tenant, sponsorship, data request, and a sharing grant (company, investor, metric scope, cadence, status), with audit events on every grant change.

**Rules that must hold.** One investor can never see that another investor backs the same company. Revoking a grant stops new sharing immediately, and the treatment of packs already shared is an open decision below. Benchmarking against other companies is not in this phase because it needs opt-in and enough volume, and is planned for Phase 6.

**Tests that must pass**

- A grant and revoke matrix across every role and endpoint, and cross-investor isolation tests.
- A state-machine test of the request lifecycle (sent, accepted, partly accepted, paused, revoked).
- Performance tests of the portfolio view at 100 and more companies, and currency-normalisation tests.
- Rule tests for the "gone quiet" and alert logic across time zones.
- A sponsor entitlement matrix covering invited-company upgrades and sponsor downgrades.

**Gate 3.** At least one investor sponsors several companies and renews, the sponsor pricing is accepted in interviews, and no cross-tenant data incident has occurred.

## Phase 4: Integrations

Phase 4 adds a connector service that fills the same five templates automatically, so a company connects its tools once and the monthly upload disappears. Because a sync produces the same dataset an upload does, everything downstream is unchanged.

**The connector service**

- **What it owns:** connections (provider, scopes, status), encrypted credentials, sync schedules and run history. It is a new private service with its own sync worker.
- **How a sync flows:** it pulls from the provider, maps provider fields to template columns, and hands the result to the intake service as a dataset. It then passes the same validation, metric calculation and approval steps as a CSV.
- **Custom fields:** where a provider has custom fields or stage names, the existing mapping skill proposes the mapping and a person confirms it once.
- **Credentials:** OAuth with read-only scopes. Tokens are encrypted with a managed key, never logged, rotated and revocable by the tenant at any time.
- **Reliability:** scheduled incremental pulls, backoff on rate limits, idempotent runs, schema-drift detection and a connector health view the tenant can see. CSV upload always works, and if a connector fails the last good dataset stands and the tenant is told.

**Priority connectors.** Start with one per template, then rank the rest by beta demand.

| Template | First connector | Next candidates |
|---|---|---|
| Finance | Xero | QuickBooks (Standard Metrics already connects both) |
| Sales pipeline | HubSpot | Salesforce, Pipedrive |
| Product delivery | Jira | Linear |
| People | HiBob | BambooHR, headcount fields only |
| Plan | Google Sheets | Excel files from OneDrive |

**Security rules specific to integrations.** Pay and compensation fields are excluded in the connector's scopes and again at intake, so they are blocked twice. Raw provider responses are not stored, only the normalised datasets. A tenant can disconnect a provider and delete its synced data in one action.

**Tests that must pass**

- Recorded provider responses as fixtures for each connector, plus nightly runs against provider sandbox accounts.
- Contract tests that fail when a provider's API changes shape.
- Idempotency: running a sync twice gives the same dataset version.
- Fault injection for rate limits, outages, token expiry and revoked access.
- A data-match test: the same data through a connector and through a CSV gives identical metrics.
- Exclusion tests proving that pay fields never reach storage or Claude.

**Gate 4.** Every live connector passes its data-match test, sync success and error rates meet limits agreed at Gate 2, three connectors run for real customers, and manual uploads fall for connected companies.

## Phase 5: M&A deal teams

Phase 5 adds a deal-team workspace so an M&A team can collect comparable information from targets and track the businesses it acquires. This is the least researched part of the plan. The market research so far covers board and investor reporting, not M&A tooling, so run separate research before committing (below).

**What gets built**

- **Deals:** a project with a stage (screening, diligence, signing, closing, post-deal), a team and a list of targets.
- **Targets:** each target is a company workspace created by invitation. The seller uploads through the same CSV templates or connectors in a guest workspace that sees only its own data.
- **Information request list:** a checklist of templates and documents per deal, with status and reminders, reusing the Phase 2 reminder machinery.
- **Standard pack per target:** the five templates plus three M&A templates. Customers (revenue by customer and period), Adjustments (normalisations from reported to adjusted earnings, each with a reason and an evidence reference) and Working capital (balances by period).
- **M&A metrics:** customer concentration (top 1, 5 and 10 share), net revenue retention, a normalised earnings bridge and the working capital trend, all with lineage.
- **Comparison:** the same metrics side by side across targets.
- **Q&A log:** questions and answers tied to a pack section, timestamped and audited.
- **Deal permissions:** roles for lead, analyst, adviser, lender and seller, field-level visibility (a lender might see summary metrics only), clean-team style restrictions where needed, and an NDA acknowledgement before access.
- **Post-deal:** an acquired target becomes a company workspace reporting to the acquirer, so 100-day plan tracking and roll-up reporting reuse the earlier phases. Exports are controlled, watermarked and logged.

**Rules that must hold.** A seller never sees another seller or the buyer's notes. Closed deals are archived with retention rules and a legal hold option. Every view is audited.

**Tests that must pass**

- A per-deal permission matrix covering every role, endpoint and object.
- Seller isolation, the NDA gate, field-level visibility and redaction tests.
- Golden-dataset tests for the concentration and earnings-bridge formulas.
- Watermark and export-logging tests, and Q&A audit completeness.
- Performance with 30 or more targets in one deal.

**Research needed before building.** What M&A teams use today (virtual data rooms, spreadsheets, CRMs), what they pay, who buys (advisers, corporate development or private equity), how much of this overlaps with data rooms, and what confidentiality expectations apply.

**Gate 5.** A deal team runs a real process in the workspace, the permission and confidentiality tests pass, and the packaging is accepted in pilot interviews.

## Phase 6: Scale and trust

Phase 6 adds what larger customers and auditors ask for, once there is revenue to justify the cost. Some of it starts earlier: SOC 2 Type II needs an observation period, so evidence collection should begin around Phase 2.

| Workstream | What gets built | Tests and notes |
|---|---|---|
| SSO and provisioning | SAML and OIDC single sign-on and SCIM provisioning, behind an enterprise plan | Identity-provider fixtures, and a test that deprovisioning removes access at once |
| SOC 2 | Policies, evidence automation and vendor reviews, aiming at a Type I report and then Type II | Evidence is generated from the CI and audit trails the MVP already produces |
| Public API and MCP server | A REST API with scoped tokens for packs and metrics, and an MCP server so customers can query their own data from their AI tools. [Standard Metrics](https://standardmetrics.io/) and [Visible](https://visible.vc/pricing/) both already offer one | Token scope matrix, rate limits, tenant isolation through the MCP path, and checks that tool output cannot carry injected instructions |
| Benchmarking | Opt-in, anonymised, aggregated comparisons with a minimum cohort size so no company is identifiable. Standard Metrics benchmarks against more than 10,000 startups, which sets the expectation | Minimum-cohort tests, and a test that opting out removes a company's data from future benchmarks |
| Regions and residency | A regional stack when customers need it. Render's [regions](https://render.com/docs/regions) include Frankfurt as the only European one, plus Oregon, Ohio, Virginia and Singapore, and each region has its own private network, so a US stack is a separate deployment | Deployment tests from the same Blueprint, and a check of Anthropic's data residency options for prompts |
| Deck export | Export a pack to PowerPoint, for example with Anthropic's pre-built PowerPoint skill or a code library | Snapshot tests, and a decision on data retention, since skills are not covered by zero data retention |
| Resilience | A high-availability Postgres standby, read replicas where load needs them, cross-region copies of stored files, and a documented recovery plan | A failover drill and a restore drill each quarter |

**Gate 6.** A SOC 2 Type I report is issued and the Type II observation period has started, at least one enterprise customer uses SSO, and customers are using the API or the MCP server.

## Platform evolution

The architecture changes when a measured trigger fires, not on a schedule. Each trigger below has a metric to watch and a planned response.

| Trigger to watch | Planned response |
|---|---|
| Postgres CPU or connections under sustained pressure, or one service's data growing fast | Split that service onto its own Postgres instance, add read replicas, keep connection pooling on |
| Queue depth or job latency growing, or long-running jobs | Priority queues by tier, more worker instances (autoscaling needs Render's [Pro plan](https://render.com/pricing)), and a look at Render Workflows for durable retries |
| One tenant's load slowing others | Per-tenant concurrency limits and fair-share queues |
| Connector volume in Phase 4 | A separate sync worker pool and a rate-limit budget per provider |
| Claude cost or latency | Prompt caching with a stable skills list, the [batch API](https://platform.claude.com/docs/en/build-with-claude/batch-processing) at half price for backfills, routing easy mappings to Haiku 5.5, and per-tenant AI budgets |
| A model or skill change | Pinned skill versions, a full eval run on any new model before switching, and rollback by version |
| Enterprise needs such as IP allow lists, SAML or contractual uptime | Render's Scale plan ($499 a month plus compute) or Enterprise plan, or a cost comparison against moving to a hyperscaler at that point |
| A customer in another region | A regional stack deployed from the same Blueprint, with Terraform as an option |
| Debugging across many services | Distributed tracing with OpenTelemetry, added by Phase 3 |

**What stays stable.** The five CSV templates, the event envelope and each service's public API are versioned, and consumers must tolerate additive changes. That is what lets a new workspace type or integration arrive without rewriting the services around it.

## Packaging and pricing

The three company tiers from the MVP stay, and the expansion adds sponsor plans for investors, a deal-team plan and add-ons. Every price below is a proposal to test, anchored on the competitor research in Competitor Pricing and Tiers: Dealum's network plans step up by member count, Standard Metrics is paid for by investors and free for companies, and Dealum's individual plan is $39 a month, though that covers one investor's deal flow, not reporting across a portfolio.

**Sponsor plans (Phase 3)**, stepped by the number of companies in the portfolio:

| Plan | Companies included | Price a month | Per company |
|---|---|---|---|
| Angel (individual) | Up to 5 | £59, or free as a viewer only | £11.80 |
| Sponsor 10 | Up to 10 | £99 | £9.90 |
| Sponsor 40 | Up to 40 | £299 | £7.48 |
| Sponsor 100 | Up to 100 | £599 | £5.99 |
| Enterprise | More than 100 | Custom | Custom |

All sponsor plans include the portfolio overview, requests, dashboards, alerts and invitations. There is no free company tier, so a sponsor either covers an invited company's Growth or Scale plan as an add-on or the company pays for itself. Open question: whether invited companies get a time-limited trial. Angels often back many companies, so they are priced per company rather than from the $39 anchor. Test £59 for five companies against free viewer access in the investor interviews.

**Company tiers by phase.** Growth gains comments and branding in Phase 2 and its first connector in Phase 4. Scale gains three connectors and keeps the multi-step approval. Connector counts follow the pattern in Visible's founder tiers, which step through one, three and five integrations.

**Deal-team plan (Phase 5).** No price is proposed because the research is missing. The options to test are an annual workspace fee, a monthly fee per active deal, or a price per seat.

**Add-ons.** Extra investor viewers in blocks of 10, extra connectors, extra AI assists, white-label investor links on a custom domain, audit log export for tiers that lack it, and priority support.

Prices exclude VAT, and Stripe handles tax and invoices.

## Testing and release strategy

Every phase adds test layers for what is new, and no phase is released until its gate passes. The MVP's layers (unit, service integration, contract, end to end, security, AI evals, performance) all carry forward.

| Phase | New tests and practices | Release gate |
|---|---|---|
| 1 MVP | The full layer set in the MVP spec, with the six critical journeys on every pull request | Success criteria met on the beta set |
| 2 Beta to GA | Email deliverability, reminder scheduling across time zones, export parity, accessibility audit, load at ten times beta volume, a second penetration test | Gate 2 |
| 3 Investor side | Grant and revoke matrix, cross-investor isolation, request state machine, portfolio performance at 100 and more companies, currency normalisation | Gate 3, with no cross-tenant incident |
| 4 Integrations | Provider fixtures, nightly sandbox runs, contract canaries for provider API changes, idempotent syncs, fault injection, data-match tests, pay-field exclusion tests | Gate 4 |
| 5 M&A | Per-deal permission matrix, seller isolation, NDA gate, redaction and field visibility, export and watermark logs, golden datasets for M&A formulas, 30 or more targets per deal | Gate 5 |
| 6 Scale and trust | Identity-provider fixtures, API token scopes, MCP tenant isolation and injection tests, minimum-cohort tests, failover and restore drills, SOC 2 evidence generated from CI | Gate 6 |

**Rules that apply to every phase**

- A new service or workspace type ships its tenant-isolation tests before any data goes into it.
- Every new capability is behind a per-tenant feature flag. It goes to an internal dogfood tenant, then to named design partners, then to everyone.
- The AI eval sets grow each phase: connector custom fields for mapping, then investor and deal-team packs for commentary. Any skill or model change reruns every eval and blocks on a regression.
- Database changes use expand-then-contract migrations tested on anonymised production-shaped data, so one release can always roll back, using Render's instant rollback.
- From Phase 2, availability and job-latency targets are written down, and releases pause when an error budget is spent.
- Security cadence: an external penetration test before launch, after Phase 2, before Phase 5 and then yearly, continuous dependency updates, and restore and failover drills each quarter.
- Each phase has a named group of 5 to 10 design partners who see the work early and supply labelled real data for the evals.

## Risks and open decisions

The main risk is breadth: three segments, integrations and compliance work compete for the same small team, so each gate exists to stop work on the next phase until the current one has earned it.

### Open decisions

| Decision | Options | My recommendation |
|---|---|---|
| Order of Phases 3 and 4 | Investor side first, or integrations first | Decide at Gate 2 from what beta customers ask for. The default is investor side first because it drives distribution |
| What a revoked investor keeps | Everything already shared, nothing, or a choice per grant | The company chooses per grant with a default of keeping published history, after legal review |
| Pay data from HR tools | Always excluded, or optional with explicit consent | Always excluded, since no board-pack metric needs individual pay |
| Benchmarking rules | Whether it is opt-in, and the minimum cohort size | Opt-in, with the cohort size set with legal advice before Phase 6 |
| M&A buyer and scope | Advisers, corporate development or private equity, and which features | Commission the research first, and consider building only post-deal tracking and target comparison at the start |
| Staying on Render | Render Scale and Enterprise plans, or a move to a hyperscaler | Revisit when an enterprise trigger fires, comparing total cost then |
| When to start SOC 2 evidence | Phase 2 or Phase 6 | Phase 2, because Type II needs an observation period |
| Sponsor pricing | The proposed steps | Validate in interviews before Phase 3 build starts |

### Risks

| Risk | Mitigation |
|---|---|
| Scope sprawl across three segments | Gates, one segment in build at a time, and pilots before commitments |
| Connector upkeep grows with every provider | A connector count per tier, contract canaries for provider changes, and ranking by demand |
| Investor-side network effects arrive slower than hoped | A free workspace for invited companies, investor design partners from the beta, and hands-on onboarding |
| Established tools respond | Compete on lineage, the approval workflow and board-focused output, aimed at angel-backed companies that fund-oriented tools serve poorly |
| M&A is a different market with strong incumbents, and is unresearched | A research gate before Phase 5 and a narrow first scope |
| One bad AI figure or one data leak destroys trust | The number verifier, human confirmation, row-level security, external penetration tests and an incident runbook |
| Reliance on a single AI provider | Model calls sit behind the mapping and insights services, a manual fallback exists, and a non-AI path exists for customers who require it |
| Compliance duties grow with the product | A legal review at each phase of data protection duties, and of whether any investor-facing feature could count as advice, which the commentary rules are designed to avoid |
