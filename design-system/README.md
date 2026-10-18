BoardRoom.io turns department CSVs into a board pack in which every figure can be traced to the row it came from. The brand should feel like a well-run board table: calm, exact and a little warm. This system matches the mockup at v5.7. Use these rules whenever you build a screen, a pack, a deck or an email for it.

## Content fundamentals

- Write in plain British English, sentence case, no exclamation marks. Say "organisation", "analyse", "£".
- Lead with the number, then the reason. Good: "Runway is 17.6 months: £1.378m cash over £78.1k average burn." Bad: "Exciting insights on your runway journey!"
- Address the reader as "you" in the app and "the company" in a pack. Packs never say "we".
- Never say "AI-powered", "magic" or "smart". Say who did what: "Drafted by Claude, 41 of 41 figures match", "Edited by the sales lead", "Approved by the CEO".
- A figure Claude could not verify is shown as "Not provided", never estimated. Advice and forecasts beyond the plan do not appear in a pack.
- Button labels are verbs that name the result: "Submit for approval", "Approve cycle and push to investors", "Confirm mapping". No emoji anywhere.
- The product's rule is the voice's rule: Claude suggests, code calculates, a person approves. Copy never blurs which of the three acted.
- Translate to board level. A row is never passed through as the headline: say what it is, why it matters and what it moves. Ticket, deal and row ids go in the source line only.

## Colour

The source palette is six colours: `deep-ocean`, `ocean`, `coral`, `brick`, `seat` and `paper`. Screens are built from the role tokens, which switch between Light and Dark (Graphite).

- Page ground is `bg`; cards, tables and fields are `surface`. Text is `ink`; secondary text is `ink-muted`.
- The primary button is `primary` with `on-primary` text: deep ocean in light, coral in dark. A view has one primary action.
- Coral means "look here": the current step, destructive actions, off-plan and warning text (`accent-ink`), focus rings and the approver seat. Never use it for decoration or body links.
- Status uses the Ocean family: `ok` (teal) for on plan or passed, `warn` (coral-brown) for check this, `err` (brick) for off plan or blocking, `info` (blue) for in review. Each is text on its own `-bg` tint.
- The risk register has a four-step heat scale, `risk-1` (ocean) through `risk-4` (solid coral), by likelihood times impact: under 5, 5 to 9, 10 to 14, 15 and up. A risk card has a left stripe in its severity colour.
- Charts use `chart-1` to `chart-10` in order. The monthly revenue and net burn chart puts revenue in `chart-1` and net burn in `chart-3` (coral), so money out always stands out; the figures are labelled on every bar. Label series directly. `chart-2`, `chart-6` and `chart-7` (light) and `chart-8` (dark) are under 3:1, so use them for large areas, never as the only cue.
- Large brand fields (cover, page header, section band) use `brand-fill` with white text.
- Every status carries a word as well as a colour, so status is never told by hue alone.
- Dark is Graphite: near-black `bg`, white `ink`, body weight 500, `brand` becomes a light ocean blue and the primary button becomes coral.

## Typography

- Headlines, card titles and big figures are `display` (Outfit 600). Everything else is `sans` (Nunito Sans). There is no monospace: source lines and ids are small Nunito Sans.
- Body copy is `body` in `ink`. Captions, deltas and source lines are `small` in `ink-muted`. Table headers, tags and status pills use `label`, which is always uppercase with tracking.
- Align numbers to the right in tables and turn on tabular figures (`font-variant-numeric: tabular-nums`).
- Load both families from Google Fonts, or self-host them. Until they load, the `type.families` fallbacks apply.

## Space, corners and depth

- Spacing steps are `space-1` to `space-8` on a 4px base. Cards use `space-5` padding; table cells use `space-3`.
- Everything is 3px (`radius-md`) with `corner-shape: bevel`: slightly angled, not rounded. Pills, tags, timeline bars, stepper chips and small buttons are 2px (`radius-sm`). Only avatars and toggles are round (`radius-round`).
- Prefer a 1px `border-subtle` hairline to a shadow. `shadow-overlay` is for the roadmap popup and menus only.
- Layout is a single column of sections at 720px to 960px for packs, and a 1120px page for the app and website. The mockup collapses to a bottom bar at 640px and its width selector has presets for a foldable's cover screen (360) and unfolded narrow (720) and wide (980).
- Override styles go last. An invalid `var()` inside a shorthand drops the whole declaration.

## Figures, tables and charts

- A figure is always shown with its unit, its period and a source line, for example "hubspot_deals_q3.csv, column arr_gbp, 96 active accounts". Clicking a figure opens its trace: source file, cell, calculation and check.
- Off-plan figures use `accent-ink` and say how far off plan: "92% of plan".
- Label series directly rather than with a legend where there is room. Never rely on colour alone to tell two series apart; vary the lightness or the line style.

## Logo

The mark is a round board table seen from above with six seats; the top seat is coral, for the approver. The wordmark "BoardRoom.io" is typeset live in `display` 600, with ".io" in `ink-muted`. Use `assets/Logo/boardroom-mark.svg` on light grounds and `boardroom-mark-reversed.svg` on dark ones. Rules for clear space and size are in the Logo group's README. The name is a working name and may change.

## Iconography

Icons are outline-only, 1.5px stroke, on a 20px or 24px grid, drawn in `ink`, `ink-muted` or the colour of the state they belong to. Pair every icon with a text label unless the control has an accessible name and a tooltip. No emoji, no filled or multi-colour icons.

## Differences from the mockup

Where the mockup fails 4.5:1 for text or 3:1 for a control edge, this system adjusts one value and the mockup should follow:

- `ok` light is #16666C, not #1E7F86 (5.4:1 on its tint, not 3.9:1).
- `accent` light is #C94F2A for fills that carry white text (4.5:1, not 3.5:1 on #E0613C). The logo coral stays #E0613C.
- Dark primary and accent fills carry dark text (5.2:1), not white (3.5:1).
- `border-strong` is new, for input and secondary-button edges. The mockup's `border` is 1.5:1 in light.
- `risk-2-ink` light is #8A4520 and `risk-4` light is #C94F2A.
- The dark reversed mark has grey seats so the approver seat stays distinct.

## Components

Each component has a live preview and a guideline: Logo, Button, StatusPill, MetricTile, DataTable and PackSection. Build new pack screens from these before inventing new ones.
