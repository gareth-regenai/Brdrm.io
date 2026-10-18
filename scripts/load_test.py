"""Load test (E10). Many companies and investors using BoardRoom at once.

Phase 1, setting up: each company signs up, adds a raw finance export and a raw deals
export, shares both updates and invites an investor, who signs up from the email. The time
from adding the first file to the investor seeing its figures is measured against the BRD's
success measure: under 30 minutes.

Phase 2, reading: every person opens what they would open (the board pack, updates,
figures, the portfolio overview) for a fixed time, all at once.

Run it against an app started with MAILER=capture, such as scripts/e2e-stack.sh:

    backend/.venv/bin/python scripts/load_test.py --companies 20 --seconds 60

Numbers from a laptop only show how the code behaves under load; run it against staging
for numbers that count.
"""

import argparse
import asyncio
import random
import re
import statistics
import time
import uuid
from collections import defaultdict
from pathlib import Path

import httpx

FILES = Path(__file__).resolve().parents[1] / "backend" / "tests" / "fixtures" / "files"
PASSWORD = "correct horse battery"  # noqa: S105  a throwaway account for the test run


class Stats:
    def __init__(self) -> None:
        self.times: dict[str, list[float]] = defaultdict(list)
        self.errors: dict[str, int] = defaultdict(int)

    def add(self, name: str, seconds: float, ok: bool) -> None:
        self.times[name].append(seconds)
        if not ok:
            self.errors[name] += 1


class Client:
    def __init__(self, http: httpx.AsyncClient, stats: Stats) -> None:
        self.http = http
        self.stats = stats

    async def call(
        self,
        name: str,
        method: str,
        path: str,
        token: str | None = None,
        tenant: str | None = None,
        **kwargs: object,
    ) -> httpx.Response:
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if tenant:
            headers["X-Tenant-ID"] = tenant
        started = time.perf_counter()
        r = await self.http.request(method, path, headers=headers, **kwargs)  # type: ignore[arg-type]
        self.stats.add(name, time.perf_counter() - started, r.status_code < 400)
        return r


async def company(c: Client, n: int) -> dict[str, str] | None:
    tag = uuid.uuid4().hex[:8]
    r = await c.call(
        "sign up",
        "POST",
        "/auth/signup",
        json={
            "email": f"ceo-{tag}@load.example.com",
            "password": PASSWORD,
            "name": f"Load CEO {n}",
            "company_name": f"Load Company {n}",
        },
    )
    if r.status_code != 201:
        return None
    token, tenant = r.json()["access_token"], r.json()["tenant_id"]
    await c.call("skip setup", "POST", "/company/setup/skip", token, tenant)

    first_file = time.perf_counter()
    for name in ("xero_pnl.csv", "hubspot_deals.csv"):
        data = (FILES / name).read_bytes()
        r = await c.call(
            "start upload",
            "POST",
            "/company/uploads",
            token,
            tenant,
            json={"filename": name, "size_bytes": len(data), "content_type": "text/csv"},
        )
        link = r.json()
        await c.http.request(link["method"], link["url"], headers=link["headers"], content=data)
        await c.call(
            "finish upload", "POST", f"/company/uploads/{link['upload_id']}/complete", token, tenant
        )

    # Wait for both updates, then share them.
    for _ in range(600):
        r = await c.call("list updates", "GET", "/company/updates", token, tenant)
        updates = r.json() if r.status_code == 200 else []
        if len(updates) == 2 and all(u["figures"] for u in updates):
            break
        await asyncio.sleep(0.5)
    for u in updates:
        await c.call("approve", "POST", f"/company/updates/{u['id']}/approve", token, tenant)

    investor = f"investor-{tag}@load.example.com"
    await c.call(
        "invite",
        "POST",
        "/company/invitations",
        token,
        tenant,
        json={"email": investor, "role": "investor"},
    )
    invite = None
    for _ in range(100):
        r = await c.http.get("/e2e/mail", params={"to": investor})
        found = [re.search(r"invite\?token=([\w-]+)", m["body"]) for m in r.json()]
        invite = next((m.group(1) for m in found if m), None)
        if invite:
            break
        await asyncio.sleep(0.2)
    if invite is None:
        return None
    r = await c.call(
        "investor sign up",
        "POST",
        "/auth/signup",
        json={
            "email": investor,
            "password": PASSWORD,
            "name": f"Investor {n}",
            "invite_token": invite,
        },
    )
    investor_token = r.json()["access_token"]
    r = await c.call("investor pack", "GET", "/company/pack", investor_token, tenant)
    seen = r.status_code == 200 and bool(r.json()["figures"])
    c.stats.add("upload to investor sees figures", time.perf_counter() - first_file, seen)
    return {"tenant": tenant, "ceo": token, "investor": investor_token}


