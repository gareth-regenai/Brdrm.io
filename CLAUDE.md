# BoardRoom.io

BoardRoom.io turns the files a small company already has into figures its investors can trust and trace. This repo is the MVP build.

## Read first
- docs/02-BRD.md: what the business needs, by chapter (BR-x.y).
- docs/03-FRD.md: what the system must do, with acceptance criteria (FR-x.y). Build to these.
- docs/01-MVP-spec-revised-with-changes.md: the full spec, with changes from the previous version marked and the reasoning.
- docs/04-Decisions-log.md: the decisions behind the spec.
- docs/05-Epics-and-build-order.md: the epics and the order to build them in.
- design-system/README.md and design-system/tokens.json: the brand. Use the tokens, never hard-coded colours.
- mockup/: the v5.7 mockup and example screens. Match them.

## Principles that override everything else
1. AI-native. The AI reads whatever a company uploads and chooses the data. Templates are guidance, never a gate. Before building any rule, rejection or required field, answer: why can't the AI handle this? If there is no good reason, do not build it.
2. Code does every calculation. Each measure has a fixed formula in the metric registry. The AI only selects which rows feed it, from a closed set of filters. No AI output is ever stored or shown as a figure, and no AI-written code is ever run.
3. Nothing can be out. A figure in commentary must be normal rounding of the real figure. The exact value is one click away. There is no tolerance band.
4. Low friction. The customer prepares nothing. Ask a person a question only when a figure cannot be calculated without the answer.
5. Keep it simple. No locking, no versioning, no per-pack grants. An update is a dated line that can be edited and shows "Last edited". If a proposed design adds process, stop and check the FRD.

## Hard rules
- Pay-like columns (salary, bonus, bank details, national insurance numbers, dates of birth, personal emails) are dropped at intake, never stored, never sent to the AI. The rest of the file is kept.
- Tenant isolation: tenant ID on every row, Postgres row-level security, two-tenant tests on every endpoint.
- Company users see their own company only. Investors see every company that invited them and only view and comment.
- Every figure stores lineage: formula version, dataset version, rows used, or the person and date for a hand-entered figure.
- Phase 2 features (product delivery, people, currency conversion) sit behind feature flags, off in phase 1.
- British English, sentence case, no em-dashes anywhere (code comments, UI copy, docs). Say "organisation", "analyse", "£".
- UI copy follows design-system/README.md: lead with the number, say who did what ("Drafted by Claude", "Approved by the CEO"), never "AI-powered" or "smart".
- This product is separate from any other business. No content, fonts, colours or copy from other projects.

## Stack
Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, Celery with Render Key Value, Postgres, S3-compatible storage, React single-page app. Hosted on Render, Frankfurt. See FRD chapters 10 to 12. Service count is an open decision: default to one app plus a worker, split later.

## Working method
- One epic at a time, in the order in docs/05-Epics-and-build-order.md.
- Every FR is done only when its acceptance line is proven by a test in CI.
- AI calls in tests use recorded responses. Never call the live API from CI.
- End each epic with a working demo. Write a short DEMO.md in the epic's folder saying how to run it.
- Open decisions (FRD chapter 14) are not yours to make. Build behind a config switch where possible and list the decision in OPEN.md.
