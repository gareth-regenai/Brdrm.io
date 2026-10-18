# Open decisions

Decisions the code does not make. Each is built behind a setting or a default that is easy to change. Listed by the epic that raised it.

## From FRD chapter 14

| Decision | Blocks | What the code does now | Where |
|---|---|---|---|
| Service count: separate services or one app plus a worker | FR-10.2, FR-12.2 | One app plus a worker, as CLAUDE.md says. Modules keep their own Postgres schema and never read each other's tables, which a test enforces, so a split later is mechanical. | `render.yaml`, `backend/boardroom/modules/` |
| What a removed investor keeps | FR-2.8 | Nothing. Removal stops all access on the next request. The setting has one allowed value until this is decided. | `REMOVED_INVESTOR_KEEPS` in `backend/boardroom/config.py` |
| Who builds it, and how many engineers | Timing | Not a code decision. | |

| File formats beyond CSV and Excel, such as PDF | FR-4.1 | CSV (any delimiter, UTF-8, UTF-16 or Windows-1252) and .xlsx. Old .xls, PDF and others get a plain message asking for CSV or .xlsx. | `backend/boardroom/modules/intake/parsing.py` |

The rest of chapter 14 (row-selection filters, thresholds, sort rule, warn or block, named check, rates feed, first connector) belongs to later epics and is recorded when those epics start.

## Raised in E1

| Decision | Why it matters | What the code does now |
|---|---|---|
| Authentication: built in or a managed provider | The previous spec recommended a managed provider for passwords, MFA and email sign-in links. The FRD does not decide. | Email and password, Argon2 hashing, 15-minute access tokens and single-use refresh tokens, behind `identity.service`. No email verification, password reset or MFA yet. Swapping in a provider changes `sign_up`, `sign_in` and the token checks only. |
| Email provider | Invitations need to be emailed. Also a subprocessor to list. | `MAILER=console` prints emails in development. Staging and production must run `MAILER=disabled`, which sends nothing and logs that an email was due (never its link). Until a provider is chosen, invitations can be created in production but the person is not emailed. |
| Database role per module | FR-11.1 asks for a role per module. | One app role (`br_app`) and one system role (`br_system`), both under row-level security. Per-module roles follow the service-count decision. |
| Migration credentials | The API and worker hold the database owner URL so the pre-deploy step can migrate. | Least privilege would move migrations to a separate job with its own secret. Worth doing when the service count is settled. |
| Render plans and staging | Full-stack previews and isolated staging need the Pro workspace. Plan names in `render.yaml` are first guesses. | `render.yaml` defines production with automatic pull-request previews. Staging is not yet defined. Confirm plan names and sizes when the Blueprint is first applied. |
| Product name | The pack says BoardRoom.io; the repository is brdrm.io. The design system calls the name a working name. | The app says BoardRoom.io everywhere. |

## Raised in E2

| Decision | Why it matters | What the code does now |
|---|---|---|
| The agreed rate for "understood with no correction" | E2's done-when line and BRD chapter 1 both depend on it. | `evals/skill1_eval.py` measures it against the real model, with a 90% threshold as a placeholder. Today's labelled set is 7 invented files in real export shapes. The rate means something once real, anonymised beta files are added. |
| Object storage provider | FR-12.1 says UK or EU, versioned and private. | Any S3-compatible bucket (`STORAGE_BACKEND=s3`). The previous spec recommended AWS S3 in London. |
| Raw uploads and bucket versioning | FR-4.1 sends files straight to storage, FR-4.4 says pay data is never stored, and FR-12.1 wants versioning. Versioning would keep a deleted raw file. | Raw files land under `quarantine/` and are deleted as soon as the pay-free copy is written. That prefix needs a lifecycle rule that expires old versions within a day, or a separate unversioned bucket. Needs your sign-off. |
| Malware scanner | FR-11.7 asks for a scan before parsing. | `SCANNER=clamav` talks to a ClamAV service; `basic` (the current Blueprint value) only refuses the antivirus test file and executables, which is not a real scan. Choose ClamAV as a private service or a scanning API before launch. |
| Wide profit and loss layouts | Most finance exports put months across the top. The FRD's closed transform list works column by column. | Skill 1 can also answer "periods as columns" and map line items instead of columns. Code does the reshaping. This adds to the closed list, so it needs agreement. |
| Which columns count as pay-like | FR-4.4 lists the categories, not the words. | Dropped by name: salary, wage, pay, bonus, commission, bank details, sort code, account number, IBAN, NI number, date of birth, personal email, home address, tax code. Dropped by content: NI numbers, sort codes, IBANs, columns of mostly personal email addresses. A company-level "Wages" total in a long-format file is also dropped, which errs towards privacy. Names and phone numbers are kept but redacted before the AI sees samples. |
| More than one uncertain column | FR-3.2 says one question. | The least certain column that blocks a figure is asked about. Other uncertain columns between 0.5 and 0.8 keep the AI's best guess; below 0.5 they are ignored. |
| Model for skill 1 | Cost and accuracy. | `claude-sonnet-5-5` at medium effort, as the spec names, with server-side fallback if a request is refused. Switch with `SKILL1_MODEL`. The eval is how to compare. |
| Agent Skills path (FR-10.5) | The spec describes skills uploaded through the Skills API with code execution, and a per-tenant switch to a Messages-only path. | Only the Messages-only path is built: structured outputs, no tools, no code execution. It fits "no AI-written code is ever run" and zero data retention. The Skills API path is not built. |
