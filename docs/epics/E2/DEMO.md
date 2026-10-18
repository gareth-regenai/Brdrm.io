# E2 AI file intake: demo

**Done when:** real messy finance and pipeline files are understood with no correction at the agreed rate.

That rate is not agreed yet (OPEN.md). What is proven: the code around the model does what the FRD says, using recorded model answers. The model's own accuracy is measured by `evals/skill1_eval.py` against the real API, which has not been run yet.

## What to show (about 8 minutes)

1. Sign in as the Owner and drop `backend/tests/fixtures/files/xero_pnl.csv` onto **Add files**. It moves through Received, Understanding, Calculating, Describing and Ready. It reads as Finance, 6 rows, data true as of 30 September 2026. The months across the top became six monthly figures.
2. Drop `finance_ambiguous.csv`. It stops at one plain question: "Is the column "Balance" your cash balance?". The same question arrives by email. Answer Yes and it finishes.
3. Drop `finance_ambiguous.csv` again. No question this time: the answer was saved to the layout.
4. Drop `team_with_pay.csv`. It is accepted. Salary, bonus, NI numbers, dates of birth, sort codes and personal emails are gone before anything is stored, including two columns with innocent names ("Ref", "Code") caught by their contents. People figures wait for phase 2.
5. Drop any CSV the model has no answer for (in the demo, anything not in `tests/fixtures/recorded`). Choose its columns by hand, the fallback for when the AI is off or unavailable.
6. Enter a target by hand. It shows "Entered by [name], [date]".
7. Show the tests, especially the hostile file set and the pay-data test.

## Run it locally

As in `docs/epics/E1/DEMO.md`, then upgrade the database and start the API with replayed model answers:

```bash
cd backend
pip install -r requirements-dev.txt && pip install --no-deps -e .
MIGRATION_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/boardroom \
APP_DB_PASSWORD=br_login alembic upgrade head
DATABASE_URL=postgresql://br_login:br_login@localhost:5432/boardroom \
SKILL1_REPLAY_DIR=$PWD/tests/fixtures/recorded \
uvicorn boardroom.gateway.app:app --reload --port 8000
```

With `ANTHROPIC_API_KEY` set instead of `SKILL1_REPLAY_DIR`, the real model reads the files. With neither, every upload goes to the manual mapping screen.

Run the eval against the real model (costs a few API calls):

```bash
ANTHROPIC_API_KEY=... python -m evals.skill1_eval
```

## Requirements covered

| FR | Status | Proved by |
|---|---|---|
| FR-3.1 | Done | Each state change is shown in the app and written as an outbox event and audit entry. Calculating and describing pass straight through until E3 and E6. |
| FR-3.2, FR-4.6 | Done | `test_an_ambiguous_cash_column_asks_exactly_one_question`: one question, in the app and by email, answered to finish |
| FR-4.1 | Done | Xero, QuickBooks, HubSpot (CSV) and Pipedrive (.xlsx) shaped exports. Direct-to-storage signed link (S3 presigned PUT in production) |
| FR-4.2 | Done | `test_profile_matches_hand_checked_values` |
| FR-4.3, FR-11.4 | Done | Payload holds a profile and 15 redacted rows, never the file. Out-of-schema answers are rejected (5 cases). Injection cells stay inside the data block or are redacted. |
| FR-4.4, FR-11.3 | Done | `test_pay_columns_leave_no_trace`: no pay value or header in storage, the database, AI payloads or the internal log. Raw upload deleted. |
| FR-4.5 | Done | Same file and layout give the same dataset fingerprint |
| FR-4.7 | Done | A second upload with the same headers asks nothing and does not call the model. Month headers are normalised, so next month's P&L matches. |
| FR-4.8 | Done | Hand-entered figures with the "Entered by" label. The click view itself is E3. |
| FR-4.9, FR-10.6 | Done | With the AI off, a person maps the columns and the file still produces a dataset |
| FR-4.10 | Done | Company endpoints carry no interpretation; the app role cannot read the log; platform admins can |
| FR-4.11 | Partly | Targets can be entered by hand, and a budget file is read as Plan. "No plan set" on tiles is E3; targets from the setup chat are E4. |
| FR-4.12 | Done | A people file uploads and is told figures arrive in phase 2 |
| FR-11.7 | Done, scanner open | Size, row, column and cell limits; parsing in a separate process with memory and CPU limits; zip bomb, old .xls, binaries, the antivirus test file, empty and binary-content files all refused safely; formula cells neutralised on export. The real malware scanner is open (OPEN.md). |
| FR-13.2 | Done | CI uses recorded answers and has no API key; the real-model eval runs on a schedule only when enabled |

142 backend tests pass.

## Not yet

- The real model has not been run against these files. Run the eval with an API key before trusting the rate.
- Storage, the scanner and the raw-upload retention rule need decisions before production (OPEN.md).
