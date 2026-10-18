# The board pack, as in mockup v5.7: demo

**Done when:** the company and its investors see the same "Full Picture", investors read-only with comments and tags.

## Run it

As in `docs/epics/E5/DEMO.md`, then `alembic upgrade head` again for comment tags. With `SKILL1_REPLAY_DIR` set, `xero_pnl.csv` gets a recorded Claude draft.

## What to show (about 5 minutes)

1. Sign up and add `xero_pnl.csv` and `hubspot_deals.csv`. The sidebar has Dashboard, Board pack, Files, Team and Settings, with the company box under it.
2. **Dashboard**: a greeting, the date the data is true as of, **Open the board pack**, the latest updates with their status, and **Needs attention** (an update waiting for your approval, commentary waiting for a person, a file with a question).
3. **Board pack**: "The Full Picture". The Overview has a card for each section, progress to plan (once a target is set), the headline figures and the founder update, labelled "Drafted by Claude" and "Number check: passed". Cashflow has the figures with their click view and a monthly revenue and net burn chart. Market validation has the pipeline. Updates has every dated update with its commentary and thread. Roadmap, Product and People say what arrives in phase 2.
4. While an update waits, the pack says so, and its figures say "Awaiting approval". Approve it from the Updates tab.
5. Sign in as an investor. The same pack, marked **Read-only**, with only what was shared. In a comment, type "@" and choose the CEO: the CEO is emailed "Priya Shah mentioned you".

## Covered

| What | Proved by |
|---|---|
| Same view, shared only | The company's pack and the investor's hold the same figures once shared; before that the investor's pack is empty, the company's marks each figure as awaiting approval |
| Monthly series, targets, commentary | Six months of revenue, net burn and cash from the update's own calculation; revenue against its target; the headline and note, never the board questions |
| @mentions | A tagged person is emailed once, by name; an investor can tag the Owner, CEO, department leads and other investors but not the whole team; a name must be chosen from the list and written as @Name; an investor cannot be tagged before the update is shared |
| FR-6.5, FR-7.4 | As before, now inside the pack |

## Left out on purpose

- The quarterly cycle stepper and "Submit for approval" in v5.7: dated updates replaced cycles in the revised spec.
- Risk register and CEO development: in v5.7 but not in the revised FRD. Left out by decision; they need their own requirements first.
