# Open decisions

Decisions the code does not make. Each is built behind a setting or a default that is easy to change. Listed by the epic that raised it.

## From FRD chapter 14

| Decision | Blocks | What the code does now | Where |
|---|---|---|---|
| Service count: separate services or one app plus a worker | FR-10.2, FR-12.2 | One app plus a worker, as CLAUDE.md says. Modules keep their own Postgres schema and never read each other's tables, which a test enforces, so a split later is mechanical. | `render.yaml`, `backend/boardroom/modules/` |
| What a removed investor keeps | FR-2.8 | Nothing. Removal stops all access on the next request. The setting has one allowed value until this is decided. | `REMOVED_INVESTOR_KEEPS` in `backend/boardroom/config.py` |
| Who builds it, and how many engineers | Timing | Not a code decision. | |

The rest of chapter 14 (file formats, row-selection filters, thresholds, sort rule, warn or block, named check, rates feed, first connector) belongs to later epics and is recorded when those epics start.

## Raised in E1

| Decision | Why it matters | What the code does now |
|---|---|---|
| Authentication: built in or a managed provider | The previous spec recommended a managed provider for passwords, MFA and email sign-in links. The FRD does not decide. | Email and password, Argon2 hashing, 15-minute access tokens and single-use refresh tokens, behind `identity.service`. No email verification, password reset or MFA yet. Swapping in a provider changes `sign_up`, `sign_in` and the token checks only. |
| Email provider | Invitations need to be emailed. Also a subprocessor to list. | `MAILER=console` prints emails in development. Staging and production must run `MAILER=disabled`, which sends nothing and logs that an email was due (never its link). Until a provider is chosen, invitations can be created in production but the person is not emailed. |
| Database role per module | FR-11.1 asks for a role per module. | One app role (`br_app`) and one system role (`br_system`), both under row-level security. Per-module roles follow the service-count decision. |
| Migration credentials | The API and worker hold the database owner URL so the pre-deploy step can migrate. | Least privilege would move migrations to a separate job with its own secret. Worth doing when the service count is settled. |
| Render plans and staging | Full-stack previews and isolated staging need the Pro workspace. Plan names in `render.yaml` are first guesses. | `render.yaml` defines production with automatic pull-request previews. Staging is not yet defined. Confirm plan names and sizes when the Blueprint is first applied. |
| Product name | The pack says BoardRoom.io; the repository is brdrm.io. The design system calls the name a working name. | The app says BoardRoom.io everywhere. |
