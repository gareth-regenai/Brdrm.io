# E4 Setup chat: demo

**Done when:** a company is set up with at most two questions.

## What to show (about 5 minutes)

The setup is a short interview, as in `mockup/interview-example.html`: one question per message, each answer acknowledged before the next, never more than two questions.

1. Sign up as Priya Shah and add `quickbooks_monthly.csv` from `backend/tests/fixtures/files`, then choose **Start setup**.
2. "Hi Priya. I've read your files and set up most of Northwind Analytics, so there are just two questions. What are you aiming for in revenue this year?" Everything worked out from the files (currency, what the business does, revenue lines, targets, how money is shown) sits in the **Set up for you** card beside the chat, not in the messages.
3. Answer "About 5.4 million". "Got it, £5.4m this year, so £450k a month. Last one. Which investors should see your updates?" The card shows the target, and revenue against plan recalculates.
4. Answer "sam@seedfund.example.com". "That's everything. You can change any of it by telling me." The address waits for **Send invitations**; nothing is emailed until then. **Skip** in the answer row moves on to the next question instead.
5. Type "We report in euros". The currency changes and the figures redraw in euros.
6. Start again with `xero_pnl.csv` and `budget_2026.csv`: the budget supplies the targets, so the interview has one question.
7. **Finish later**, then **Reopen setup**: "Welcome back Priya. What would you like to change?" **Settings** offers the same choices as a plain form.

Steps 1 to 5 run without a key: code runs the interview and reads simple answers itself. With `ANTHROPIC_API_KEY` set, the model writes the messages and reads freer answers ("Update my targets: revenue 90k for September", "Our revenue was actually 999,999", which changes no figure).

## Requirements covered

| FR | Status | Proved by |
|---|---|---|
| FR-8.1 | Done | With a P&L, a budget and a website, the facts sent to the chat hold all five inferences and the profile is filled without a question. The Set up for you card shows them |
| FR-8.2 | Done | The assumptions are shown in the card, not asked; "we report in euros" changes the currency setting and the figures |
| FR-8.3 | Done | With a budget the only question is investors; without, targets and investors; none once both are known. Without the model the whole interview completes in two answers, one question per message |
| FR-8.4 | Done | Skipping keeps the defaults; reopening and "update my targets" sets a target |
| FR-8.5 | Done | No figure field in the schema; a chat message about revenue changes no figure; a target or email the CEO did not type is refused |
| FR-10.4 | Done | Messages API with structured outputs, writing only to settings. History is sent append-only |
| FR-4.11 | Done | Targets from the chat, from settings, from a hand-entered figure or from a budget file all feed revenue against plan |

## Not yet

- The interview has not been run against the real model. Its replies in tests are scripted; the code-run interview is tested end to end.
