# Epics and build order

One epic at a time. Each ends with a demo of working software. Phase 2 (E11) starts only after E10.

| Order | Epic | Covers | Key FRs | Done when |
|---|---|---|---|---|
| 1 | E1 Foundations and tenancy | Monorepo, service template, CI, Blueprint, tenants, users, roles, standing investor invites, audit log | FR-2.1 to 2.9, FR-10.1, 10.7, FR-11.1, 11.2, 11.5, 11.8, FR-12.1 to 12.4, FR-13.1 | A user creates a company, invites a colleague and an investor, every action audited, two-tenant tests pass |
| 2 | E2 AI file intake | Upload, profiler, skill 1, pay drop, one question when stuck, saved layouts, manual fallback, internal log | FR-4.1 to 4.12, FR-3.1, 3.2, FR-11.3, 11.4, 11.7 | Real messy finance and pipeline files are understood with no correction at the agreed rate |
| 3 | E3 Figures engine | Metric registry, skill 2 row selection, lineage, click view data, display precision, risk levels | FR-5.1 to 5.4, 5.6, 5.7, FR-1.1, 1.2, FR-13.3 | Every phase 1 metric computes from real files with lineage, golden datasets match |
| 4 | E4 Setup chat | Assumptions, questions, targets into settings | FR-8.1 to 8.5, FR-4.11, FR-10.4 | A company is set up with at most two questions |
| 5 | E5 Updates, approvals and comments | Updates, dated line, editing with Last edited, approval permission, comments, PDF export | FR-6.1 to 6.7, FR-3.3, 3.4 | An update goes out, an investor sees it and comments, an edit shows Last edited |
| 6 | E6 Commentary and number check | Skill 3, number check, voice setting | FR-5.5, FR-6.4, FR-10.3 | Commentary passes the check or a person writes the section |
| 7 | E7 Investor portfolio overview | Portfolio cards, eight measures, common thresholds, sort, drill-in, phase 2 labels | FR-7.1 to 7.8 | An investor with three companies sees them ranked by risk |
| 8 | E8 Billing entitlements | Entitlement keys, Stripe checkout and portal, warn or block switch | FR-9.1 to 9.4 | Entitlements are enforced as configured |
| 9 | E9 Web app and critical journeys | Built alongside E1 to E8; the six Playwright journeys | FR-1.4, FR-13.4 | All six journeys pass on a preview |
| 10 | E10 Hardening and beta | Load test, penetration test, restore drill, runbooks, alerts, privacy documents, beta with 5 to 10 companies | FR-12.3, 12.4, FR-13.2, FR-11.6 | Success measures in BRD chapter 1 met on the beta set |
| 11 | E11 Delivery, people and currency (phase 2) | Delivery and people files and measures, currency conversion with a rates feed, overview measures 6 and 7 | FR-1.3, FR-4.12, 4.13, FR-5.1 phase 2 rows, FR-7.5 | Flags on, the two measures show, mixed-currency files convert |

## Six critical journeys
1. Sign up and set up through the chat.
2. Upload a clean file and see tiles.
3. Upload a messy file and see tiles with at most one question.
4. Draft commentary that passes the number check.
5. Send an update and edit it.
6. Log in as an investor, see the portfolio, open a company, trace a figure and comment.

## Open decisions (do not decide in code)
See FRD chapter 14. Build behind a config switch where possible and record the choice needed in OPEN.md at the repo root.
