# E10 part 3: the load test

`scripts/load_test.py` sets up many companies at once, each adding a raw finance export and a raw deals export, sharing both updates and inviting an investor, who signs up from the email. It then has everyone open what they would open (board pack, updates, figures, files, portfolio overview) continuously, all at once, with no pause between clicks.

## Run it

```bash
WEB_CONCURRENCY=2 E2E_WORKER=1 scripts/e2e-stack.sh      # the app, with a real worker
backend/.venv/bin/python scripts/load_test.py --companies 20 --readers 20 --seconds 30
```

It exits with an error if any request failed, any company could not be set up, or any investor waited longer than 30 minutes for figures (the BRD success measure).

## Results on a laptop, 18 October 2026

20 companies and 20 investors, then 20 people reading at once for 30 seconds, with no pause between clicks (much harder than real use).

| | One API process, library pool | Two API processes, pool 10 + 10 |
|---|---|---|
| Errors | Failed: the database connection pool ran out (15) | **0** |
| First file to the investor seeing figures (slowest) | | **17 seconds** (target: 30 minutes) |
| Requests a second while reading | 23 | **38** |
| Board pack, median under load | 1,600 ms | **910 ms** |
| Board pack, one request alone | 110 ms | 110 ms |

## What it changed

- **Database pool.** The first run failed: SQLAlchemy's default of 5 connections plus 10 ran out under 20 people. The pool is now a setting (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT`), 10 + 10 by default, sized so two API processes and the worker stay well under the database's limit.
- **Two API processes.** Alone, the board pack takes 110 ms; under load it waited in line behind one Python process. `WEB_CONCURRENCY=2` on the API in `render.yaml` runs two.
- **The test stack can run a real worker** (`E2E_WORKER=1`), as production does. The journeys keep delivering events inside the request, which is simpler for a browser test.

Run it again against staging once Render is connected: a laptop shows how the code behaves under load, not what the servers will do.
