"""Fill a running BoardRoom with demo data, through the API, as real people would.

Three companies and one investor who backs all three:

- Kestrel Field: the CEO answers the setup chat, adds a Xero export and a HubSpot deals
  export, shares both, and invites the investor, who comments; the CEO replies and tags
  them.
- Northpath: QuickBooks and Pipedrive exports, shared.
- Alder Labs: connects the demo tool instead of exporting anything, and shares one update,
  so one update still waits for approval.

The app must run with CONNECTORS_DEMO=true. The investor's invitation links are read from
the local inbox (--mailpit, as docker compose does) or from the capture mailbox
(MAILER=capture, as scripts/e2e-stack.sh does):

    docker compose --profile app up --build          # runs this for you
    backend/.venv/bin/python backend/scripts/seed_demo.py --suffix 2   # against e2e-stack.sh

If the demo companies are already there it changes nothing. It prints the sign-ins. Every
account uses the password below. Demo data only.
"""

import argparse
import re
import sys
import time
from collections.abc import Callable
from pathlib import Path

import httpx

FILES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "files"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PASSWORD = "boardroom-demo"  # noqa: S105  demo accounts only


class Api:
    def __init__(self, base: str, mailpit: str | None) -> None:
        self.http = httpx.Client(base_url=base, timeout=60)
        self.mailpit = mailpit
        self.used: set[str] = set()

    def call(
        self,
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
        r = self.http.request(method, path, headers=headers, **kwargs)  # type: ignore[arg-type]
        if r.status_code >= 400:
            sys.exit(f"{method} {path} failed: {r.status_code} {r.text}")
        return r

    def upload(self, token: str, tenant: str, name: str) -> None:
        data = (FILES / name).read_bytes()
        kind = XLSX if name.endswith(".xlsx") else "text/csv"
        link = self.call(
            "POST",
            "/company/uploads",
            token,
            tenant,
            json={"filename": name, "size_bytes": len(data), "content_type": kind},
        ).json()
        self.http.request(link["method"], link["url"], headers=link["headers"], content=data)
        self.call("POST", f"/company/uploads/{link['upload_id']}/complete", token, tenant)

    def wait_for_updates(self, token: str, tenant: str, count: int) -> list[dict]:
        for _ in range(240):
            updates = self.call("GET", "/company/updates", token, tenant).json()
            if len(updates) >= count and all(u["figures"] for u in updates):
                return updates
            time.sleep(0.5)
        sys.exit("The files were not processed. Is the worker running?")

    def bodies(self, to: str) -> list[str]:
        """Every email sent to this address, oldest first."""
        if self.mailpit is None:
            return [m["body"] for m in self.http.get("/e2e/mail", params={"to": to}).json()]
        found = httpx.get(f"{self.mailpit}/api/v1/search", params={"query": f"to:{to}"}).json()
        ids = [m["ID"] for m in reversed(found["messages"])]
        return [httpx.get(f"{self.mailpit}/api/v1/message/{i}").json()["Text"] for i in ids]

    def invite_link(self, to: str) -> str:
        """The newest invitation to this address that has not been used yet."""
        for _ in range(150):
            tokens = [re.search(r"invite\?token=([\w-]+)", body) for body in self.bodies(to)]
            fresh = [t.group(1) for t in tokens if t and t.group(1) not in self.used]
            if fresh:
                self.used.add(fresh[-1])
                return fresh[-1]
            time.sleep(0.2)
        sys.exit("No invitation email arrived. Is the app running with MAILER=capture?")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--domain", default="demo.boardroom.example.com")
    parser.add_argument("--mailpit", help="the local inbox, for example http://localhost:8025")
    parser.add_argument("--suffix", default="", help="added to each address, to seed again")
    args = parser.parse_args()
    api = Api(args.api, args.mailpit)
    tag = f".{args.suffix}" if args.suffix else ""

    def email(who: str) -> str:
        return f"{who}{tag}@{args.domain}"

    signed_in = api.http.post("/auth/login", json={"email": email("ellie"), "password": PASSWORD})
    if signed_in.status_code == 200:
        print("The demo companies are already there.")
        sign_ins(email)
        return

    def company(name: str, person: str, who: str) -> tuple[str, str]:
        r = api.call(
            "POST",
            "/auth/signup",
            json={"email": email(who), "password": PASSWORD, "name": person, "company_name": name},
        ).json()
        return r["access_token"], r["tenant_id"]

    # Kestrel Field: setup chat, two exports, both shared.
    ellie, kestrel = company("Kestrel Field", "Ellie Marsh", "ellie")
    api.call("POST", "/company/setup/start", ellie, kestrel)
    api.call("POST", "/company/setup/messages", ellie, kestrel, json={"text": "Skip"})
    api.call("POST", "/company/setup/messages", ellie, kestrel, json={"text": "Skip"})
    api.upload(ellie, kestrel, "xero_pnl.csv")
    api.upload(ellie, kestrel, "hubspot_deals.csv")
    for u in api.wait_for_updates(ellie, kestrel, 2):
        api.call("POST", f"/company/updates/{u['id']}/approve", ellie, kestrel)
    # The revenue target, set in Settings once the files are in.
    api.call(
        "PUT",
        "/company/settings/targets",
        ellie,
        kestrel,
        json=[{"metric": "revenue", "period": "2026-09", "value": "75000"}],
    )

    # The investor joins from the emailed link.
    priya_email = email("priya")
    api.call(
        "POST",
        "/company/invitations",
        ellie,
        kestrel,
        json={"email": priya_email, "role": "investor"},
    )
    priya = api.call(
        "POST",
        "/auth/signup",
        json={
            "email": priya_email,
            "password": PASSWORD,
            "name": "Priya Shah",
            "invite_token": api.invite_link(priya_email),
        },
    ).json()["access_token"]
    [finance] = [
        u
        for u in api.call("GET", "/company/updates", priya, kestrel).json()
        if "financ" in u["headline"]
    ]
    api.call(
        "POST",
        f"/company/updates/{finance['id']}/comments",
        priya,
        kestrel,
        json={"body": "Thanks Ellie. What drove the drop in burn in September?", "mentions": []},
    )
    me = api.call("GET", "/me", priya).json()
    api.call(
        "POST",
        f"/company/updates/{finance['id']}/comments",
        ellie,
        kestrel,
        json={"body": "@Priya Shah two contractor roles ended in August.", "mentions": [me["id"]]},
    )

    # Northpath: QuickBooks and Pipedrive.
    sam, northpath = company("Northpath", "Sam Hart", "sam")
    api.call("POST", "/company/setup/skip", sam, northpath)
    api.upload(sam, northpath, "quickbooks_monthly.csv")
    api.upload(sam, northpath, "pipedrive_deals.xlsx")
    for u in api.wait_for_updates(sam, northpath, 2):
        api.call("POST", f"/company/updates/{u['id']}/approve", sam, northpath)

    # Alder Labs: a connected tool instead of exports; one update left awaiting approval.
    jo, alder = company("Alder Labs", "Jo Patel", "jo")
    api.call("POST", "/company/setup/skip", jo, alder)
    api.call("POST", "/company/connections/demo", jo, alder)
    first, *_ = api.wait_for_updates(jo, alder, 2)
    api.call("POST", f"/company/updates/{first['id']}/approve", jo, alder)

    # The same investor backs all three.
    for token, tenant in ((sam, northpath), (jo, alder)):
        api.call(
            "POST",
            "/company/invitations",
            token,
            tenant,
            json={"email": priya_email, "role": "investor"},
        )
        api.call("POST", "/invitations/accept", priya, json={"token": api.invite_link(priya_email)})

    print("Demo data ready.")
    sign_ins(email)


def sign_ins(email: Callable[[str], str]) -> None:
    print("Open http://localhost:3000. Password for every account:", PASSWORD)
    print(f"  CEO of Kestrel Field   {email('ellie')}")
    print(f"  CEO of Northpath       {email('sam')}")
    print(f"  CEO of Alder Labs      {email('jo')}  (one update awaiting approval)")
    print(f"  Investor in all three  {email('priya')}")


if __name__ == "__main__":
    main()
