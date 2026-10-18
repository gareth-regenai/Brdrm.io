# BoardRoom.io build decisions (rules review), 18 October 2026

Build only. Commercials and pricing are parked.

## Tenancy and access (decided)
- Multi-tenant and multi-user. Target is hundreds to thousands of companies.
- Company team (CEO, department leads) see their own company only.
- The CEO invites each investor once to the company, and that invite is their standing access. The platform holds no cap table. They log in to a portfolio of every company they back, and see every published pack for each.
- Co-investors in the same company can see each other. Nothing crosses between companies.
- No per-pack grants and no hold-backs. Drafts and unpublished cycles stay hidden through the normal publish step.
- Investor login with a portfolio view moves into the MVP (Ali has it in Phase 3).

## Investor portfolio dashboard (decided)
- Top-level overview only, one row per company, same measures and same High, Medium, Low lines for every company (common defaults in config).
- Not shown to the CEO.
- Click a company to drill into that company's own section.
- Eight measures: cash balance, runway, net monthly burn, revenue against plan, pipeline coverage, delivery against plan (tasks completed against planned), headcount against plan, last pack published (days ago).

## Rules reviewed
1. Points dropped. Use tasks completed against planned.
2. Finance required columns accepted.
3. Hand-entered figures and person-written forecasts allowed, labelled "Entered by [name], [date]". Claude stays strict. Each figure keeps a small, minimised source line that opens the file, formula and check, or who entered it.
4. Number check: written figures may only be normal rounding of the real figure. No tolerance band. Click a figure for the exact value, source, check, what it moves (runway etc.) and its risk level (High, Medium, Low).
   - Warning lines: sensible defaults in config. Each company has a settings tool to choose what it sees and its display scale.
   - Display precision by annual revenue: under 100k whole pounds; 100k to 1m in k with 1 decimal; 1m to 10m in m with 3 decimals over 1m (k with 1 decimal below); 10m to 100m in m with 2 decimals (k whole below 1m); over 100m in m with 1 decimal. Months and percentages always 1 decimal. Company can move up or down a band.
   - Open: still to confirm whether cash, burn and runway need a named person to tick them before approval.
5. Investor access: standing, per company, set by one invite (see above).
6. Who can approve is a permissions setting. Parked to revisit when permissions are designed. Default stays the CEO.
7. Currency: accept any currency per row, converted to the company's reporting currency by the system with a published period rate. Rate is visible and can be overridden. No money added across companies. Needs a rates feed.
9. Pack voice: default is the company speaking as "we", with a setting to switch a company to third person. "Drafted by Claude" and "Approved by the CEO" labels unchanged.
10. Investor login and portfolio overview are in the MVP. CEO invites each investor once. The sponsor plan (investor pays and invites companies) stays later with commercials.
11. Published packs are editable. Each pack carries the note "Produced subject to change and may be edited". No version process, no per-item marks.
12. All approvals sit on the company side (who approves is a permissions setting, see 6). Investors only view and comment. Each update reads as a dated statement, e.g. "CEO X added new financials, true as of [upload date], subject to change".

## Upload principle (decided, replaces the file-rejection parts of rules 2, 7 and 8)
- Accept any file. The AI works out what each column is and ignores what it does not need. Pay-like columns (salary, bonus, bank details, NI numbers, dates of birth) are never stored.
- The five templates are guidance, not a gate.
- What the AI understood and ignored is logged for our dev team only. Neither the CEO nor the investor sees it.
- Ask one plain question only when a figure cannot be calculated without it.
- Code still does the calculations, the number check and the sign-off stay as agreed.

## AI-native principle (decided)
- BoardRoom is AI-native. Rules exist only for what must be exact: calculations, the number check, access and sign-off.
- Each tile has a fixed output, but the AI works out how to produce it from whatever the company uploaded. The AI writes the calculation, code runs it, so the arithmetic is exact and repeatable. The AI never gives a number from its head.
- The click view shows the method, the rows used and the exact figure. The number check still applies to commentary.
- Build-note test for every gate: why can't the AI handle this? Build the AI intake first, keep the app thin, demo working software early.

## To do
Plus: fixed flag thresholds (now config), Frankfurt-only region and UK residency.
