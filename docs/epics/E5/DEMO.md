# E5 Updates, approvals and comments: demo

**Done when:** an update goes out, an investor sees it and comments, and an edit shows "Last edited".

## Run it

As in `docs/epics/E2/DEMO.md`, then `alembic upgrade head` again for the updates tables. Emails print in the API's terminal (`MAILER=console`), which is where the investor's invitation link comes from.

## What to show (about 5 minutes)

1. Sign up as Sam Hart for Kestrel Field, skip setup, and add `xero_pnl.csv` from `backend/tests/fixtures/files`.
2. Under **Updates**: "Owner Sam Hart added new financials. Data true as of 30 Sep 2026. Subject to change and may be edited." It is marked **Awaiting approval**, with revenue, revenue growth, gross margin and net monthly burn from that file. Investors cannot see it yet, in the API or in the database.
3. **Approve and share**. It now reads "Approved by Sam Hart", and the upload's last step is **Shared**. Every investor is emailed.
4. Invite an investor. Open the link from the API's terminal and sign up as them. They see the update, open **Source** on revenue to see the formula and the rows used, and comment "Is the Q4 pipeline all enterprise?". Sam is emailed.
5. As Sam, reply. The investor is emailed. Then **Change** revenue to 80000. The update shows "Last edited 18 Oct 2026 by Sam Hart", and the figure says "Changed by Sam Hart. Calculated: £72.9k". The investor sees the same, and the audit log holds the value before and after.
6. **Download PDF**: the company name on its colour, its logo if one is set in **Settings**, the dated line, the labels and each figure with its source.
7. In **Settings**, give a department lead approval: they now see **Approve and share**. Take it away: they do not.

## Requirements covered

| FR | Status | Proved by |
|---|---|---|
| FR-6.1 | Done | A finished P&L makes one update recording who added it, the department, the data-as-of date and the time |
| FR-3.4 | Done | The dated line reads "CEO ceo person added new financials. Data true as of 30 Sep 2026. Subject to change and may be edited." |
| FR-3.3 | Done | Before an approver acts, the investor's list is empty and the update's figures, PDF and comments return 404. Row-level security hides it from an investor's database session too. After approval the investor sees it |
| FR-6.3, FR-2.7 | Done | A department lead cannot approve until the company's setting names them, and then can, and sees the action |
| FR-2.3 | Done | An investor invited after an update was shared sees it with no further action |
| FR-6.2 | Done | Editing revenue shows "Last edited" to the investor, the figure shows who changed it and the calculated value, and the audit entry holds before and after. Department leads edit only their own departments; contributors and investors cannot edit |
| FR-6.5 | Done | An investor's comment emails the CEO and Owner; the CEO's reply emails the investor. A comment on an unshared update emails no investor |
| FR-6.6 | Done | The PDF matches its byte snapshot; a file name starting "=" is printed with a leading quote and markup is printed as text, while a negative figure prints as it is |
| FR-6.7 | Done | Each figure in an update opens the same lineage as the company's tiles, plus who changed it in the update |
| FR-3.1 | Done | An upload moves to Shared when its update is approved |
| FR-6.4 | E6 | The voice setting exists from E4; "Drafted by Claude" arrives with commentary |

## Not yet

- Commentary (E6). An update holds figures only.
- The six Playwright journeys run on previews from E9. "Send an update and edit it" was run by hand in a browser for this epic.
