# E1 Foundations and tenancy: demo

**Done when:** a user creates a company, invites a colleague and an investor, every action is audited, and two-tenant tests pass.

## What to show (about 5 minutes)

1. Open the web app and choose **Create your company**. You are the Owner.
2. On the company page, invite an investor, then a department lead for Sales pipeline. Both appear under **Open invitations**.
3. In the API's terminal, copy the investor's invitation link (development prints emails there).
4. Open the link in a private window, create the investor's account, and land on the company. The investor sees the company and its investors, and nothing else.
5. Back as the Owner, refresh. **Activity** shows each step: created the company, sent and emailed each invitation, the investor accepting, and the investor viewing the company.
6. Remove the investor. Their next click is refused.
7. Run the tests and point at the two-tenant and role-matrix results.

## Run it locally

You need Python 3.12, Node 22 and Postgres 16 (or Docker).

```bash
# Database and queue
docker compose up -d

# API: migrate as the owner, then run as the app's own login role
cd backend
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt && pip install --no-deps -e .
MIGRATION_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/boardroom \
APP_DB_PASSWORD=br_login alembic upgrade head
DATABASE_URL=postgresql://br_login:br_login@localhost:5432/boardroom \
uvicorn boardroom.gateway.app:app --reload --port 8000

# Web app, in another terminal
cd web && npm install && npm run dev
```

Open http://localhost:5173. In development, events are delivered straight after each request, so the worker is not needed. To run it anyway: `celery -A boardroom.worker:celery_app worker --beat` with `DISPATCH_INLINE=false`.

## Run the tests

```bash
cd backend
TEST_ADMIN_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres pytest
```

The tests create a `boardroom_test` database, migrate it and connect as `br_login`, the same way production does. Row-level security is tested against a real Postgres, never assumed.

## Requirements covered

| FR | Status | Proved by |
|---|---|---|
| FR-2.1 to 2.9 | Done | `tests/test_identity.py` |
| FR-2.6 | Done | `tests/test_two_tenant.py`: every company endpoint, every role, plus a database-level check of every table |
| FR-10.1 | Done | `tests/test_architecture.py` reads `render.yaml`: only the API and the static site are public |
| FR-10.7 | Done | `tests/test_events.py`: a redelivered event is processed once; a failed consumer is retried |
| FR-11.1 | Done | `tests/test_policies.py`: every table has row-level security and an app policy. Tenant rows need active membership, not just a tenant ID. |
| FR-11.2 | Done | `tests/test_role_matrix.py`: the matrix is generated from the routes and passes at 100% |
| FR-11.5 | Done | `tests/test_audit.py`: every state-changing endpoint writes its event; the log refuses updates and deletes |
| FR-11.8 | Gate in place | CI proves gitleaks catches a seeded secret, then scans the repository and its history. Rotation is a runbook item for E10. |
| FR-12.1 | Done | `tests/test_architecture.py`: every resource in Frankfurt |
| FR-12.2 | Partly | Automatic pull-request previews are configured. Staging is not yet defined (see OPEN.md). Not yet applied on Render. |
| FR-12.3 | Not started | Point-in-time recovery and the restore drill are E10. |
| FR-12.4 | Partly | JSON logs carrying tenant ID and no data values (`tests/test_logs.py`), and `/healthz`. Error tracking and alerts are E10. |
| FR-13.1 | Partly | CI runs lint, types, tests, the API contract check, bandit, pip-audit, npm audit and gitleaks. End-to-end tests on previews come with E9. |

Also in place: phase 2 flags off by default (FR-1.3), the investor portfolio refuses company-only users (FR-7.7), and the copy check that enforces the CLAUDE.md wording rules.

## Not yet

- Email is not sent in production until a provider is chosen (OPEN.md).
- No password reset, email verification or MFA (OPEN.md, authentication).
- The Blueprint has not been applied to a Render workspace.
