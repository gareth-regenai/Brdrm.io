# Run BoardRoom.io on your laptop

The whole app on your own machine, with three demo companies and an investor already in
it, so you can check everything before a deploy. Nothing leaves your laptop: emails land
in a local inbox and files stay on your disk.

## Once: install Docker Desktop
Download Docker Desktop from docker.com, install it and open it. Leave it running.

## Start it
1. Get the code: on GitHub, open the repo, click **Code**, then **Download ZIP**, and unzip it.
   (Or `git clone` it, if you use git.)
2. Open Terminal in that folder. On a Mac: right-click the folder in Finder, then
   **New Terminal at Folder**.
3. Run:

   ```
   docker compose --profile app up --build -d
   ```

   The first start takes about five minutes. Later starts take seconds.
4. Open **http://localhost:3000**.

| Sign in as | Email | Sees |
|---|---|---|
| CEO of Kestrel Field | ellie@demo.boardroom.example.com | Xero and HubSpot exports, shared, with an investor thread |
| CEO of Northpath | sam@demo.boardroom.example.com | QuickBooks and Pipedrive exports, shared |
| CEO of Alder Labs | jo@demo.boardroom.example.com | A connected tool, and one update awaiting approval |
| Investor in all three | priya@demo.boardroom.example.com | The portfolio, read-only, with comments |

The password for every account is `boardroom-demo`.

Every email the app sends, such as invitations and @mentions, is in the local inbox at
**http://localhost:8025**. Click a link in one to follow it, as the person would.

## Your own files
Without an API key, Claude's answers are recorded ones that cover only the demo files.
Your own files still go in, but you match the columns yourself on the next screen.

To have Claude read your own files, create a file called `.env` in the folder with this line:

```
ANTHROPIC_API_KEY=your-key
```

Then run the start command again. This calls the live API and is charged to that key.

## Stop, reset, update
| To | Run |
|---|---|
| Stop it (keeps the data) | `docker compose --profile app down` |
| Start again from empty, demo data reloaded | `docker compose --profile app down -v`, then the start command |
| Take the latest code | Download it again (or `git pull`), then the start command |
| See what went wrong | `docker compose --profile app logs api worker` |

If the start fails because a port is in use, another app on your laptop holds 3000, 8000,
8025, 5432 or 6379. Close it and start again.

## How this differs from Render
The same code, with local stand-ins for the paid services:

| | Laptop | Render |
|---|---|---|
| Files | On your disk | S3-compatible storage |
| Email | Local inbox | SMTP |
| Claude | Recorded answers, unless `.env` has a key | Live API |
| Payment | Off, plans and limits still apply | Stripe, once keys are set |
| Demo tool | On | Off |

Before a deploy, the checks that matter most also run in CI on every pull request: the
tests, and the browser journeys in web/e2e (see docs/epics/E9/DEMO.md).
