# Runbooks

What to do when something goes wrong. Each alert email names one of these. Keep each fix to the steps here; if they do not work, stop and escalate rather than improvise on production data.

Alerts are checked every 5 minutes by the worker and emailed to `OPS_ALERT_EMAIL`, at most once an hour each. They are also in the logs as `"event": "alert"`.

## Alert: queue

**Means:** events or files have waited longer than `ALERT_QUEUE_MINUTES` (10). Customers see files stuck at Understanding, Calculating or Describing, and emails arrive late.

1. In Render, open **boardroom-worker**. Is it running? If it crashed or is restarting, read the last error in its logs.
2. Is **boardroom-queue** (Key Value) up? The worker cannot take jobs without it.
3. Restart the worker. Nothing is lost: events wait in each module's outbox and are sent once, and a file already past a step is left alone.
4. If one file keeps failing, the logs name its route and error type, never its contents. Open a support session on the company (below) to look, and tell the company if the file needs exporting again.

## Alert: ai_errors

**Means:** the AI failed on at least a quarter of files in the last hour (`ALERT_AI_ERROR_RATE`, once there are `ALERT_AI_MIN_CALLS`). Nothing is wrong with the figures: those files went to "Choose what each column is", so customers have more to do.

1. Check the AI provider's status page.
2. Check `ANTHROPIC_API_KEY` is set on the API and the worker, and has not run out of credit.
3. If the model named in `SKILL1_MODEL` was retired, set it to a current one and redeploy. Run the skill 1 eval (`.github/workflows/skill-evals.yml`) before trusting it.

## Alert: login_failures

**Means:** `ALERT_LOGIN_FAILURES` (20) failed sign-ins in 15 minutes, across all accounts. Likely someone guessing passwords.

1. In the logs, look at `auth.login_failed` in the audit log: one account, or many?
2. One account: tell the person, and suggest a new password.
3. Many accounts from a few places: block them at Render or the network edge. Do not lock accounts in bulk; that locks real customers out.

## Restore the database

Render keeps point-in-time recovery on the paid Postgres plans (FR-12.3).

1. In Render, open **boardroom-db**, choose **Recovery**, and restore to a new database at the time just before the problem.
2. Point the API and worker at the restored database, restart both, and check `/healthz` and one company's board pack.
3. Tell affected companies what time their data was restored to. Files added after that time need adding again.

Practise this before launch and after any change to the database plan: `scripts/restore-drill.sh` backs up a database, restores it into a fresh one, compares every table row for row, and prints how long the restore took.

## Rotate a secret

1. Create the new value (a new API key, SMTP password or storage key) with the provider.
2. Set it in Render on every service that uses it (see `render.yaml`), then redeploy.
3. Revoke the old value with the provider.
4. `JWT_SECRET`: rotating it signs everyone out. Do it outside working hours and tell customers first.

## Look into a company's account

Use a support session, never the database (FR-11.6).

1. `POST /admin/support/{tenant_id}` with a reason the customer will read.
2. The company sees who, why and until when, and can end it. Every page you open is in their audit log.
3. It ends after `SUPPORT_SESSION_MINUTES` (60).
