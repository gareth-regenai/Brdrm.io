# BoardRoom.io

BoardRoom.io turns the files a small company already has into figures its investors can trust and trace.

## Repository

| Folder | What is in it |
|---|---|
| backend/ | FastAPI app and Celery worker, one Postgres schema per module, Alembic migrations, tests |
| web/ | React app, styled only from design-system/tokens.json |
| render.yaml | Render Blueprint, Frankfurt |
| OPEN.md | Decisions the code does not make yet |
| docs/epics/ | A DEMO.md per epic: what to show and how to run it |

Start with docs/epics/E1/DEMO.md to run it locally.

## Dev pack, 18 October 2026

Everything needed to start the MVP build in Claude Code.

| Folder | What is in it |
|---|---|
| CLAUDE.md | Project instructions for Claude Code. Copy to the repo root. |
| docs/ | 01 revised MVP spec with changes marked and the reasoning. 02 BRD. 03 FRD with acceptance criteria. 04 decisions log. 05 epics and build order. docs/html/ has the same three documents as readable pages. |
| design-system/ | Brand README, tokens.json, logo SVGs, component previews. Build every screen from these. |
| mockup/ | The v5.7 mockup and example screens: tiles with the minimised source line, the investor flow, the setup chat, who sees which update. Mock data throughout. |
| reference/ | The previous spec, roadmap and market research for context, a number-check demo script, and the data sources table. Not build instructions. |

## How to start
1. Create the repo (separate from any other business) and copy CLAUDE.md to its root.
2. Open it in Claude Code and start with E1 in docs/05-Epics-and-build-order.md.
3. Build to the FRD. A requirement is done when its acceptance line passes in CI.
4. Demo at the end of every epic.

## Not in this pack
Pricing, tiers and limits (under separate review). Jira epics (to be created once a BoardRoom project exists). The open decisions in FRD chapter 14.
