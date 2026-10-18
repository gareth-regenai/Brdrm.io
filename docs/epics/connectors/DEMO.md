# Connected tools: demo

**Done when:** a company connects a tool and its data arrives, checked and calculated, with no export. Real tools are added one at a time on this framework.

Added at the CEO's request after E9: the customer journey first, the real connectors later. It is outside the original epics, and choosing the first real connector is still open (FRD chapter 14), so no real tool is connected yet.

## Run it

As in `docs/epics/E5/DEMO.md`, with `CONNECTORS_DEMO=true` on the API and worker, then `alembic upgrade head` for migration 0009. Or run the journey: `scripts/e2e-stack.sh`, then `cd web && npx playwright test tools`.

## What to show (about 3 minutes)

1. Sign in as the Owner or CEO and open **Files**. **Your tools** lists each tool and what it sends. Xero, QuickBooks, HubSpot and Pipedrive say "Coming soon". Jira, monday.com and HiBob say "Phase 2".
2. Choose **Connect Demo company**. It pulls straight away: two files appear, "Demo company: profit and loss" and "Demo company: deals". Each goes through the same steps as an uploaded file, and the figures and two updates appear.
3. **Pull now** again: "Last pulled" moves on, and nothing is added, because nothing changed.
4. The worker pulls each connected tool once a day, as the person who connected it. If that person stops managing the company's tools, the tool shows "Needs attention" with the reason, and the dashboard says so.
5. **Disconnect**: pulls stop, and what already arrived stays.

## How a real connector is added

1. Register a developer app with the tool and keep its client id and secret in Render.
2. Add a sign-in step: the company signs in to the tool once, read-only, and the access is stored encrypted for that company.
3. Write its `pull`: fetch the data and hand back CSV files. Everything after that is already built.
4. Record one real response for the tests, so CI never calls the tool.

## What it proves

| Rule | Proved by |
|---|---|
| A tool's data takes a file's path | Connecting the demo gives the same uploads, figures and updates as uploading its two files by hand |
| The same checks as a file | A plan allowing one file a month lets the first through and stops the second, with the reason on the tool |
| Nothing new adds nothing | Pulling again with no change adds no file and no update |
| The daily pull respects access | It runs as the person who connected it under their company's row-level security, and waits when they can no longer manage tools |
| Companies stay apart | One company's connection is invisible to another, in the API and the database |
| No made-up data in production | Production refuses `CONNECTORS_DEMO` |
| The customer journey | Journey 7 in `web/e2e/tools.spec.ts` |
