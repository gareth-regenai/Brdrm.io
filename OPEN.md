# Open decisions

Decisions the code does not make. Each is built behind a setting or a default that is easy to change. Listed by the epic that raised it.

## From FRD chapter 14

| Decision | Blocks | What the code does now | Where |
|---|---|---|---|
| Service count: separate services or one app plus a worker | FR-10.2, FR-12.2 | One app plus a worker, as CLAUDE.md says. Modules keep their own Postgres schema and never read each other's tables, which a test enforces, so a split later is mechanical. | `render.yaml`, `backend/boardroom/modules/` |
| What a removed investor keeps | FR-2.8 | Nothing. Removal stops all access on the next request. The setting has one allowed value until this is decided. | `REMOVED_INVESTOR_KEEPS` in `backend/boardroom/config.py` |
| Who builds it, and how many engineers | Timing | Not a code decision. | |

| File formats beyond CSV and Excel, such as PDF | FR-4.1 | CSV (any delimiter, UTF-8, UTF-16 or Windows-1252) and .xlsx. Old .xls, PDF and others get a plain message asking for CSV or .xlsx. | `backend/boardroom/modules/intake/parsing.py` |

| The closed filter set for row selection | FR-5.2 | Four filters: in, not in, is empty, not empty, on the dataset's own fields and only with values the dataset holds. Defined once in `backend/boardroom/modules/metrics/selection.py`. | `FILTER_OPS` |
| Default High, Medium and Low thresholds | FR-5.7, FR-7.2, FR-7.3 | Placeholders: runway high below 6 months, medium below 12; gross margin 20% / 40%; revenue growth -5% / 0%; revenue against plan 80% / 95% of target; coverage 1x / 2x; win rate 15% / 25%; stalled deals above 30% / 15% of open deals. Cash, burn, pipeline and deal size carry no level. Companies can change their own. | `DEFAULT_THRESHOLDS` in `backend/boardroom/modules/metrics/display.py` |
| Overview sort rule | FR-7.3 | The proposed rule: most High measures first, then most Medium, then shortest runway, then name. A company with no runway shared sorts after those with one. | `overview` in `backend/boardroom/modules/updates/service.py` |
| Limits warn or block | FR-9.4 | Warn: the action goes through, the person sees "Your plan includes 3 investors. This went through.", and `billing.limit_passed` is audited. `block` refuses it with the same sentence. Both are tested. | `LIMIT_BEHAVIOUR` in `backend/boardroom/config.py` |
| Named check on cash, burn and runway before sharing | FR-3.3, FR-6.3 | Not built. An update is shared when one approver approves it, under the company's approval setting (default the CEO). A named tick on these three figures would be a second step in `approve`, and needs the decision before it adds process. | `approve` in `backend/boardroom/modules/updates/service.py` |

The rest of chapter 14 (rates feed, first connector) belongs to later epics and is recorded when those epics start.

## Raised in E1

| Decision | Why it matters | What the code does now |
|---|---|---|
| Authentication: built in or a managed provider | The previous spec recommended a managed provider for passwords, MFA and email sign-in links. The FRD does not decide. | Email and password, Argon2 hashing, 15-minute access tokens and single-use refresh tokens, behind `identity.service`. No email verification, password reset or MFA yet. Swapping in a provider changes `sign_up`, `sign_in` and the token checks only. |
| Email provider | Invitations and questions need to be emailed. Also a subprocessor to list. | Decided for now: plain SMTP (`MAILER=smtp`), so an existing mailbox can send without a new account. See docs/email.md. A dedicated sending service (better deliverability, bounce handling) can replace it later by changing the SMTP settings only. Sending from a RegenAI mailbox would mix the two businesses, which CLAUDE.md rules out, so use a separate BoardRoom address. |
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

## Raised in E3

| Decision | Why it matters | What the code does now |
|---|---|---|
| Periods for sales measures | The FRD says "for the period" without defining it. | Win rate and average deal size use deals closed in each calendar month. Pipeline, weighted pipeline, coverage and stalled deals are a snapshot at the latest sales data. Coverage compares deals expected to close this month with this month's closed-won target. A quarterly view would need agreeing. |
| Runway with fewer than three months | The formula averages the last three months of burn. | Runway shows only when three months of burn are known; otherwise "Not provided". |
| Company-specific methods | FR-5.3 allows one only where the standard formula cannot work. | One so far: net burn from the fall in cash when the profit and loss lines are missing. It is flagged on the tile, in the click view and in the database, which refuses an unflagged one. Others need agreeing as they come up. |
| Deals in another currency | Conversion is phase 2. | Rows in a currency other than the company's are left out of sales figures, and the click view says how many. The reporting currency is GBP until the setup chat (E4) sets it. |
| Targets from a plan file | FR-4.11. | Hand-entered targets are used first. From a plan file, rows whose metric reads revenue, sales, income or turnover are revenue targets, and closed won, bookings or new business are sales targets. The setup chat (E4) will capture targets in conversation. |
| Display precision for cash | BRD chapter 5 sets money precision by annual revenue. | Applied to every money figure, so a £800k-revenue company sees cash of £1.19m as £1,194.5k. Each company can move a measure one step either way. |

