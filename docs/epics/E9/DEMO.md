# E9 Web app and critical journeys: demo

**Done when:** all six journeys pass on a preview.

The journeys pass on every pull request in CI, against the whole app started there. Render previews are not connected yet, so "on a preview" waits for that (see OPEN.md).

## Run it

You need Postgres running, the backend installed (`backend/.venv`) and `npm ci` done in `web`.

```bash
ADMIN_URL=postgresql://postgres:postgres@localhost:5432/postgres \
PYTHON=backend/.venv/bin/python scripts/e2e-stack.sh
cd web && npx playwright test          # add --headed to watch, or --ui to step through
```

`scripts/e2e-stack.sh` makes a fresh `boardroom_e2e` database, starts the API with recorded AI answers and the capture mailer, and serves the built web app on port 4173. It changes the `br_login` password, so restart a local dev server afterwards. Where Chromium is already installed, set `PW_CHROMIUM` to it.

## The six journeys (`web/e2e/journeys.spec.ts`)

| Journey | What the test does |
|---|---|
| 1. Set up through the chat | Signs up, answers the two questions, agrees to invite the investor it named, sees "That's everything" and "£75k a month", and the invitation email arrives. Next visit the dashboard is clear |
| 2. Upload a clean file and see tiles | Adds a raw Xero export: no question, a Revenue tile in £, and its click view with the exact value |
| 3. Upload a messy file, at most one question | Adds an ambiguous export: exactly one question, answered with one click, then tiles |
| 4. Commentary that passes the number check | The board pack shows "Drafted by Claude" and "Number check: passed", and the headline uses the real figure |
| 5. Send an update and edit it | Approves and shares, changes Revenue, and sees "Last edited" and "Changed by" |
| 6. The investor | From a raw finance export and a raw deals export (FR-1.4): the CEO shares both and invites an investor by email. The investor follows the email link, signs up, sees the company on the portfolio, opens it, traces Revenue, sees the pipeline, has no approve or change buttons, and comments. The CEO sees the comment |

## What the journeys found

- On the dashboard, the setup chat vanished the moment the last question was answered, so the CEO never saw the "Invite these investors?" question or the closing words, and the investor was never invited. Fixed: setup finished on this visit stays on screen.
- With no files yet, the chat said "I've read your files". It now says it will work out the rest from the first file.

## Seeded defects

Each was put in on purpose and caught, then taken out:

- Showing investors the "Change" button on a figure: journey 6 fails.
- The setup chat vanishing when done: journey 1 fails.

## Requirements covered

| FR | Status | Proved by |
|---|---|---|
| FR-13.4 | Done in CI; on previews once Render is connected | The six journeys above, in the `journeys` CI job, which runs after the backend and web checks |
| FR-1.4 | Done | Journey 6: sign-up to an update the investor sees, from raw exports, no template |
| FR-13.1 | Done except the preview step | Lint, types, unit and integration tests, contract, security scans, then the journeys. A seeded defect fails each |
| FR-13.2 | Done | The journeys replay recorded AI answers; the stack starts with no AI key |
