# E10 part 2: alerts and the restore drill

## Alerts (FR-12.4)

**Accept:** each alert fires in a staged fault test.

The worker checks three signals every 5 minutes (`boardroom/ops.py`). An alert is logged at error level as `"event": "alert"` and emailed to `OPS_ALERT_EMAIL`, at most once an hour each. What to do for each is in `docs/runbooks.md`.

| Alert | Fires when | Setting |
|---|---|---|
| queue | Events or files have waited over 10 minutes | `ALERT_QUEUE_MINUTES` |
| ai_errors | The AI failed on a quarter or more of files in the last hour, once there are at least 4 | `ALERT_AI_ERROR_RATE`, `ALERT_AI_MIN_CALLS` |
| login_failures | 20 failed sign-ins in 15 minutes, across all accounts | `ALERT_LOGIN_FAILURES` |

Unexpected errors are logged as `unhandled_error` with the error's type and route, never its message, which can hold a value from a file. The person sees a plain "Something went wrong on our side".

### Proved by (`backend/tests/test_ops.py`)

- A healthy system with a file processed raises nothing.
- An event left waiting 20 minutes, and a file stuck at Calculating for 30, each raise **queue**.
- 2 of 4 and 1 of 4 AI failures raise **ai_errors**; 1 of 5 does not, and 3 of 3 is too few to judge.
- Three real failed sign-ins through the API raise **login_failures** at a threshold of 3; two do not.
- An alert is emailed once, not on every check.
- Every module's outbox is watched, so a new module cannot be missed.
- An error whose message holds "Revenue 48,213.07 for Harbour Robotics" is logged with neither.
- Seeded defects caught: files not counted, the AI rate off by one, emailing on every check, and counting the wrong audit action.

## Restore drill (FR-12.3)

**Accept:** a timed restore to staging succeeds.

`scripts/restore-drill.sh` backs up a database, restores it into a fresh one, fingerprints every table (row count and a checksum of every row) on both, and reports how long the restore took.

Run locally on the development database: **passed, 36 tables, 2,252 rows, restored in 0.5 seconds.** Changing one value in the restored copy changes that table's checksum, so a bad restore is caught.

Still to do once Render is connected: run it against staging and record the time, and switch on point-in-time recovery on the production database plan.

## Runbooks

`docs/runbooks.md`: one page per alert, restoring the database, rotating a secret, and looking into a company's account with a support session.