## Raised in E4

| Decision | Why it matters | What the code does now |
|---|---|---|
| What "no figure value changes because of a chat message" means | FR-8.5's acceptance line, read literally, conflicts with FR-4.11: a target set in the chat changes "revenue against plan". | The chat has no way to write a figure: its output schema holds settings, targets and investor emails only, and a test proves an attempt to change revenue in conversation changes nothing. Plan figures do recalculate from a new target, by code. |
| Which questions the chat may ask | FR-8.3 says "usually targets and investor emails". | Code decides: targets if none are known from a budget file, the chat or settings; investors if none are invited. Never more than two. Currency and what the business does are assumed, not asked. |
| Reading the company's website | FR-8.1 wants what the business does "from its website". | Guessed from the CEO's email domain (not free mail), or set in settings. Our server reads it over https only, refuses private network addresses on every redirect, and keeps at most 3,000 characters of title, description and text. A determined attacker could still try DNS tricks between the check and the fetch; a fetch proxy would close that. |
| Model for the setup chat | Cost and quality. | `claude-sonnet-5-5`, like the skills, switchable with `SETUP_MODEL`. Without a key, or if the model fails, code runs the same interview: it reads amounts, email addresses, skips and "we report in euros" itself, and asks again when it cannot. |
| A yearly revenue target | The interview asks "What are you aiming for in revenue this year?", as in the mockup, but revenue against plan is monthly. | A yearly answer is split into twelve equal months of this year, and the acknowledgement says so ("£5.4m this year, so £450k a month"). A monthly answer applies to the next twelve months. Seasonal targets can be set month by month in settings or from a budget file. |
| Investor invitations from the chat | Inviting emails a third party. | The chat collects addresses the CEO typed; nothing is sent until the CEO presses Send invitations. |

## Raised in E5

| Decision | Why it matters | What the code does now |
|---|---|---|
| "Data true as of" date | BRD 6.1 and FR-6.1 say "data true as of"; the decisions log says the upload date. A P&L to September added on 17 October is true as of 30 September, not 17 October. | The latest date in the data (month end for a P&L or budget, the latest past date for a deals list), and the upload date when the file has no dates. `UPDATE_AS_OF=upload` always uses the upload date. |
| PDF tooling | FR-6.6. The previous spec proposed WeasyPrint, which needs system libraries Render's native Python runtime may not have. | ReportLab, pure Python, behind `PDF_RENDERER`. Output is byte-for-byte repeatable, so the snapshot test compares exact bytes. Fonts are Helvetica; brand fonts would need font files bundled. |
| How the Owner is named in the dated line | FR-3.4 says "[Role] [Name]". The person who signs up is the Owner, often also the CEO. | "Owner Sam Hart added new financials". If founders should read as "CEO", the Owner could choose a title, or the Owner could also be given the CEO role. |
| What can be edited in an update | FR-6.2: "editing a figure". Commentary arrives in E6. | A figure in an update can be changed by an editor (Owner, CEO, or a department lead for their own department) and put back. The update then shows "Last edited", the figure shows "Changed by" with the calculated value, and its lineage names the person and date. The company's own tiles keep the calculated figure. |
| Emails beyond comments | FR-6.5 asks for comment notifications only. Without others, approvers and investors would not know an update exists. | Approvers are emailed when an update waits for them (not the person who added it), and investors when one is shared. Comment emails go to the Owner and CEO for an investor's comment, and to the company's investors for the company's reply on a shared update. |
| Phase 2 files and updates | FR-6.1 says each finished upload makes an update. Delivery and people files have no figures while their flags are off. | No update is made for them until the flag is on, so investors never get an empty update. |
| What an investor sees in a figure's source | The old mockup said investors never see raw files; FR-6.7 and the journeys say they trace a figure. | The same click view as the company: formula, inputs and the rows used (with pay columns already dropped at intake). Never the whole file. |

## Raised in E6