async def reader(c: Client, people: list[dict[str, str]], until: float) -> None:
    pages = [
        ("pack", "GET", "/company/pack", "ceo"),
        ("updates", "GET", "/company/updates", "ceo"),
        ("figures", "GET", "/company/metrics", "ceo"),
        ("dashboard files", "GET", "/company/uploads", "ceo"),
        ("investor pack", "GET", "/company/pack", "investor"),
        ("investor updates", "GET", "/company/updates", "investor"),
        ("portfolio overview", "GET", "/portfolio/overview", "investor"),
    ]
    while time.perf_counter() < until:
        p = random.choice(people)  # noqa: S311  load spread, not security
        name, method, path, who = random.choice(pages)  # noqa: S311
        tenant = None if path.startswith("/portfolio") else p["tenant"]
        await c.call(name, method, path, p[who], tenant)


def report(stats: Stats, seconds: float) -> None:
    print(f"\n{'Request':34} {'count':>6} {'errors':>6} {'p50 ms':>8} {'p95 ms':>8} {'max ms':>8}")
    for name, times in stats.times.items():
        times.sort()
        p95 = times[max(0, int(len(times) * 0.95) - 1)]
        print(
            f"{name:34} {len(times):6} {stats.errors[name]:6} "
            f"{statistics.median(times) * 1000:8.0f} {p95 * 1000:8.0f} {times[-1] * 1000:8.0f}"
        )
    reads = sum(len(stats.times[n]) for n in stats.times if n not in SETUP)
    print(f"\nReading phase: {reads / seconds:.0f} requests a second.")


SETUP = {
    "sign up",
    "skip setup",
    "start upload",
    "finish upload",
    "list updates",
    "approve",
    "invite",
    "investor sign up",
    "investor pack",
    "upload to investor sees figures",
}


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--companies", type=int, default=20)
    parser.add_argument("--readers", type=int, default=20, help="people reading at once")
    parser.add_argument("--seconds", type=int, default=60)
    args = parser.parse_args()

    stats = Stats()
    limits = httpx.Limits(max_connections=args.readers + args.companies)
    async with httpx.AsyncClient(base_url=args.api, timeout=60, limits=limits) as http:
        c = Client(http, stats)
        print(f"Setting up {args.companies} companies, each with an investor")
        made = await asyncio.gather(*(company(c, n) for n in range(args.companies)))
        people = [p for p in made if p]
        if not people:
            print("No company could be set up. Is the app running with MAILER=capture?")
            return 1
        print(f"Reading with {args.readers} people at once for {args.seconds} seconds")
        until = time.perf_counter() + args.seconds
        await asyncio.gather(*(reader(c, people, until) for _ in range(args.readers)))
    report(stats, args.seconds)
    failed = sum(stats.errors.values())
    slowest = max(stats.times["upload to investor sees figures"], default=0)
    print(f"Slowest upload to investor seeing figures: {slowest:.1f} seconds (target: 1,800).")
    print(f"Companies set up: {len(people)} of {args.companies}. Errors: {failed}.")
    return 0 if failed == 0 and len(people) == args.companies and slowest < 1800 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