| Decision | Why it matters | What the code does now |
|---|---|---|
| Which numbers the check tests | FR-5.5: "ignores dates, quarters and counts of things". | A number is a figure when it has a unit: £, € or $, k, m or million, %, x, or months with a decimal (months are always written with one). Bare numbers are dates, years, quarters or counts and are ignored, as is a whole number of months ("the last 3 months"). |
| What a written figure may round to | The reference demo allowed differences between any two figures, which lets a wrong number through by chance. | The update's figures, last period's, the change between the two for the same measure, the money inputs a figure came from, and revenue as a share of target. Units must match: 2.4 as a ratio does not pass "2.4 months". Rounding is half up at the precision written. |
| A person's words and the check | BR-5: "every commentary figure passes the check, or the section is written by a person". | A person's text is checked too, and figures that match nothing are shown to the company as a warning. It is not blocked, because the person is the fallback. |
| Likely board questions | FR-10.3 asks skill 3 for them; nothing says who sees them. | Shown to the company only, to prepare. Hidden from investors in the API, the PDF and by row-level security. |
| A section that fails twice | The update could wait for it, or go out without it. | The update can still be approved. The section stays hidden from investors until a person writes it; a person can also leave it out. |
| Model for commentary | Cost and quality. | `claude-sonnet-5-5`, switchable with `COMMENTARY_MODEL`. |

## Raised in E7

| Decision | Why it matters | What the code does now |
|---|---|---|
| Levels for cash and net burn on the overview | FR-7.2 asks for a level on every measure, and the mockup shows them. An amount of cash means different things for companies of different sizes. | No level yet, as in the threshold placeholders. Runway already carries the risk of low cash. Set lines in `DEFAULT_THRESHOLDS` to add them. |
| Lines for "Last update" | FR-7.6 gives days since the last shared update; nothing sets its levels. | Placeholders matching the mockup: High above 35 days, Medium above 20 (`LAST_UPDATE_DAYS`). A company that has shared nothing shows "None yet" with no level. |
| Which lines an investor sees inside a company | FR-5.7 says a company's own lines apply on its own pages. The investor's view of a company is the company's section, but read by an investor. | The common lines, in the investor's tiles and click view as on the overview, so an investor judges every company the same way everywhere. The company still sees its own lines. |
| Where overview figures come from | An investor must only see what a company shared (FR-3.3). | Each measure is the most recently shared figure of that measure, as shared, including a change a person made in the update. Never the company's live tiles. |
| A runway that is not limited | A company spending less than it earns has no runway figure. | It shows "Not shared yet" on the overview for now, and sorts after companies with a runway. A "Cash generative" label would be clearer. |

## Raised in the v5.7 board pack

| Decision | Why it matters | What the code does now |
|---|---|---|
| Who an investor can tag | Tagging tells a person their name was used. Investors already see other investors' names (FR-2.5), not the whole team. | Investors can tag the Owner, the CEO, department leads and other investors. The company can tag anyone in it. Investors cannot be tagged on an update before it is shared. |
| What the company sees in its own pack | "The same view" for both sides, but the company also needs to see what is about to go out. | The company's pack includes updates awaiting approval, with each such figure marked "Awaiting approval" and a notice at the top. Investors see shared updates only. |
| Parts of v5.7 not built | v5.7 predates the revised spec. | Quarterly cycles, the stepper and "Submit for approval" are replaced by dated updates. Risk register and CEO development are left out until they have requirements. Spend, income and balance sub-pages, forward burn and stack optimisation need calculations the registry does not have yet. |

## Raised in E8

| Decision | Why it matters | What the code does now |
|---|---|---|
| Plans, prices and the value of each limit | Pricing is under commercial review (BR-9); the build must not hard-wire it. | No plan exists until a platform admin adds one (`PUT /admin/billing/plans/{key}`). With no plans, nothing is limited. Each plan holds a Stripe price id and a value for each key; changing one takes effect on the next request. |
| Which keys exist | FR-9.1 gives viewers, uploads_per_month and max_file_mb as examples. | Those three. `viewers` counts investors in the company plus open investor invitations, checked when an investor is invited. `uploads_per_month` counts files added this calendar month (UTC), not counting failed ones. `max_file_mb` can lower the size limit but never raise it above `MAX_FILE_MB`. A new key needs its check where the action happens. |
| Who manages billing | The FRD permissions table has no billing row. | The Owner and the CEO, as for company settings. Approval never depends on the plan (FR-9.3), which a test enforces. |
| A company whose payment lapses | Stripe retries a failed payment for a while before ending the subscription. | Active, trialing and past due keep the paid plan. Any other status, or no subscription, falls back to the default plan. Nothing is deleted. |
| Investor workspaces | Investors may one day pay for the portfolio view. | Billing applies to company workspaces only. Investors pay nothing and have no limits. |

## Raised in E9

| Decision | Why it matters | What the code does now |
|---|---|---|
| Journeys on Render previews | FR-13.4 asks for the journeys on every preview. Previews need Render connected. | The journeys run in CI against the whole app started by `scripts/e2e-stack.sh`. To run them on a preview: give the preview `ENVIRONMENT=staging`, `MAILER=capture` and the recorded AI answers, then run `npx playwright test` with `E2E_WEB_URL` and `E2E_API_URL` set to the preview. |
| How a journey reads an invitation email | The investor journey has to follow the link in a real email. | `MAILER=capture` keeps emails in storage and `GET /e2e/mail` returns them. The route exists only in capture mode, and production refuses `MAILER=capture` (tested). |

